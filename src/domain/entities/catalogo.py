from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TipoInforme:
    id: UUID
    codigo: str
    nombre: str
    activo: bool = True


@dataclass(frozen=True)
class AreaMunicipal:
    id: UUID
    codigo: str | None
    nombre: str
    activo: bool = True
    area_padre_id: UUID | None = None
    descripcion: str | None = None


@dataclass(frozen=True)
class Normativa:
    id: UUID
    codigo: str | None
    titulo: str
    tipo: str = "OTRO"
    activo: bool = True
