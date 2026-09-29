"""Prueba real Auth -> FastAPI -> PostgreSQL y reinicio de proceso.

Lee contraseñas exclusivamente de .env.auth-test (ignorado por Git).
No muestra tokens, passwords, claves, UUID ni identificadores de sesión.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
import httpx
import psycopg

from src.infrastructure.configuration.database import DatabaseSettings, ROOT
from src.infrastructure.auth.supabase import SupabaseAuthSettings
from scripts.aplicar_seguridad_supabase import protected_fingerprint


class VerificationError(Exception):
    pass


def check(condition, label):
    if not condition:
        raise VerificationError(label + ": FALLÓ")
    print(label + ": OK", flush=True)


@contextmanager
def backend(port):
    env = {**os.environ, "NAXJI_PERSISTENCE_MODE": "postgres", "NAXJI_AUTH_MODE": "supabase",
           "NAXJI_AUTH_COOKIE_SECURE": "false", "PYTHONPATH": str(ROOT)}
    with (ROOT / "venv/run-logs/auth-test-backend.log").open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(port),
             "--log-level", "warning", "--no-access-log"], cwd=ROOT, env=env,
            stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            ready = False
            with httpx.Client(trust_env=False, timeout=1) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        break
                    try:
                        ready = client.get(f"http://127.0.0.1:{port}/health").status_code == 200
                        if ready:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.2)
            check(ready, "Backend_real_iniciado")
            yield process.pid
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def run_verification(browser_sessions=None):
    credentials = dotenv_values(ROOT / ".env.auth-test", interpolate=False, encoding="utf-8-sig")
    required = [f"NAXJI_TEST_{field}_{letter}" for letter in ("A", "B") for field in ("EMAIL", "PASSWORD")]
    if browser_sessions:
        credentials = {"NAXJI_TEST_EMAIL_A": "funcionario1.naxji@gmail.com",
                       "NAXJI_TEST_EMAIL_B": "funcionario2.naxji@gmail.com"}
    elif any(not credentials.get(name) for name in required):
        raise VerificationError("Falta configuración local en .env.auth-test; no se ejecutó autenticación real")
    auth_settings = SupabaseAuthSettings.from_env()
    db = DatabaseSettings.from_env()
    with db.connect() as c:
        baseline = protected_fingerprint(c)
        owners = [r[0] for r in c.execute("SELECT id FROM auth.users WHERE email=ANY(%s)",
                  ([credentials["NAXJI_TEST_EMAIL_A"], credentials["NAXJI_TEST_EMAIL_B"]],))]
    check(len(owners) == 2, "Dos_cuentas_existentes_distintas")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    marker = "TEST_AUTH_" + uuid4().hex
    csrf = {"X-NAXJI-Client": "web"}
    base = f"http://127.0.0.1:{port}"
    sessions, identities = {}, {}
    try:
        with httpx.Client(base_url=base, trust_env=False, timeout=30) as a, httpx.Client(base_url=base, trust_env=False, timeout=30) as b:
            with backend(port) as first_pid:
                for letter, client in (("A", a), ("B", b)):
                    if browser_sessions:
                        sessions[letter] = browser_sessions[letter]["access_token"]
                        client.cookies.set("naxji_refresh", browser_sessions[letter]["refresh_token"], domain="127.0.0.1", path="/")
                    else:
                        response = client.post("/auth/login", headers=csrf, json={
                            "email": credentials[f"NAXJI_TEST_EMAIL_{letter}"],
                            "password": credentials[f"NAXJI_TEST_PASSWORD_{letter}"],
                        })
                        check(response.status_code == 200, "Supabase_login_funcionario_" + letter)
                        sessions[letter] = response.json()["access_token"]
                    client.headers["Authorization"] = "Bearer " + sessions[letter]
                    me = client.get("/auth/me")
                    check(me.status_code == 200, "Auth_me_funcionario_" + letter)
                    identities[letter] = me.json()["id"]
                    with db.connect() as c:
                        row = c.execute("SELECT p.id::text,p.nombres,p.apellidos FROM public.perfiles p JOIN auth.users u ON u.id=p.id "
                                        "WHERE u.email=%s AND p.activo", (credentials[f"NAXJI_TEST_EMAIL_{letter}"],)).fetchone()
                    check(row == (me.json()["id"], me.json()["nombres"], me.json()["apellidos"])
                          and me.json()["roles"] == ["FUNCIONARIO"], "Perfil_y_rol_PostgreSQL_" + letter)
                result = a.post("/solicitudes", json={"asunto": marker + "_A"})
                check(result.status_code == 201, "FastAPI_creacion_solicitud_A")
                identifier = result.json()["id"]
                path = "/solicitudes/" + identifier
                with db.connect() as c:
                    row = c.execute("SELECT usuario_id::text,asunto FROM public.solicitudes WHERE id=%s", (identifier,)).fetchone()
                check(row == (identities["A"], marker + "_A"), "Persistencia_SQL_datos_y_propietario")
                check(a.get(path).status_code == 200, "A_recupera_solicitud")
                check(b.get(path).status_code == 403, "B_lectura_ajena_denegada_403")
                check(b.put(path, json={"asunto": "intento prohibido"}).status_code == 403, "B_modificacion_ajena_denegada_403")
                own = b.post("/solicitudes", json={"asunto": marker + "_B"})
                check(own.status_code == 201 and b.get("/solicitudes/" + own.json()["id"]).status_code == 200,
                      "B_puede_operar_solicitud_propia")
                check(b.post("/solicitudes", json={"asunto": marker, "usuario_id": identities["A"], "roles": ["ADMINISTRADOR"]}).status_code == 422,
                      "HTTP_identidad_y_roles_no_manipulables_422")
                check(b.put("/auth/me", json={"roles": ["ADMINISTRADOR"]}).status_code == 405, "HTTP_sin_autoasignacion_admin_405")
                check(a.put(path, json={"asunto": marker + "_EDITADA"}).status_code == 200, "A_actualiza_solicitud_propia")
                for bad in ("demo-admin", "invalid.jwt.signature"):
                    check(a.get("/auth/me", headers={"Authorization": "Bearer " + bad}).status_code == 401, "Token_no_verificado_rechazado_401")
                # JWT reales enviados al Data API: se aplica el rol authenticated de Supabase.
                with httpx.Client(timeout=20) as rest:
                    for letter, expected in (("A", 1), ("B", 0)):
                        result = rest.get(auth_settings.url + "/rest/v1/solicitudes", params={"id": "eq." + identifier, "select": "id"},
                                          headers={"apikey": auth_settings.publishable_key, "Authorization": "Bearer " + sessions[letter]})
                        check(result.status_code == 200 and len(result.json()) == expected, "RLS_Data_API_JWT_real_" + letter)
            with backend(port) as second_pid:
                check(first_pid != second_pid, "Backend_proceso_anterior_finalizado_y_reiniciado")
                result = a.get(path)
                check(result.status_code == 200 and result.json()["asunto"] == marker + "_EDITADA", "Persistencia_despues_reinicio")
                check(b.get(path).status_code == 403, "Aislamiento_conservado_despues_reinicio")
                refreshed = a.post("/auth/refresh", headers=csrf)
                check(refreshed.status_code == 200 and "refresh_token" not in refreshed.json(), "Renovacion_sesion_cookie_HttpOnly")
                a.headers["Authorization"] = "Bearer " + refreshed.json()["access_token"]
                check(a.get("/auth/me").status_code == 200, "Access_token_renovado_valido")
                check(a.post("/auth/logout", headers=csrf).status_code == 204, "Cierre_sesion_Supabase")
                check(a.post("/auth/refresh", headers=csrf).status_code == 401, "Sesion_cerrada_no_se_renueva")
                b.post("/auth/logout", headers=csrf)
    finally:
        with db.connect() as c:
            c.execute("DELETE FROM public.solicitudes WHERE usuario_id=ANY(%s::uuid[]) AND asunto LIKE %s", (owners, marker + "%"))
        with db.connect() as c:
            check(c.execute("SELECT count(*) FROM public.solicitudes WHERE asunto LIKE %s", (marker + "%",)).fetchone()[0] == 0,
                  "Solicitudes_temporales_eliminadas")
            check(baseline == protected_fingerprint(c), "Cuentas_perfiles_roles_y_contrasenas_conservados")
    print("AUTH_PERSISTENCIA_AISLAMIENTO: COMPROBADOS", flush=True)


if __name__ == "__main__":
    try:
        sessions = json.load(sys.stdin) if "--browser-sessions-stdin" in sys.argv else None
        run_verification(sessions)
    except (VerificationError, ValueError) as error:
        print(str(error))
        raise SystemExit(1)
    except (httpx.HTTPError, psycopg.Error):
        print("Fallo de conectividad durante la verificación; no se publican detalles privados")
        raise SystemExit(1)
