"""Comprueba conexion y tablas de Supabase en una transaccion de solo lectura.

Lee .env desde la raiz del repositorio. Nunca imprime credenciales ni errores
sin filtrar del proveedor. No importa la aplicacion ni carga sus modelos de IA.
Con --crud prueba operaciones sobre una fila ficticia y revierte la transaccion.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]


def report(**values: object) -> None:
    print(json.dumps(values, ensure_ascii=True))


class CrudCheckError(Exception):
    """Fallo de comprobacion con un codigo fijo, sin datos del proveedor."""


def check_crud(connection: psycopg.Connection) -> dict:
    """Prueba solo una fila creada por esta ejecucion; nunca confirma cambios."""
    fixture_id = uuid4()
    code = "TEST_" + fixture_id.hex[:24]
    original_name = "NAXJI - prueba CRUD temporal"
    updated_name = "NAXJI - prueba CRUD actualizada"

    # Termina la consulta inicial antes de comenzar una transaccion independiente.
    connection.rollback()
    connection.read_only = False
    with connection.transaction(force_rollback=True):
        connection.execute("SET LOCAL statement_timeout = '10s'")
        connection.execute("SET LOCAL lock_timeout = '3s'")
        # Un trigger o una regla personalizada podria tener efectos externos
        # que no se reviertan con ROLLBACK: requiere revisar esa tabla primero.
        custom_behaviour = connection.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_trigger "
            "WHERE tgrelid = 'public.areas_municipales'::regclass "
            "AND NOT tgisinternal AND tgenabled <> 'D') "
            "OR EXISTS (SELECT 1 FROM pg_rules "
            "WHERE schemaname = 'public' AND tablename = 'areas_municipales')"
        ).fetchone()[0]
        if custom_behaviour:
            raise CrudCheckError("custom_triggers_or_rules_require_review")

        inserted = connection.execute(
            "INSERT INTO public.areas_municipales (id, codigo, nombre) "
            "VALUES (%s, %s, %s) RETURNING id, codigo, nombre, activo",
            (fixture_id, code, original_name),
        ).fetchone()
        if inserted != (fixture_id, code, original_name, True):
            raise CrudCheckError("create_verification_failed")

        selected = connection.execute(
            "SELECT id, codigo, nombre, activo FROM public.areas_municipales "
            "WHERE id = %s AND codigo = %s", (fixture_id, code),
        ).fetchone()
        if selected != inserted:
            raise CrudCheckError("read_verification_failed")

        updated = connection.execute(
            "UPDATE public.areas_municipales SET nombre = %s "
            "WHERE id = %s AND codigo = %s RETURNING id",
            (updated_name, fixture_id, code),
        ).fetchall()
        selected = connection.execute(
            "SELECT nombre FROM public.areas_municipales "
            "WHERE id = %s AND codigo = %s", (fixture_id, code),
        ).fetchone()
        if updated != [(fixture_id,)] or selected != (updated_name,):
            raise CrudCheckError("update_verification_failed")

        deleted = connection.execute(
            "DELETE FROM public.areas_municipales "
            "WHERE id = %s AND codigo = %s RETURNING id", (fixture_id, code),
        ).fetchall()
        remaining = connection.execute(
            "SELECT count(*) FROM public.areas_municipales WHERE id = %s",
            (fixture_id,),
        ).fetchone()[0]
        if deleted != [(fixture_id,)] or remaining != 0:
            raise CrudCheckError("delete_verification_failed")

        # Repone la misma fila ficticia sin commit para verificar que el rollback
        # tambien elimina una escritura pendiente, independientemente del DELETE.
        connection.execute(
            "INSERT INTO public.areas_municipales (id, codigo, nombre) "
            "VALUES (%s, %s, %s)", (fixture_id, code, original_name),
        )

    connection.read_only = True
    connection.execute("SET LOCAL statement_timeout = '10s'")
    remaining = connection.execute(
        "SELECT count(*) FROM public.areas_municipales WHERE id = %s OR codigo = %s",
        (fixture_id, code),
    ).fetchone()[0]
    if remaining != 0:
        raise CrudCheckError("rollback_verification_failed")
    return {
        "status": "ok", "scope": "supabase_postgresql",
        "table": "public.areas_municipales", "fixture_id": str(fixture_id),
        "crud": {"create": "ok", "read": "ok", "update": "ok", "delete": "ok"},
        "rollback": "ok", "remaining_test_rows": remaining,
    }


def main(*, crud: bool = False) -> int:
    # Evita que un error de sintaxis de .env exponga su contenido en los logs.
    logging.getLogger("dotenv.main").disabled = True
    config = dotenv_values(ROOT / ".env", encoding="utf-8-sig", interpolate=False)
    required = (
        "NAXJI_DB_HOST", "NAXJI_DB_PORT", "NAXJI_DB_NAME", "NAXJI_DB_USER",
        "NAXJI_DB_PASSWORD", "NAXJI_DB_SSLMODE",
    )
    missing = [key for key in required if not config.get(key)]
    if missing:
        report(status="error", category="missing_configuration", fields=missing)
        return 1
    password = config["NAXJI_DB_PASSWORD"]
    if password.startswith(("postgresql://", "postgres://")):
        report(status="error", category="password_contains_connection_uri")
        return 1
    if password.strip().lower() in {"[your-password]", "your-password", "[oculta]"}:
        report(status="error", category="password_is_placeholder")
        return 1
    if config["NAXJI_DB_SSLMODE"] not in {"require", "verify-ca", "verify-full"}:
        report(status="error", category="encrypted_connection_required")
        return 1
    try:
        port = int(config["NAXJI_DB_PORT"])
        timeout = int(config.get("NAXJI_DB_CONNECT_TIMEOUT") or "10")
        if not 1 <= port <= 65535 or not 1 <= timeout <= 30:
            raise ValueError
    except ValueError:
        report(status="error", category="invalid_port_or_timeout")
        return 1

    schema = (ROOT / "NAXJI_database_schema_actual.sql").read_text(encoding="utf-8")
    expected = sorted(set(re.findall(
        r"create\s+table\s+if\s+not\s+exists\s+public\.([a-z_]+)", schema, re.I,
    )))
    if not expected:
        report(status="error", category="reference_schema_has_no_tables")
        return 1

    try:
        with psycopg.connect(
            host=config["NAXJI_DB_HOST"], port=port, dbname=config["NAXJI_DB_NAME"],
            user=config["NAXJI_DB_USER"], password=password,
            sslmode=config["NAXJI_DB_SSLMODE"], connect_timeout=timeout,
            application_name="naxji_connection_check",
        ) as connection:
            connection.read_only = True
            if not connection.pgconn.ssl_in_use:
                report(status="error", category="connection_is_not_encrypted")
                return 1
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
                missing_or_inaccessible_tables=sorted(set(expected) - found),
            )
            if crud:
                if "areas_municipales" not in found:
                    raise CrudCheckError("areas_municipales_missing_or_inaccessible")
                report(**check_crud(connection))
        return 0
    except CrudCheckError as error:
        report(status="error", category=str(error))
        return 1
    except psycopg.Error as error:
        # Clasifica internamente; nunca devuelve el mensaje original ni el DSN.
        detail = str(error).lower()
        category = "database_connection_or_query_failed"
        if "password authentication failed" in detail or error.sqlstate == "28P01":
            category = "authentication_failed"
        elif "tenant or user not found" in detail:
            category = "project_or_user_not_found"
        elif "timeout" in detail or "timed out" in detail:
            category = "connection_or_query_timeout"
        elif "certificate" in detail or "ssl" in detail:
            category = "tls_error"
        elif "permission denied" in detail or error.sqlstate == "42501":
            category = "permission_denied"
        report(status="error", category=category, sqlstate=error.sqlstate)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--crud", action="store_true",
        help="Prueba crear, leer, actualizar y eliminar una fila ficticia con rollback.",
    )
    raise SystemExit(main(crud=parser.parse_args().crud))
