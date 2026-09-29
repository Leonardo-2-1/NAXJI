from dataclasses import dataclass
from uuid import UUID

from src.domain.value_objects.estados import Rol


@dataclass(frozen=True)
class UsuarioActual:
    id: UUID
    roles: frozenset[Rol]
    area_id: UUID | None = None
    activo: bool = True
    email: str | None = None
    nombres: str | None = None
    apellidos: str | None = None
    cargo: str | None = None
    area_nombre: str | None = None
