"""Auditoría y ejecución independiente del SQL: solo PostgreSQL desechable loopback."""
import os

import psycopg
import pytest

from scripts.verificar_inspeccion_guardada import comparar, definicion_sql, diferencias, leer_catalogo
from tests.test_estructura_postgres import db_local, script  # noqa: F401
from tests.test_inspeccion_piloto import NOMBRE, SEED, TECNICA, snapshot

pytestmark = pytest.mark.skipif(not os.getenv("NAXJI_TEST_PG_PORT"), reason="PostgreSQL aislado: opt-in")


def test_reproduce_42p01_y_semilla_no_depende_de_objetos_entre_conexiones(db_local):
    db = db_local[0]
    with db.connect(autocommit=True) as c:
        # Reproduce el fallo de una sentencia temporal ejecutada fuera de la
        # transacción que la consume; NO asume que así operó el SQL Editor real.
        c.execute("CREATE TEMP TABLE naxji_inspeccion_piloto(n integer) ON COMMIT DROP")
        with pytest.raises(psycopg.errors.UndefinedTable) as error:
            c.execute("SELECT * FROM naxji_inspeccion_piloto")
        assert error.value.sqlstate == "42P01"
        script(c, TECNICA)
        antes = snapshot(c)
        script(c, SEED)  # autocommit, una sola sentencia DO
        despues = snapshot(c)
        assert len(despues["plantillas"]) == len(antes["plantillas"]) + 1
        assert len(despues["campos_plantilla"]) == len(antes["campos_plantilla"]) + 7
        for tabla, registros in antes.items():
            assert all(r in despues[tabla] for r in registros), tabla
        assert c.execute("SELECT count(*) FROM pg_class WHERE relpersistence='t' AND relname LIKE 'naxji_inspeccion%'").fetchone()[0] == 0
    for autocommit in (True, False, True):
        with db.connect(autocommit=autocommit) as otra:
            script(otra, SEED)
            assert snapshot(otra) == despues  # IDs, timestamps y datos intactos
    with db.connect() as c:
        assert snapshot(c) == despues


def test_respeta_la_transaccion_externa_y_el_rollback(db_local):
    db = db_local[0]
    with db.connect(autocommit=True) as c:
        antes = snapshot(c)
    with db.connect() as c:
        script(c, SEED)
        assert c.execute("SELECT count(*) FROM public.plantillas WHERE nombre=%s", (NOMBRE,)).fetchone()[0] == 1
        c.rollback()  # El DO no hace COMMIT de la transacción de quien lo llama.
    with db.connect(autocommit=True) as c:
        assert snapshot(c) == antes
        script(c, SEED)
        assert c.execute("SELECT count(*) FROM public.plantillas WHERE nombre=%s", (NOMBRE,)).fetchone()[0] == 1


CAMPO = " WHERE plantilla_id IN (SELECT id FROM public.plantillas WHERE nombre=%s) AND clave='estado_resultados'"
PLANTILLA = " WHERE nombre=%s"


@pytest.mark.parametrize("cambio", [
    "DELETE FROM public.campos_plantilla" + CAMPO,
    "UPDATE public.campos_plantilla SET etiqueta='Distinta'" + CAMPO,
    "UPDATE public.campos_plantilla SET tipo_dato='textarea'" + CAMPO,
    "UPDATE public.campos_plantilla SET obligatorio=false" + CAMPO,
    "UPDATE public.campos_plantilla SET orden=8" + CAMPO,
    "UPDATE public.campos_plantilla SET activo=false" + CAMPO,
    "UPDATE public.campos_plantilla SET clave='otro_campo'" + CAMPO,
    "UPDATE public.campos_plantilla SET configuracion=configuracion-'valores_sin_resultados'" + CAMPO,
    "UPDATE public.campos_plantilla SET configuracion=configuracion || '{\"extra\":true}'::jsonb" + CAMPO,
    "UPDATE public.campos_plantilla SET configuracion=jsonb_set(configuracion,'{opciones,0}','\"Otra opcion\"')" + CAMPO,
    "UPDATE public.plantillas SET tipo_informe_id=(SELECT id FROM public.tipos_informe WHERE codigo='INFORME_TECNICO')" + PLANTILLA,
    "UPDATE public.plantillas SET area_id=NULL" + PLANTILLA,
    "UPDATE public.plantillas SET activa=false" + PLANTILLA,
    "UPDATE public.plantillas SET descripcion='Distinta'" + PLANTILLA,
    "UPDATE public.plantillas SET secciones_salida=jsonb_set(secciones_salida,'{0,titulo}','\"Distinto\"')" + PLANTILLA,
    "UPDATE public.plantillas SET secciones_salida=jsonb_set(secciones_salida,'{5,obligatoria}','true')" + PLANTILLA,
    "UPDATE public.plantillas SET secciones_salida=(secciones_salida->5) || (secciones_salida - 5)" + PLANTILLA,
    "UPDATE public.plantillas SET secciones_salida=secciones_salida - 5" + PLANTILLA,
])
def test_auditoria_y_semilla_detectan_definicion_distinta_sin_repararla(db_local, cambio):
    db = db_local[0]
    with db.connect(autocommit=True) as c:
        script(c, SEED)
        c.execute(cambio, (NOMBRE,))  # Mutación deliberada SOLO en base desechable.
        antes = snapshot(c)
        with pytest.raises(psycopg.errors.RaiseException):
            script(c, SEED)
        assert snapshot(c) == antes  # No completa campos faltantes ni sobrescribe.
    with db.connect() as c:
        c.read_only = True
        c.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        esperado = definicion_sql()
        resultado = comparar(esperado, leer_catalogo(c, esperado))
        assert not resultado["integra"] and resultado["diferencias"]
    with db.connect() as c:
        assert snapshot(c) == antes


def test_fallo_al_insertar_campos_revierte_tambien_la_plantilla(db_local):
    db = db_local[0]
    with db.connect(autocommit=True) as c:
        c.execute("""CREATE FUNCTION public.fallo_inspeccion_prueba() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN IF NEW.clave='informacion_pendiente' THEN RAISE EXCEPTION 'Fallo simulado de prueba'; END IF;
          RETURN NEW; END $$;
          CREATE TRIGGER fallo_inspeccion BEFORE INSERT ON public.campos_plantilla
          FOR EACH ROW EXECUTE FUNCTION public.fallo_inspeccion_prueba()""")
        antes = snapshot(c)
        with pytest.raises(psycopg.errors.RaiseException):
            script(c, SEED)
        assert snapshot(c) == antes
        c.execute("DROP TRIGGER fallo_inspeccion ON public.campos_plantilla")
        script(c, SEED)
        assert c.execute("SELECT count(*) FROM public.plantillas WHERE nombre=%s", (NOMBRE,)).fetchone()[0] == 1


def test_lectura_completa_integra_con_columnas_y_sin_mutaciones(db_local):
    db = db_local[0]
    with db.connect(autocommit=True) as c:
        script(c, SEED)
        antes = snapshot(c)
    esperado = definicion_sql()
    with db.connect() as c:
        c.read_only = True
        c.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        datos = leer_catalogo(c, esperado)
        resultado = comparar(esperado, datos)
        assert resultado["integra"] and not resultado["diferencias"]
        assert len(resultado["campos_comparados"]) == 7
        assert all(resultado["comprobaciones"].values())
        # La propia conexión impide escrituras accidentales.
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            c.execute("UPDATE public.plantillas SET activa=activa WHERE false")
        c.rollback()
    with db.connect() as c:
        assert snapshot(c) == antes


def test_comparador_respeta_tipos_y_orden_pero_no_orden_de_claves():
    assert not diferencias({"a": 1, "b": False}, {"b": False, "a": 1})
    assert diferencias({"a": 1}, {"a": True})
    assert diferencias({"a": ["uno", "dos"]}, {"a": ["dos", "uno"]})
