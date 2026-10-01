from dataclasses import replace
from http.cookies import SimpleCookie
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.infrastructure.auth.supabase import SupabaseAuth, SupabaseAuthSettings, AuthError
from src.infrastructure.configuration.settings import Settings
from src.main import create_app


FRONTEND_ORIGIN = "https://naxji.pages.dev"
BACKEND_ORIGIN = "https://naxji-production.up.railway.app"
CROSS_SITE_HEADERS = {"X-NAXJI-Client": "web", "Origin": FRONTEND_ORIGIN,
                      "Sec-Fetch-Site": "cross-site"}


@pytest.fixture
def auth_app():
    user = UsuarioActual(uuid4(), frozenset({Rol.FUNCIONARIO}), email="test@example.invalid",
                         nombres="Prueba", apellidos="Local")
    calls = []
    def transport(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/user"):
            if request.headers.get("authorization") != "Bearer access-test":
                return httpx.Response(401, json={"msg": "private upstream"})
            return httpx.Response(200, json={"id": str(user.id), "email": user.email,
                                             "user_metadata": {"role": "ADMINISTRADOR"}})
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "access-test", "refresh_token": "refresh-private",
                                             "expires_in": 3600})
        return httpx.Response(204)
    auth = SupabaseAuth(SupabaseAuthSettings("https://project.supabase.co", "sb_publishable_test",
                                           allowed_origins=(FRONTEND_ORIGIN,)),
                        httpx.MockTransport(transport))
    profiles = Mock()
    profiles.obtener_usuario.return_value = user
    container = SimpleNamespace(persistence_mode="postgres", perfiles=profiles)
    app = create_app(Settings(auth_mode="supabase", persistence_mode="postgres",
                              cors_origins=(FRONTEND_ORIGIN,)), container, auth=auth)
    with TestClient(app, base_url=BACKEND_ORIGIN) as client:
        yield client, profiles, user, calls


def test_verified_identity_uses_database_roles_not_metadata(auth_app):
    client, profiles, user, calls = auth_app
    response = client.get("/auth/me", headers={"Authorization": "Bearer access-test"})
    assert response.status_code == 200
    assert response.json()["roles"] == ["FUNCIONARIO"]
    assert response.json()["nombres"] == "Prueba"
    assert response.headers["cache-control"] == "no-store"
    profiles.obtener_usuario.assert_called_once_with(user.id, user.email)
    assert calls == ["/auth/v1/user"]


@pytest.mark.parametrize("token", [None, "demo-admin", "forged", "expired"])
def test_unverified_token_never_reaches_profile(auth_app, token):
    client, profiles, _, _ = auth_app
    response = client.get("/auth/me", headers={"Authorization": "Bearer " + token} if token else {})
    assert response.status_code == 401
    assert "private upstream" not in response.text
    profiles.obtener_usuario.assert_not_called()


@pytest.mark.parametrize("state", ["missing", "inactive", "no-roles"])
def test_missing_inactive_or_roleless_profile_denied(auth_app, state):
    client, profiles, user, _ = auth_app
    profiles.obtener_usuario.return_value = {"missing": None, "inactive": replace(user, activo=False),
                                            "no-roles": replace(user, roles=frozenset())}[state]
    response = client.get("/auth/me", headers={"Authorization": "Bearer access-test"})
    assert response.status_code == 403


def test_login_refresh_logout_cookie_and_no_secret_reflection(auth_app):
    client, _, _, calls = auth_app
    headers = CROSS_SITE_HEADERS
    response = client.post("/auth/login", headers=headers, json={"email": "test@example.invalid", "password": "test-private"})
    assert response.status_code == 200
    assert_session_cookie(response)
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "refresh_token" not in response.json()
    assert "test-private" not in response.text
    renewed = client.post("/auth/refresh", headers=headers)
    assert renewed.status_code == 200
    assert_session_cookie(renewed)
    response = client.post("/auth/logout", headers={**headers, "Authorization": "Bearer access-test"})
    assert response.status_code == 204
    assert_session_cookie(response, deleted=True)
    assert not client.cookies.get("naxji_refresh")
    assert "/auth/v1/logout" in calls
    expired = client.post("/auth/refresh", headers=headers)
    assert expired.status_code == 401
    assert_session_cookie(expired, deleted=True)


def assert_session_cookie(response, *, deleted=False):
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    refresh = cookie["naxji_refresh"]
    assert refresh["samesite"].lower() == "none"
    assert refresh["secure"] is True
    assert refresh["httponly"] is True
    assert refresh["path"] == "/"
    assert not refresh["domain"]  # Host-only: no compartir con otros proyectos Railway.
    assert refresh["max-age"] == ("0" if deleted else str(30 * 24 * 3600))
    if deleted:
        assert refresh.value == ""


@pytest.mark.parametrize("endpoint", ["login", "refresh", "logout"])
@pytest.mark.parametrize("headers", [
    {},
    {"Origin": FRONTEND_ORIGIN},
    {**CROSS_SITE_HEADERS, "X-NAXJI-Client": "wrong"},
    {"X-NAXJI-Client": "web", "Sec-Fetch-Site": "cross-site"},
    {**CROSS_SITE_HEADERS, "Origin": "https://attacker.invalid"},
    {**CROSS_SITE_HEADERS, "Origin": "https://naxji.pages.dev.attacker.invalid"},
    {**CROSS_SITE_HEADERS, "Origin": "null"},
])
def test_cookie_endpoints_reject_csrf(auth_app, endpoint, headers):
    client, _, _, calls = auth_app
    response = client.post(f"/auth/{endpoint}", headers=headers,
                           json={"email": "test@example.invalid", "password": "private"} if endpoint == "login" else None)
    assert response.status_code == 403
    assert calls == []
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("origin,expected", [(FRONTEND_ORIGIN, 200), ("https://attacker.invalid", 400)])
def test_cross_site_preflight_only_allows_explicit_frontend(auth_app, origin, expected):
    client, _, _, calls = auth_app
    response = client.options("/auth/login", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-naxji-client,authorization",
    })
    assert response.status_code == expected
    assert response.headers["access-control-allow-credentials"] == "true"
    if expected == 200:
        assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
        assert "x-naxji-client" in response.headers["access-control-allow-headers"].lower()
    else:
        assert "access-control-allow-origin" not in response.headers
    assert calls == []


def test_refresh_for_inactive_profile_deletes_secure_cookie(auth_app):
    client, profiles, user, _ = auth_app
    login = client.post("/auth/login", headers=CROSS_SITE_HEADERS,
                        json={"email": "test@example.invalid", "password": "test-private"})
    assert login.status_code == 200
    profiles.obtener_usuario.return_value = replace(user, activo=False)
    response = client.post("/auth/refresh", headers=CROSS_SITE_HEADERS)
    assert response.status_code == 403
    assert_session_cookie(response, deleted=True)
    assert not client.cookies.get("naxji_refresh")


def test_cross_site_auth_rejects_insecure_cookie_configuration(monkeypatch):
    monkeypatch.setattr("src.infrastructure.auth.supabase.environment", lambda: {
        "NAXJI_SUPABASE_URL": "https://project.supabase.co",
        "NAXJI_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test",
        "NAXJI_AUTH_COOKIE_SECURE": "false",
    })
    with pytest.raises(ValueError, match="SameSite=None requiere Secure"):
        SupabaseAuthSettings.from_env()


@pytest.mark.parametrize("origin", ["*", "https://*.pages.dev"])
def test_auth_and_cors_reject_wildcard_origins(origin):
    with pytest.raises(ValueError, match="explícitos"):
        SupabaseAuthSettings("https://project.supabase.co", "sb_publishable_test",
                             allowed_origins=(origin,))
    with pytest.raises(ValueError, match="explícitos"):
        Settings(cors_origins=(origin,))


def test_http_cannot_assign_admin_or_reflect_password(auth_app):
    client, _, _, calls = auth_app
    response = client.post("/auth/login", headers={"X-NAXJI-Client": "web"},
                           json={"email": "test@example.invalid", "password": "private", "roles": ["ADMINISTRADOR"]})
    assert response.status_code == 422
    assert "private" not in response.text
    assert calls == []


def test_auth_outage_is_503_without_upstream_details():
    auth = SupabaseAuth(SupabaseAuthSettings("https://project.supabase.co", "sb_publishable_test"),
                        httpx.MockTransport(lambda request: httpx.Response(500, json={"error": "private"})))
    with pytest.raises(AuthError) as error:
        auth.verificar("access-test")
    assert error.value.status == 503
    assert "private" not in error.value.detail
