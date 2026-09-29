"""Opt-in: NAXJI_RUN_DB_TESTS=1. No crea usuarios, políticas ni esquema.

Las identidades se inyectan SOLO en TestClient: no prueba Supabase Auth/RLS.
Las pruebas de escritura completa requieren perfiles y catálogos ya existentes.
"""
import os
from uuid import uuid4
import subprocess
import sys
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from scripts.verificar_supabase import check_crud, CrudCheckError
from src.infrastructure.configuration.database import DatabaseSettings
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.configuration.container import Container
from src.infrastructure.dependencies import get_current_user
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.adapters.out.ai.context_predictor_mock import ContextPredictorMock
from src.main import create_app


pytestmark = pytest.mark.skipif(os.getenv("NAXJI_RUN_DB_TESTS") != "1", reason="Supabase: prueba opt-in")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database():
    return DatabaseSettings.from_env()


@pytest.fixture
def postgres(database):
    return Container(Settings(persistence_mode="postgres", auth_mode="disabled"),
                     database_settings=database, predictor=ContextPredictorMock())


def test_crud_script_and_rollback_after_injected_failure(database, capsys):
    with database.connect() as connection:
        result = check_crud(connection)
        assert result["original_records_unchanged"]
        assert result["remaining_test_rows"] == 0
        class FailingConnection:
            def __getattr__(self, name):
                return getattr(connection, name)

            @property
            def read_only(self):
                return connection.read_only

            @read_only.setter
            def read_only(self, value):
                connection.read_only = value

            def execute(self, query, params=None):
                if query.startswith("UPDATE public.tipos_informe"):
                    raise CrudCheckError("fallo_inyectado_antes_update")
                return connection.execute(query, params)

        with pytest.raises(CrudCheckError, match="fallo_inyectado"):
            check_crud(FailingConnection())
        assert '"rollback": "verified"' in capsys.readouterr().out


def test_endpoint_reads_actual_postgres_catalog(database, postgres):
    settings = Settings(persistence_mode="postgres", auth_mode="disabled")
    app = create_app(settings, postgres)
    # Solo para leer catálogos en esta prueba; no crea ningún perfil.
    user = UsuarioActual(uuid4(), frozenset({Rol.FUNCIONARIO}))
    app.dependency_overrides[get_current_user] = lambda: user
    with database.connect() as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        expected = connection.execute("SELECT id, codigo FROM public.tipos_informe WHERE activo ORDER BY codigo").fetchall()
    with TestClient(app) as client:
        result = client.get("/tipos-informe")
        assert result.status_code == 200, result.text
        assert [(r["id"], r["codigo"]) for r in result.json()] == [(str(i), code) for i, code in expected]
        assert client.get("/areas").status_code == 200
        assert client.get("/plantillas").status_code == 200
    print(f"GET /tipos-informe: 200, {len(expected)} IDs iguales a PostgreSQL; autenticacion inyectada")


def test_repositories_read_temporary_catalogs_and_rollback(database, postgres):
    area_id, template_id, campo_id, norma_id = (uuid4() for _ in range(4))
    code = "TEST_" + uuid4().hex[:24]
    class AbortTest(Exception):
        pass
    with pytest.raises(AbortTest):
        with postgres.uow.transaccion():
            with postgres.uow.connection() as c:
                tipo = c.execute("SELECT id FROM public.tipos_informe WHERE activo ORDER BY codigo LIMIT 1").fetchone()
                if tipo is None:
                    pytest.skip("No hay tipos de informe activos")
                c.execute("INSERT INTO public.areas_municipales (id,codigo,nombre) VALUES (%s,%s,%s)",
                          (area_id, code, "Prueba temporal"))
                c.execute("INSERT INTO public.normativas (id,codigo,titulo,tipo) VALUES (%s,%s,%s,'OTRO')",
                          (norma_id, code, "Prueba temporal sin valor normativo"))
                c.execute("INSERT INTO public.plantillas (id,nombre,tipo_informe_id,area_id) VALUES (%s,%s,%s,%s)",
                          (template_id, code, tipo["id"], area_id))
                c.execute("INSERT INTO public.campos_plantilla "
                          "(id,plantilla_id,clave,etiqueta,tipo_dato,orden,configuracion) "
                          "VALUES (%s,%s,'prueba','Prueba','text',1,'{}')", (campo_id, template_id))
            assert area_id in {a.id for a in postgres.catalogos.areas()}
            assert postgres.catalogos.normativa(norma_id).codigo == code
            assert postgres.catalogos.normativa_por_codigo(code).id == norma_id
            template = postgres.plantillas.obtener_por_id(template_id)
            assert template.campos[0].id == campo_id
            assert template_id in {p.id for p in postgres.plantillas.listar()}
            assert postgres.solicitudes.obtener_por_id(uuid4()) is None
            assert postgres.predicciones.ultima(uuid4()) is None
            assert postgres.informes.obtener_por_id(uuid4()) is None
            assert postgres.informes.obtener_por_solicitud(uuid4()) is None
            raise AbortTest()
    with database.connect() as c:
        for table, identifier in (("areas_municipales", area_id), ("plantillas", template_id),
                                  ("campos_plantilla", campo_id), ("normativas", norma_id)):
            assert c.execute(sql.SQL("SELECT count(*) FROM public.{} WHERE id=%s").format(sql.Identifier(table)),
                             (identifier,)).fetchone()[0] == 0


def test_endpoint_rejects_nonexistent_profile_and_rolls_back(database, postgres):
    marker = "TEST_API_" + uuid4().hex
    app = create_app(Settings(persistence_mode="postgres", auth_mode="disabled"), postgres)
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(uuid4(), frozenset({Rol.FUNCIONARIO}))
    with TestClient(app) as client:
        result = client.post("/solicitudes", json={"asunto": marker})
        assert result.status_code == 400, result.text
        assert "Referencias" in result.json()["detail"]
    with database.connect() as c:
        assert c.execute("SELECT count(*) FROM public.solicitudes WHERE asunto=%s", (marker,)).fetchone()[0] == 0
    print("POST /solicitudes sin perfil: 400; fila no persistida; FK conservada")


def eligible_profile(database):
    with database.connect() as c:
        c.execute("SET TRANSACTION READ ONLY")
        row = c.execute("SELECT p.id FROM public.perfiles p JOIN public.usuario_roles ur ON ur.usuario_id=p.id "
                        "JOIN public.roles r ON r.id=ur.rol_id WHERE p.activo AND r.activo "
                        "AND r.codigo IN ('FUNCIONARIO','ADMINISTRADOR') ORDER BY p.id LIMIT 1").fetchone()
    if row is None:
        pytest.skip("Persistencia tras reinicio bloqueada: no existe perfil activo con rol de escritura; no se crean usuarios")
    return row[0]


def test_request_survives_two_backend_processes(database):
    profile_id = eligible_profile(database)
    marker = "TEST_RESTART_" + uuid4().hex
    worker = ROOT / "tests" / "postgres_restart_worker.py"
    identifier = None
    try:
        first = subprocess.run([sys.executable, str(worker), "create", str(profile_id), marker],
                               cwd=ROOT, capture_output=True, text=True, timeout=60, check=True)
        identifier = json.loads(first.stdout)["id"]
        with database.connect() as c:
            assert c.execute("SELECT asunto FROM public.solicitudes WHERE id=%s", (identifier,)).fetchone() == (marker,)
        second = subprocess.run([sys.executable, str(worker), "read", str(profile_id), identifier],
                                cwd=ROOT, capture_output=True, text=True, timeout=60, check=True)
        assert json.loads(second.stdout)["asunto"] == marker
        print("POST proceso 1 -> SELECT PostgreSQL -> GET proceso 2: OK")
    finally:
        with database.connect() as c:
            # Solo la solicitud temporal sin hijos creada por esta prueba.
            c.execute("DELETE FROM public.solicitudes WHERE asunto=%s AND usuario_id=%s", (marker, profile_id))
        with database.connect() as c:
            assert c.execute("SELECT count(*) FROM public.solicitudes WHERE asunto=%s", (marker,)).fetchone()[0] == 0


def test_full_endpoint_flow_uses_postgres_aggregates(database, postgres):
    """Todos los agregados, JSON, versiones y conflicto optimista; rollback global."""
    profile_id = eligible_profile(database)
    area_id, tipo_id, template_id, field_id, norma_id = (uuid4() for _ in range(5))
    marker = "TEST_" + uuid4().hex[:24]
    request_id = None
    from src.domain.entities.prediccion_contexto import PrediccionContexto, NormativaPredicha
    from src.application.ports.output.context_predictor import ContextPredictor
    class PredictorFixture(ContextPredictor):
        def predecir(self, asunto, solicitud_id):
            return PrediccionContexto(solicitud_id, tipo_id, area_id, 0.9, 0.9, "TEST_PREDICTOR",
                                     normativas=[NormativaPredicha(norma_id, 0.8, 1)])
    postgres.predecir_contexto.predictor = PredictorFixture()
    app = create_app(Settings(persistence_mode="postgres", auth_mode="disabled"), postgres)
    with database.connect() as c:
        roles = c.execute("SELECT r.codigo FROM public.roles r JOIN public.usuario_roles ur ON r.id=ur.rol_id "
                          "WHERE ur.usuario_id=%s AND r.activo", (profile_id,)).fetchall()
    user = UsuarioActual(profile_id, frozenset(Rol(r[0]) for r in roles))
    app.dependency_overrides[get_current_user] = lambda: user
    class RollbackFixture(Exception):
        pass
    with pytest.raises(RollbackFixture):
        with postgres.uow.transaccion():
            with postgres.uow.connection() as c:
                c.execute("INSERT INTO public.areas_municipales(id,codigo,nombre) VALUES (%s,%s,%s)", (area_id, marker, marker))
                c.execute("INSERT INTO public.tipos_informe(id,codigo,nombre) VALUES (%s,%s,%s)", (tipo_id, marker, marker))
                c.execute("INSERT INTO public.normativas(id,codigo,titulo,tipo) VALUES (%s,%s,%s,'OTRO')", (norma_id, marker, marker))
                c.execute("INSERT INTO public.plantillas(id,nombre,tipo_informe_id) VALUES (%s,%s,%s)", (template_id, marker, tipo_id))
                c.execute("INSERT INTO public.campos_plantilla(id,plantilla_id,clave,etiqueta,tipo_dato,orden,obligatorio) "
                          "VALUES (%s,%s,'antecedentes','Prueba','textarea',1,true)", (field_id, template_id))
            with TestClient(app) as client:
                result = client.post("/solicitudes", json={"asunto": marker, "tipo_informe_id": str(tipo_id),
                                     "plantilla_id": str(template_id), "area_destino_id": str(area_id)})
                assert result.status_code == 201, result.text
                request_id = result.json()["id"]
                url = f"/solicitudes/{request_id}"
                values = {"valores": [{"campo_plantilla_id": str(field_id), "valor": "Prueba temporal"}]}
                assert client.put(url + "/valores", json=values).status_code == 200
                prediction = client.post(url + "/predecir-contexto")
                assert prediction.status_code == 200, prediction.text
                valid = client.post(url + "/validar-prediccion", json={"prediccion_id": prediction.json()["id"], "resultado": "ACEPTADA"})
                assert valid.status_code == 200, valid.text
                generated = client.post(url + "/generar-borrador", json={})
                assert generated.status_code == 201, generated.text
                report = generated.json()
                content = {**report["contenido"], "conclusiones": "Editado en PostgreSQL"}
                edited = client.put("/informes/" + report["informe_id"], json={"contenido": content, "numero_version": 1})
                assert edited.status_code == 200, edited.text
                assert edited.json()["numero_version"] == 2
                assert client.get("/informes/" + report["informe_id"]).json()["contenido"] == content
                assert client.put("/informes/" + report["informe_id"], json={"contenido": content, "numero_version": 1}).status_code == 409
                assert client.get(url).json()["estado"] == "GENERADA"
                with postgres.uow.connection() as c:
                    assert c.execute("SELECT count(*) AS n FROM public.versiones_informe WHERE informe_id=%s", (report["informe_id"],)).fetchone()["n"] == 2
            raise RollbackFixture()
    with database.connect() as c:
        assert c.execute("SELECT count(*) FROM public.solicitudes WHERE id=%s", (request_id,)).fetchone()[0] == 0
