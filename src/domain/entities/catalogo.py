from dataclasses import dataclass
from datetime import date
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
    numero: str | None = None
    fecha_publicacion: date | None = None
    fecha_inicio_vigencia: date | None = None
    fecha_fin_vigencia: date | None = None
    url_fuente: str | None = None
    descripcion: str | None = None
