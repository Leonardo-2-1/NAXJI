"""Supabase Auth REST: la identidad siempre se valida contra /auth/v1/user.

No decodifica un JWT del usuario para confiar en sus claims ni almacena contraseñas.
Compatible con claves de firma simétricas y asimétricas del proyecto.
"""
import base64
from dataclasses import dataclass, field
import json
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from src.infrastructure.configuration.database import environment


class AuthError(Exception):
    def __init__(self, status=401, detail="Credenciales o sesión no válidas"):
        self.status, self.detail = status, detail
        super().__init__(detail)


@dataclass(frozen=True)
class SupabaseAuthSettings:
    url: str
    publishable_key: str = field(repr=False)
    cookie_secure: bool = True
    allowed_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")

    @classmethod
    def from_env(cls):
        values = environment()
        url = (values.get("NAXJI_SUPABASE_URL") or "").rstrip("/")
        key = values.get("NAXJI_SUPABASE_PUBLISHABLE_KEY") or ""
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.path or parts.query or parts.fragment:
            raise ValueError("NAXJI_SUPABASE_URL debe ser la URL HTTPS del proyecto")
        if not key.startswith("sb_publishable_"):
            # Solo clasifica la clave de configuración legacy, NO verifica JWT de usuarios.
            try:
                payload = key.split(".")[1]
                role = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("role")
            except (ValueError, IndexError, TypeError):
                role = None
            if role != "anon":
                raise ValueError("Configure una clave publicable o anon; no use service_role ni claves secretas")
        secure = values.get("NAXJI_AUTH_COOKIE_SECURE", "true").lower()
        if secure not in {"true", "false"}:
            raise ValueError("NAXJI_AUTH_COOKIE_SECURE debe ser true o false")
        origins = tuple(o.strip().rstrip("/") for o in values.get(
            "NAXJI_AUTH_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
        ).split(",") if o.strip())
        if "*" in origins:
            raise ValueError("Los orígenes de autenticación deben ser explícitos")
        return cls(url, key, secure == "true", origins)


class SupabaseAuth:
    def __init__(self, settings, transport=None):
        self.settings, self.transport = settings, transport

    def _request(self, method, path, *, token=None, body=None, params=None):
        headers = {"apikey": self.settings.publishable_key}
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            with httpx.Client(timeout=15, follow_redirects=False, transport=self.transport) as client:
                response = client.request(method, self.settings.url + "/auth/v1" + path,
                                          headers=headers, json=body, params=params)
        except httpx.HTTPError:
            raise AuthError(503, "Servicio de autenticación no disponible") from None
        if response.status_code == 429:
            raise AuthError(429, "Demasiados intentos; vuelva a intentarlo más tarde")
        if response.status_code >= 500 or 300 <= response.status_code < 400:
            raise AuthError(503, "Servicio de autenticación no disponible")
        if not response.is_success:
            raise AuthError()
        if response.status_code == 204:
            return {}
        try:
            return response.json()
        except ValueError:
            raise AuthError(503, "Respuesta de autenticación no válida") from None

    def verificar(self, token):
        if not token or token.startswith("demo-") or len(token) > 16384:
            raise AuthError()
        data = self._request("GET", "/user", token=token)
        try:
            user_id = UUID(data["id"])
            email = data.get("email")
            if email is not None and not isinstance(email, str):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise AuthError(503, "Respuesta de autenticación no válida") from None
        return user_id, email

    def login(self, email, password):
        return self._request("POST", "/token", params={"grant_type": "password"},
                             body={"email": email, "password": password})

    def refresh(self, token):
        if not token or len(token) > 16384:
            raise AuthError()
        return self._request("POST", "/token", params={"grant_type": "refresh_token"},
                             body={"refresh_token": token})

    def logout(self, token):
        self._request("POST", "/logout", token=token, params={"scope": "local"})
