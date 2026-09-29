"""Comprueba conexion y tablas de Supabase en una transaccion de solo lectura.

Lee .env desde la raiz del repositorio. Nunca imprime credenciales ni errores
sin filtrar del proveedor. No importa la aplicacion ni carga sus modelos de IA.
Con --crud prueba operaciones sobre una fila ficticia y revierte la transaccion.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from uuid import uuid4

import psycopg
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.infrastructure.configuration.database import DatabaseSettings, database_error


ROOT = Path(__file__).resolve().parents[1]


def report(**values: object) -> None:
    print(json.dumps(values, ensure_ascii=True))


class CrudCheckError(Exception):
    """Fallo de comprobacion con un codigo fijo, sin datos del proveedor."""


def check_crud(connection: psycopg.Connection) -> dict:
    """Prueba solo una fila creada por esta ejecucion; nunca confirma cambios."""
    fixture_id = uuid4()
    code = "TEST_CRUD_" + fixture_id.hex[:20]
    original_name = "NAXJI - prueba CRUD temporal"
    updated_name = "NAXJI - prueba CRUD actualizada"

    columns = dict(connection.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='tipos_informe'"
    ).fetchall())
    required = {"id": "uuid", "codigo": "character varying", "nombre": "character varying",
                "descripcion": "text", "activo": "boolean", "created_at": "timestamp with time zone"}
    if any(columns.get(k) != v for k, v in required.items()):
        raise CrudCheckError("tipos_informe_structure_mismatch")
    fingerprint_sql = (
        "SELECT count(*), md5(coalesce(string_agg(row_to_json(t)::text, '' ORDER BY id), '')) "
        "FROM public.tipos_informe t"
    )
    before = connection.execute(fingerprint_sql).fetchone()
    # Termina la consulta inicial antes de comenzar una transaccion independiente.
    connection.rollback()
    connection.read_only = False
    try:
        with connection.transaction(force_rollback=True):
            connection.execute("SET LOCAL statement_timeout = '10s'")
            connection.execute("SET LOCAL lock_timeout = '3s'")
            # Un trigger o una regla personalizada podria tener efectos externos
            # que no se reviertan con ROLLBACK: requiere revisar esa tabla primero.
            custom_behaviour = connection.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_trigger "
                "WHERE tgrelid = 'public.tipos_informe'::regclass "
                "AND NOT tgisinternal AND tgenabled <> 'D') "
                "OR EXISTS (SELECT 1 FROM pg_rules "
                "WHERE schemaname = 'public' AND tablename = 'tipos_informe')"
            ).fetchone()[0]
            if custom_behaviour:
                raise CrudCheckError("custom_triggers_or_rules_require_review")

            inserted = connection.execute(
                "INSERT INTO public.tipos_informe (id, codigo, nombre) "
                "VALUES (%s, %s, %s) RETURNING id, codigo, nombre, activo",
                (fixture_id, code, original_name),
            ).fetchone()
            if inserted != (fixture_id, code, original_name, True):
                raise CrudCheckError("create_verification_failed")

            selected = connection.execute(
                "SELECT id, codigo, nombre, activo FROM public.tipos_informe "
                "WHERE id = %s AND codigo = %s", (fixture_id, code),
            ).fetchone()
            if selected != inserted:
                raise CrudCheckError("read_verification_failed")

            updated = connection.execute(
                "UPDATE public.tipos_informe SET nombre = %s "
                "WHERE id = %s AND codigo = %s RETURNING id",
                (updated_name, fixture_id, code),
            ).fetchall()
            selected = connection.execute(
                "SELECT nombre FROM public.tipos_informe "
                "WHERE id = %s AND codigo = %s", (fixture_id, code),
            ).fetchone()
            if updated != [(fixture_id,)] or selected != (updated_name,):
                raise CrudCheckError("update_verification_failed")

            deleted = connection.execute(
                "DELETE FROM public.tipos_informe "
                "WHERE id = %s AND codigo = %s RETURNING id", (fixture_id, code),
            ).fetchall()
            remaining = connection.execute(
                "SELECT count(*) FROM public.tipos_informe WHERE id = %s",
                (fixture_id,),
            ).fetchone()[0]
            if deleted != [(fixture_id,)] or remaining != 0:
                raise CrudCheckError("delete_verification_failed")

            # Repone la misma fila ficticia sin commit para verificar que el rollback
            # tambien elimina una escritura pendiente, independientemente del DELETE.
            connection.execute(
                "INSERT INTO public.tipos_informe (id, codigo, nombre) "
                "VALUES (%s, %s, %s)", (fixture_id, code, original_name),
            )

    finally:
        connection.read_only = True
        connection.execute("SET LOCAL statement_timeout = '10s'")
        remaining = connection.execute(
            "SELECT count(*) FROM public.tipos_informe WHERE id = %s OR codigo = %s",
            (fixture_id, code),
        ).fetchone()[0]
        after = connection.execute(fingerprint_sql).fetchone()
        if before != after:
            raise CrudCheckError("original_records_changed_or_concurrent_activity")
        if remaining != 0:
            raise CrudCheckError("rollback_verification_failed")
        report(status="ok", rollback="verified", remaining_test_rows=remaining,
               original_records_unchanged=True)
    return {
        "status": "ok", "scope": "supabase_postgresql",
        "table": "public.tipos_informe", "fixture_id": str(fixture_id),
        "crud": {"create": "ok", "read": "ok", "update": "ok", "delete": "ok"},
        "original_count": before[0], "final_count": after[0], "original_records_unchanged": True,
        "rollback": "ok", "remaining_test_rows": remaining,
    }


def main(*, crud: bool = False) -> int:
    try:
        config = DatabaseSettings.from_env()
    except ValueError as error:
        report(status="error", category="configuration", detail=str(error))
        return 1

    schema = (ROOT / "NAXJI_database_schema_actual.sql").read_text(encoding="utf-8")
    expected = sorted(set(re.findall(
        r"create\s+table\s+if\s+not\s+exists\s+public\.([a-z_]+)", schema, re.I,
    )))
    if not expected:
        report(status="error", category="reference_schema_has_no_tables")
        return 1

    try:
        with config.connect() as connection:
            connection.read_only = True
            if not connection.pgconn.ssl_in_use:
                report(status="error", category="connection_is_not_encrypted")
                return 1
            conexion = connection.execute("SELECT 1 AS conexion").fetchone()[0]
            report(status="ok", conexion=conexion, ssl=True)
            connection.execute("SET LOCAL statement_timeout = '10s'")
            database, user, read_only = connection.execute(
                "SELECT current_database(), current_user, "
                "current_setting('transaction_read_only')"
            ).fetchone()
            if read_only != "on":
                report(status="error", category="transaction_is_not_read_only")
                return 1
            found = {row[0] for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "AND table_name = ANY(%s)", (expected,),
            ).fetchall()}
            report(
                status="ok", authenticated=True, ssl=True, read_only=True,
                database=database, database_role=user,
                expected_tables=len(expected), visible_tables=len(found),
                tables=sorted(found),
                missing_or_inaccessible_tables=sorted(set(expected) - found),
            )
            if set(expected) - found:
                return 1
            count = connection.execute("SELECT COUNT(*) FROM public.tipos_informe").fetchone()[0]
            report(status="ok", table="public.tipos_informe", count=count)
            if crud:
                if "tipos_informe" not in found:
                    raise CrudCheckError("tipos_informe_missing_or_inaccessible")
                report(**check_crud(connection))
        return 0
    except CrudCheckError as error:
        report(status="error", category=str(error))
        return 1
    except psycopg.Error as error:
        report(status="error", category=database_error(error), sqlstate=error.sqlstate)
        return 1



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--crud", action="store_true",
        help="Prueba crear, leer, actualizar y eliminar una fila ficticia con rollback.",
    )
    raise SystemExit(main(crud=parser.parse_args().crud))