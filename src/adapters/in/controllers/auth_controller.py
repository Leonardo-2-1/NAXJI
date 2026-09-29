"""Sesiones Supabase: access token en respuesta, refresh token solo en cookie HttpOnly."""
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field, SecretStr

from src.infrastructure.auth.supabase import AuthError
from ..schemas.base import RequestModel


router = APIRouter(prefix="/auth", tags=["Autenticación"])
COOKIE = "naxji_refresh"


class LoginRequest(RequestModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: SecretStr = Field(min_length=1, max_length=1024)


def provider(request):
    if request.app.state.settings.auth_mode != "supabase":
        raise HTTPException(400, "Inicio de sesión real no habilitado")
    return request.app.state.auth


def check_origin(request):
    # Header no simple: evita formularios CSRF. CORS debe aprobar el preflight.
    if request.headers.get("X-NAXJI-Client") != "web":
        raise HTTPException(403, "Origen de la petición no autorizado")
    origin = request.headers.get("origin")
    own_origin = str(request.base_url).rstrip("/")
    if origin and origin not in (*provider(request).settings.allowed_origins, own_origin):
        raise HTTPException(403, "Origen de la petición no autorizado")
    if request.headers.get("sec-fetch-site") == "cross-site" and not origin:
        raise HTTPException(403, "Origen de la petición no autorizado")


def session_response(request, response, session):
    auth = provider(request)
    try:
        access = session["access_token"]
        refresh = session["refresh_token"]
        expires = int(session["expires_in"])
        if not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh or expires <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise AuthError(503, "Respuesta de autenticación no válida") from None
    # No confiar en user_metadata ni roles incluidos en un payload del navegador.
    user_id, email = auth.verificar(access)
    usuario = request.app.state.container.perfiles.obtener_usuario(user_id, email)
    if usuario is None or not usuario.activo or not usuario.roles:
        try:
            auth.logout(access)
        except AuthError:
            pass
        raise AuthError(403, "Perfil inactivo, inexistente o sin permisos asignados")
    response.set_cookie(COOKIE, refresh, httponly=True, secure=auth.settings.cookie_secure,
                        samesite="strict", max_age=30 * 24 * 3600, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": access, "token_type": "bearer", "expires_in": expires}


@router.get("/config")
def config(request: Request):
    return {"mode": request.app.state.settings.auth_mode,
            "persistence": request.app.state.settings.persistence_mode}


@router.post("/login")
def login(datos: LoginRequest, request: Request, response: Response):
    check_origin(request)
    session = provider(request).login(datos.email, datos.password.get_secret_value())
    return session_response(request, response, session)


@router.post("/refresh")
def refresh(request: Request, response: Response):
    check_origin(request)
    session = provider(request).refresh(request.cookies.get(COOKIE))
    return session_response(request, response, session)


@router.post("/logout", status_code=204)
def logout(request: Request):
    check_origin(request)
    auth = provider(request)
    header = request.headers.get("authorization", "")
    access = header[7:] if header.lower().startswith("bearer ") else None
    try:
        if not access and request.cookies.get(COOKIE):
            access = auth.refresh(request.cookies[COOKIE]).get("access_token")
        if access:
            auth.logout(access)
    except AuthError as error:
        # Credenciales caducadas ya no permiten renovar; fallos de red sí se informan.
        if error.status not in (401, 403):
            raise
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=auth.settings.cookie_secure, samesite="strict")
    return response
