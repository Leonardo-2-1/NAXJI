"""Opt-in local: NAXJI_TEST_PG_PORT. Crea y elimina SOLO una base de prueba nueva.

Host fijo loopback, usuario naxji_step3, sin .env ni Supabase. El clúster debe ser
exclusivo de pruebas. auth.users es una tabla mínima; no prueba Auth ni RLS.
"""
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from src.adapters.out.persistence.postgres import (
    InformeRepositoryPostgres, PlantillaRepositoryPostgres, PostgresUnidadTrabajo,
)
from src.domain.entities.informe import Informe, VersionInforme
from src.domain.value_objects.estados import OrigenVersion, Rol
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.seccion_salida import secciones_a_json, secciones_desde_json
from src.infrastructure.configuration.database import DatabaseSettings
from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from src.adapters.out.ai.context_predictor_mock import ContextPredictorMock
from src.adapters.out.ai.generador_borrador_mock import GeneradorBorradorMock
from tests.test_estructura_borrador import DEMO

pytestmark = pytest.mark.skipif(not os.getenv("NAXJI_TEST_PG_PORT"), reason="PostgreSQL local aislado: opt-in")
ROOT = Path(__file__).resolve().parents[1]


def script(connection, relative):
    connection.execute((ROOT / relative).read_text(encoding="utf-8-sig"))


@pytest.fixture
def db_local():
    admin = DatabaseSettings("127.0.0.1", int(os.environ["NAXJI_TEST_PG_PORT"]), "postgres", "naxji_step3", "", sslmode="disable")
    nombre = "naxji_step3_test_" + uuid4().hex
    with admin.connect(autocommit=True) as conexion:
        conexion.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(nombre)))
    settings = replace(admin, dbname=nombre)
    try:
        with settings.connect(autocommit=True) as c:
            c.execute("CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY)")
            script(c, "NAXJI_database_schema_actual.sql")
            script(c, "database/seeds/pmv1_catalogos.sql")
            uid = uuid4()
            c.execute("INSERT INTO auth.users VALUES (%s)", (uid,))
            c.execute("INSERT INTO public.perfiles(id,nombres,apellidos) VALUES (%s,'DEMO','Pruebas')", (uid,))
            pid = c.execute("SELECT id FROM public.plantillas WHERE nombre='Informe Técnico – Piloto NAXJI'").fetchone()[0]
            sid = c.execute("INSERT INTO public.solicitudes(usuario_id,asunto,plantilla_id) VALUES (%s,'DEMO anterior',%s) RETURNING id", (uid, pid)).fetchone()[0]
            iid = c.execute("INSERT INTO public.informes(solicitud_id,plantilla_id,creado_por) VALUES (%s,%s,%s) RETURNING id", (sid, pid, uid)).fetchone()[0]
            contenido = {"antecedentes": "A", "desarrollo": "D", "conclusiones": "C", "objetivo": "Anterior", "encabezado": {"asunto": "Anterior"}}
            c.execute("INSERT INTO public.versiones_informe(informe_id,numero_version,contenido,origen,creado_por) VALUES (%s,1,%s,'IA',%s)", (iid, Jsonb(contenido), uid))
            # Toda fila anterior, incluidos timestamps, debe ser idéntica tras migrar.
            tablas = ["plantillas", "campos_plantilla", "solicitudes", "informes", "versiones_informe"]
            previos = {t: c.execute(sql.SQL("SELECT to_jsonb(t) FROM public.{} t ORDER BY id").format(sql.Identifier(t))).fetchall() for t in tablas}
            script(c, "database/migrations/20260930_01_secciones_salida.sql")
            script(c, "database/migrations/20260930_01_secciones_salida.sql")
            for tabla in tablas:
                actuales = c.execute(sql.SQL("SELECT to_jsonb(t) - 'secciones_salida' FROM public.{} t ORDER BY id").format(sql.Identifier(tabla))).fetchall()
                assert actuales == previos[tabla]
            script(c, "database/seeds/paso3_estructura_piloto.sql")
            piloto = c.execute("SELECT to_jsonb(p) FROM public.plantillas p WHERE id=%s", (pid,)).fetchone()[0]
            script(c, "database/seeds/paso3_estructura_piloto.sql")
            assert c.execute("SELECT to_jsonb(p) FROM public.plantillas p WHERE id=%s", (pid,)).fetchone()[0] == piloto
        yield settings, uid, pid, iid, contenido
    finally:
        with admin.connect(autocommit=True) as conexion:
            # nombre se genera arriba; nunca acepta una base del entorno o del usuario.
            conexion.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(nombre)))


def test_migracion_preserva_versiones_y_repositorios_recuperan_snapshot(db_local):
    settings, uid, pid, iid, contenido = db_local
    uow = PostgresUnidadTrabajo(settings)
    plantillas, informes = PlantillaRepositoryPostgres(uow), InformeRepositoryPostgres(uow)
    assert secciones_a_json(plantillas.obtener_por_id(pid).secciones_salida) == DEMO[0]["secciones_salida"]
    anterior = informes.obtener_por_id(iid)
    assert anterior.versiones[0].contenido == contenido
    assert anterior.versiones[0].secciones_salida is None
    deps = Container(Settings(persistence_mode="postgres", auth_mode="disabled"), database_settings=settings,
                     predictor=ContextPredictorMock(), generador=GeneradorBorradorMock())
    editado = deps.actualizar_borrador.ejecutar(iid, UsuarioActual(uid, frozenset({Rol.FUNCIONARIO})),
                                              {**contenido, "objetivo": "Edición compatible"}, 1)
    assert editado.versiones[-1].secciones_salida is None
    with settings.connect() as c:
        assert c.execute("SELECT secciones_salida IS NULL FROM public.versiones_informe WHERE id=%s", (editado.versiones[-1].id,)).fetchone()[0]
    for demo in DEMO:
        estructura = secciones_desde_json(demo["secciones_salida"])
        with settings.connect() as c:
            # Dos plantillas de prueba con estructuras distintas; ninguna se instala en catálogos reales.
            p = c.execute("INSERT INTO public.plantillas(nombre,tipo_informe_id,secciones_salida) SELECT %s,tipo_informe_id,%s FROM public.plantillas WHERE id=%s RETURNING id", (demo["nombre"], Jsonb(demo["secciones_salida"]), pid)).fetchone()[0]
            s = c.execute("INSERT INTO public.solicitudes(usuario_id,asunto,plantilla_id) VALUES (%s,'DEMO persistencia',%s) RETURNING id", (uid, p)).fetchone()[0]
        assert plantillas.obtener_por_id(p).secciones_salida == estructura
        nuevo = Informe(s, p, uid)
        nuevo.versiones.append(VersionInforme(nuevo.id, 1, {sec.clave: "Texto de prueba" for sec in estructura}, OrigenVersion.IA, uid, secciones_salida=estructura))
        informes.guardar(nuevo)
        # Otra instancia/ conexión de repositorio debe recuperar el mismo orden y valores.
        recuperado = InformeRepositoryPostgres(PostgresUnidadTrabajo(settings)).obtener_por_id(nuevo.id)
        assert recuperado.versiones == nuevo.versiones
        with settings.connect() as c:
            c.execute("UPDATE public.plantillas SET secciones_salida=NULL WHERE id=%s", (p,))
        assert informes.obtener_por_id(nuevo.id).versiones[0].secciones_salida == estructura


def test_postgres_rechaza_estructura_invalida_sin_alterar_registros(db_local):
    settings, _, pid, _, _ = db_local
    for valor in [[], {}, None, [{"clave": "encabezado", "titulo": "No", "obligatoria": True}],
                  [{"clave": "resumen", "titulo": "X", "obligatoria": "true"}], DEMO[1]["secciones_salida"] * 2]:
        with pytest.raises(psycopg.errors.CheckViolation):
            with settings.connect() as c:
                c.execute("UPDATE public.plantillas SET secciones_salida=%s WHERE id=%s", (Jsonb(valor), pid))
    with settings.connect() as c:
        assert c.execute("SELECT secciones_salida FROM public.plantillas WHERE id=%s", (pid,)).fetchone()[0] == DEMO[0]["secciones_salida"]
