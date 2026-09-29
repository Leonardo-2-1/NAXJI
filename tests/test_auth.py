from dataclasses import replace
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
    auth = SupabaseAuth(SupabaseAuthSettings("https://project.supabase.co", "sb_publishable_test"),
                        httpx.MockTransport(transport))
    profiles = Mock()
    profiles.obtener_usuario.return_value = user
    container = SimpleNamespace(persistence_mode="postgres", perfiles=profiles)
    app = create_app(Settings(auth_mode="supabase", persistence_mode="postgres"), container, auth=auth)
    with TestClient(app, base_url="https://testserver") as client:
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
    headers = {"X-NAXJI-Client": "web", "Origin": "https://testserver"}
    response = client.post("/auth/login", headers=headers, json={"email": "test@example.invalid", "password": "test-private"})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    assert "refresh_token" not in response.json()
    assert "test-private" not in response.text
    assert client.post("/auth/refresh", headers=headers).status_code == 200
    response = client.post("/auth/logout", headers={**headers, "Authorization": "Bearer access-test"})
    assert response.status_code == 204
    assert not client.cookies.get("naxji_refresh")
    assert "/auth/v1/logout" in calls
    assert client.post("/auth/refresh", headers=headers).status_code == 401


@pytest.mark.parametrize("headers", [{}, {"X-NAXJI-Client": "web", "Origin": "https://attacker.invalid"}])
def test_cookie_endpoints_reject_csrf(auth_app, headers):
    client, _, _, calls = auth_app
    response = client.post("/auth/login", headers=headers, json={"email": "test@example.invalid", "password": "private"})
    assert response.status_code == 403
    assert calls == []


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
