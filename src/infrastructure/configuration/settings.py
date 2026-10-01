from dataclasses import dataclass
from math import isfinite
from urllib.parse import urlsplit
from src.infrastructure.configuration.database import environment


@dataclass(frozen=True)
class Settings:
    auth_mode: str = "mock"
    cors_origins: tuple[str, ...] = ()
    persistence_mode: str = "memory"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: float = 300.0

    def __post_init__(self):
        if any("*" in origin for origin in self.cors_origins):
            raise ValueError("NAXJI_CORS_ORIGINS requiere orígenes explícitos, sin comodines")
        try:
            url = urlsplit(self.ollama_base_url)
            valida = (url.scheme in {"http", "https"} and url.hostname and not url.username
                      and not url.password and not url.query and not url.fragment)
            _ = url.port
        except ValueError:
            valida = False
        if not valida:
            raise ValueError("NAXJI_OLLAMA_BASE_URL debe ser una URL HTTP(S) sin credenciales ni query")
        if not self.ollama_model.strip() or len(self.ollama_model) > 150 or any(c.isspace() for c in self.ollama_model):
            raise ValueError("NAXJI_OLLAMA_MODEL debe identificar un modelo de hasta 150 caracteres")
        if not isfinite(self.ollama_timeout_seconds) or not 1 <= self.ollama_timeout_seconds <= 1800:
            raise ValueError("NAXJI_OLLAMA_TIMEOUT_SECONDS debe estar entre 1 y 1800 segundos")

    @classmethod
    def from_env(cls):
        values = environment()
        persistence = values.get("NAXJI_PERSISTENCE_MODE", "memory")
        if persistence not in {"memory", "postgres"}:
            raise ValueError("NAXJI_PERSISTENCE_MODE debe ser memory o postgres")
        modo = values.get("NAXJI_AUTH_MODE", "mock" if persistence == "memory" else "disabled")
        if modo not in {"mock", "disabled", "supabase"}:
            raise ValueError("NAXJI_AUTH_MODE debe ser mock, disabled o supabase")
        if modo == "supabase" and persistence != "postgres":
            raise ValueError("Supabase Auth requiere persistencia postgres")
        origins = tuple(o.strip() for o in values.get("NAXJI_CORS_ORIGINS", "").split(",") if o.strip())
        try:
            timeout = float(values.get("NAXJI_OLLAMA_TIMEOUT_SECONDS", "300"))
        except (ValueError, TypeError):
            raise ValueError("NAXJI_OLLAMA_TIMEOUT_SECONDS debe ser un número") from None
        return cls(auth_mode=modo, cors_origins=origins, persistence_mode=persistence,
                   ollama_base_url=values.get("NAXJI_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
                   ollama_model=values.get("NAXJI_OLLAMA_MODEL", "qwen2.5:7b"),
                   ollama_timeout_seconds=timeout)
