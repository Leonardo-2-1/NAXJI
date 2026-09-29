from uuid import UUID

from pydantic import JsonValue

from src.domain.value_objects.estados import TipoDato
from .base import ResponseModel


class CatalogoResponse(ResponseModel):
    id: UUID
    codigo: str | None
    nombre: str
    activo: bool


class PlantillaResponse(ResponseModel):
    id: UUID
    nombre: str
    tipo_informe_id: UUID
    area_id: UUID | None
    version: int
    activa: bool
    descripcion: str | None = None


class AreaResponse(CatalogoResponse):
    area_padre_id: UUID | None = None
    descripcion: str | None = None


class CampoResponse(ResponseModel):
    id: UUID
    plantilla_id: UUID
    clave: str
    etiqueta: str
    tipo_dato: TipoDato
    obligatorio: bool
    orden: int
    configuracion: dict[str, JsonValue]
    activo: bool
