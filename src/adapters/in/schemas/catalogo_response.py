from uuid import UUID

from pydantic import JsonValue

from src.domain.value_objects.estados import TipoDato
from src.domain.value_objects.seccion_salida import secciones_efectivas
from .base import ResponseModel
from .seccion_response import SeccionSalidaResponse


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
    secciones_salida: list[SeccionSalidaResponse]
    estructura_legacy: bool
    formato_documento: str | None = None


def representar_plantilla(plantilla) -> PlantillaResponse:
    return PlantillaResponse(
        id=plantilla.id, nombre=plantilla.nombre, tipo_informe_id=plantilla.tipo_informe_id,
        area_id=plantilla.area_id, version=plantilla.version, activa=plantilla.activa,
        descripcion=plantilla.descripcion, secciones_salida=secciones_efectivas(plantilla.secciones_salida),
        estructura_legacy=plantilla.secciones_salida is None,
        formato_documento=plantilla.formato_documento,
    )


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
