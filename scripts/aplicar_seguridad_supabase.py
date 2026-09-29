"""Valida la migración RLS con rollback; --apply confirma solo políticas y trigger.

Los registros sintéticos se revierten incluso al usar --apply. No cambia las
tres cuentas existentes ni sus perfiles/roles. No imprime credenciales ni UUID.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from src.infrastructure.configuration.database import DatabaseSettings, ROOT, database_error


MIGRATION = ROOT / "migrations/20260928_01_auth_rls.sql"


def assert_check(condition, name):
    if not condition:
        raise RuntimeError(name)
    print(name + ": OK")


def protected_fingerprint(c):
    records = []
    for query in (
        "SELECT row_to_json(t)::text FROM public.perfiles t ORDER BY id",
        "SELECT row_to_json(t)::text FROM public.usuario_roles t ORDER BY usuario_id,rol_id",
        "SELECT row_to_json(t)::text FROM public.roles t ORDER BY id",
        "SELECT id::text,email,encrypted_password FROM auth.users ORDER BY id",
    ):
        records.append(c.execute(query).fetchall())
    return hashlib.sha256(json.dumps(records).encode()).hexdigest()


def expect_denied(c, query, parameters=()):
    try:
        with c.transaction():
            c.execute(query, parameters)
    except psycopg.errors.InsufficientPrivilege:
        return
    raise RuntimeError("La operación no autorizada no fue rechazada")


def validate(c):
    before = protected_fingerprint(c)
    users = c.execute(
        "SELECT u.email,p.id FROM auth.users u JOIN public.perfiles p ON p.id=u.id "
        "WHERE u.email=ANY(%s) AND p.activo",
        (["funcionario1.naxji@gmail.com", "funcionario2.naxji@gmail.com"],),
    ).fetchall()
    mapping = dict(users)
    if len(mapping) != 2:
        raise RuntimeError("Faltan los dos perfiles de funcionarios existentes")
    a, b = mapping["funcionario1.naxji@gmail.com"], mapping["funcionario2.naxji@gmail.com"]
    request_id = uuid4()
    with c.transaction(force_rollback=True):
        c.execute("INSERT INTO public.solicitudes(id,usuario_id,asunto) VALUES (%s,%s,%s)",
                  (request_id, a, "TEST_RLS_" + uuid4().hex))
        c.execute("SET LOCAL ROLE authenticated")
        role, bypass = c.execute("SELECT current_user,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
        assert_check(role == "authenticated" and not bypass, "RLS_contexto_sin_BYPASSRLS")
        c.execute("SELECT set_config('request.jwt.claims',%s,true)", (json.dumps({"sub": str(a), "role": "authenticated"}),))
        assert_check(c.execute("SELECT count(*) FROM public.solicitudes WHERE id=%s", (request_id,)).fetchone()[0] == 1,
                     "RLS_funcionario_A_lee_su_solicitud")
        c.execute("SELECT set_config('request.jwt.claims',%s,true)",
                  (json.dumps({"sub": str(b), "role": "authenticated", "user_metadata": {"role": "ADMINISTRADOR"}}),))
        assert_check(c.execute("SELECT count(*) FROM public.solicitudes WHERE id=%s", (request_id,)).fetchone()[0] == 0,
                     "RLS_funcionario_B_no_lee_solicitud_A_ni_eleva_rol_con_metadata")
        expect_denied(c, "UPDATE public.solicitudes SET asunto='prohibido' WHERE id=%s", (request_id,))
        expect_denied(c, "UPDATE public.perfiles SET activo=true WHERE id=%s", (b,))
        expect_denied(c, "INSERT INTO public.usuario_roles(usuario_id,rol_id) "
                        "SELECT %s,id FROM public.roles WHERE codigo='ADMINISTRADOR'", (b,))
        assert_check(True, "RLS_escritura_directa_y_autoasignacion_roles_denegadas")
        c.execute("SET LOCAL ROLE anon")
        expect_denied(c, "SELECT * FROM public.solicitudes LIMIT 1")
        assert_check(True, "RLS_anon_sin_acceso")
    assert_check(c.execute("SELECT count(*) FROM public.solicitudes WHERE id=%s", (request_id,)).fetchone()[0] == 0,
                 "RLS_datos_temporales_revertidos")
    # Prueba del trigger con un usuario SQL exclusivamente transaccional; no manda correo.
    future_id = uuid4()
    with c.transaction(force_rollback=True):
        c.execute("INSERT INTO auth.users(id,email,raw_user_meta_data) VALUES (%s,%s,%s::jsonb)",
                  (future_id, "test-" + uuid4().hex + "@example.invalid",
                   json.dumps({"nombres": " " , "apellidos": "A" * 200, "role": "ADMINISTRADOR", "activo": True})))
        name, surname, active = c.execute("SELECT nombres,apellidos,activo FROM public.perfiles WHERE id=%s", (future_id,)).fetchone()
        assert_check(name == "Pendiente" and len(surname) == 150 and not active, "Trigger_perfil_pendiente_datos_validados")
        assert_check(c.execute("SELECT count(*) FROM public.usuario_roles WHERE usuario_id=%s", (future_id,)).fetchone()[0] == 0,
                     "Trigger_no_asigna_roles")
    assert_check(c.execute("SELECT count(*) FROM auth.users WHERE id=%s", (future_id,)).fetchone()[0] == 0,
                 "Trigger_usuario_temporal_revertido")
    assert_check(before == protected_fingerprint(c), "Cuentas_perfiles_roles_y_contrasenas_existentes_intactos")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Confirma la migración solo después de aprobar las pruebas")
    args = parser.parse_args()
    try:
        with DatabaseSettings.from_env().connect(autocommit=True) as c:
            before = protected_fingerprint(c)
            with c.transaction(force_rollback=not args.apply):
                c.execute(MIGRATION.read_text(encoding="utf-8"), prepare=False)
                validate(c)
            assert_check(before == protected_fingerprint(c), "Registros_originales_conservados")
            print("Migracion: " + ("APLICADA" if args.apply else "VALIDADA_CON_ROLLBACK"))
        return 0
    except psycopg.Error as error:
        print("ERROR:", database_error(error))
        return 1
    except (RuntimeError, ValueError) as error:
        print("ERROR:", str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
