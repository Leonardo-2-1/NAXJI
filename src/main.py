import importlib
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.domain.services.errores import (
    ConflictoEstado, DatosInvalidos, ErrorDominio, ErrorGeneracion, NoAutorizado, NoEncontrado,
)
from src.infrastructure.auth.mock import usuarios_demo
from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from src.adapters.out.persistence.postgres import PersistenceError
from src.infrastructure.auth.supabase import SupabaseAuth, SupabaseAuthSettings, AuthError


logger = logging.getLogger(__name__)


def health():
    return {"status": "ok", "service": "NAXJI API"}


def create_app(settings: Settings | None = None, container: Container | None = None, *, auth=None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="NAXJI API", version="1.0.0",
        description=(f"Backend PMV1. Persistencia configurada: {settings.persistence_mode}. "
                     "Predicción RF-IA-01 y generación estructurada con Ollama local. "
                     "Los tokens demo solo están habilitados en memoria. PostgreSQL usa Supabase Auth."),
    )
    app.state.settings = settings
    app.state.container = container or Container(settings)
    if app.state.container.persistence_mode != settings.persistence_mode:
        raise ValueError("El contenedor no coincide con el modo de persistencia configurado")
    app.state.usuarios_demo = usuarios_demo() if settings.auth_mode == "mock" else {}
    if settings.auth_mode == "supabase":
        if settings.persistence_mode != "postgres":
            raise ValueError("Supabase Auth requiere persistencia postgres")
        app.state.auth = auth or SupabaseAuth(SupabaseAuthSettings.from_env())
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                           allow_methods=["GET", "POST", "PUT"],
                           allow_headers=["Authorization", "Content-Type", "X-NAXJI-Client"],
                           allow_credentials=True)

    @app.exception_handler(AuthError)
    async def error_auth(request: Request, error: AuthError):
        headers = {"Cache-Control": "no-store"}
        if error.status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        response = JSONResponse(status_code=error.status, content={"detail": error.detail}, headers=headers)
        if request.url.path == "/auth/refresh" and error.status in (401, 403):
            response.delete_cookie("naxji_refresh", path="/")
        return response

    @app.exception_handler(RequestValidationError)
    async def error_validacion(request: Request, error: RequestValidationError):
        # Pydantic puede incluir el cuerpo original en input: nunca reflejar passwords.
        details = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in error.errors()]
        return JSONResponse(status_code=422, content={"detail": details})

    @app.middleware("http")
    async def auth_no_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(PersistenceError)
    async def error_persistencia(request: Request, error: PersistenceError):
        logger.error("Persistencia no disponible en %s: %s", request.url.path, error)
        return JSONResponse(status_code=503, content={"detail": "Persistencia PostgreSQL no disponible"})

    @app.exception_handler(ErrorDominio)
    async def error_dominio(request: Request, error: ErrorDominio):
        if isinstance(error, ErrorGeneracion):
            codigo = {"OLLAMA_NO_DISPONIBLE": 503, "OLLAMA_MODELO_NO_INSTALADO": 503,
                      "OLLAMA_TIMEOUT": 504, "OLLAMA_RESPUESTA_INVALIDA": 502,
                      "OLLAMA_ERROR": 502}.get(error.codigo, 500)
            return JSONResponse(status_code=codigo,
                                content={"detail": error.mensaje_publico, "codigo": error.codigo})
        codigo = {DatosInvalidos: 400, NoAutorizado: 403, NoEncontrado: 404,
                  ConflictoEstado: 409, ErrorGeneracion: 500}.get(type(error), 400)
        return JSONResponse(status_code=codigo, content={"detail": str(error)})

    @app.exception_handler(Exception)
    async def error_no_controlado(request: Request, error: Exception):
        # Única frontera global: registra el fallo sin exponer detalles internos por HTTP.
        logger.error("Error no controlado en %s", request.url.path,
                     exc_info=(type(error), error, error.__traceback__))
        return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

    for nombre in ("solicitud", "catalogo", "ia", "informe", "usuario", "auth"):
        modulo = importlib.import_module(f"src.adapters.in.controllers.{nombre}_controller")
        app.include_router(modulo.router)
    app.add_api_route("/health", health, methods=["GET"], tags=["Estado"])
    return app


app = create_app()
