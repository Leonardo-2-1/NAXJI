"""Semilla v2 en PostgreSQL loopback aislado, sin leer .env ni tocar Supabase."""
from copy import deepcopy
import os
from uuid import UUID

import psycopg
from psycopg import sql
import pytest
from fastapi.testclient import TestClient

from src.adapters.out.ai.context_predictor_mock import ContextPredictorMock
from src.adapters.out.ai.generador_borrador_mock import GeneradorBorradorMock
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.domain.value_objects.fuentes_piloto import campos_fuente_piloto
from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.dependencies import get_current_user
from src.main import create_app
from tests.test_estructura_postgres import db_local, script  # noqa: F401
from tests.test_piloto_v2 import preparar_v2, leer_docx


pytestmark = pytest.mark.skipif(not os.getenv("NAXJI_TEST_PG_PORT"), reason="PostgreSQL aislado: opt-in")
SEED = "database/seeds/20261001_piloto_v2_datos_fuente.sql"


def snapshot(c):
    return {tabla: c.execute(sql.SQL("SELECT to_jsonb(t) FROM public.{} t ORDER BY id").format(sql.Identifier(tabla))).fetchall()
            for tabla in ["plantillas", "campos_plantilla", "solicitudes", "solicitud_valores", "informes", "versiones_informe"]}


def test_semilla_aditiva_idempotente_y_persistencia_de_versiones(db_local):
    db, uid, pid, iid_antiguo, contenido_antiguo = db_local
    with db.connect(autocommit=True) as c:
        antes = snapshot(c)
        script(c, SEED)
        despues = snapshot(c)
        for tabla, registros in antes.items():
            assert all(r in despues[tabla] for r in registros), tabla
        assert len(despues["plantillas"]) == len(antes["plantillas"]) + 1
        assert len(despues["campos_plantilla"]) == len(antes["campos_plantilla"]) + 6
        script(c, SEED)
        assert snapshot(c) == despues
    settings = Settings(persistence_mode="postgres", auth_mode="disabled")
    deps = Container(settings, database_settings=db, predictor=ContextPredictorMock(), generador=GeneradorBorradorMock())
    usuario = UsuarioActual(uid, frozenset({Rol.FUNCIONARIO}))
    app = create_app(settings, deps)
    app.dependency_overrides[get_current_user] = lambda: usuario
    with TestClient(app) as client:
        assert client.get(f"/informes/{iid_antiguo}").json()["contenido"] == contenido_antiguo
        leer_docx(client.get(f"/informes/{iid_antiguo}/versiones/1/docx"))
        sid, plantilla = preparar_v2(client)
        p = next(p for p in deps.plantillas.listar() if p.version == 2)
        esperado = campos_fuente_piloto(p.id)
        assert [(c.clave,c.etiqueta,c.obligatorio,c.tipo_dato,c.configuracion) for c in p.campos] == [
            (c.clave,c.etiqueta,c.obligatorio,c.tipo_dato,c.configuracion) for c in esperado]
        generado = client.post(f"/solicitudes/{sid}/generar-borrador", json={})
        assert generado.status_code == 201, generado.text
        informe = generado.json()
        iid = informe["informe_id"]
        contenido = {**informe["contenido"], "conclusiones": "Edición persistida de prueba. Pendiente de verificación."}
        assert client.put(f"/informes/{iid}", json={"numero_version": 1, "contenido": contenido}).status_code == 200
        otro = Container(settings, database_settings=db, predictor=ContextPredictorMock(), generador=GeneradorBorradorMock())
        recuperado = otro.obtener_informe.por_solicitud(UUID(sid), usuario)
        assert recuperado.versiones[-1].contenido == contenido
        assert recuperado.versiones[0].contenido == informe["contenido"]
        with db.connect() as c:
            antes_descarga = snapshot(c)
        leer_docx(client.get(f"/informes/{iid}/versiones/2/docx"))
        with db.connect() as c:
            assert snapshot(c) == antes_descarga


def test_semilla_rechaza_definicion_v2_conflictiva_sin_sobrescribir(db_local):
    db = db_local[0]
    with db.connect(autocommit=True) as c:
        script(c, SEED)
        c.execute("UPDATE public.campos_plantilla SET etiqueta='Personalizado' WHERE clave='hechos_conocidos'")
        antes = deepcopy(snapshot(c))
        with pytest.raises(psycopg.errors.RaiseException):
            script(c, SEED)
        c.execute("ROLLBACK")
        assert snapshot(c) == antes
