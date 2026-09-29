from dataclasses import dataclass
from src.infrastructure.configuration.database import environment


@dataclass(frozen=True)
class Settings:
    auth_mode: str = "mock"
    cors_origins: tuple[str, ...] = ()
    persistence_mode: str = "memory"

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
        return cls(auth_mode=modo, cors_origins=origins, persistence_mode=persistence)
