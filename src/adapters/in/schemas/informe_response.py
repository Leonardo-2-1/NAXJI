from datetime import datetime
from uuid import UUID

from pydantic import JsonValue

from src.domain.entities.informe import Informe
from src.domain.value_objects.estados import EstadoInforme, OrigenVersion
from src.domain.value_objects.seccion_salida import secciones_efectivas
from .base import ResponseModel
from .seccion_response import SeccionSalidaResponse


class InformeResponse(ResponseModel):
    informe_id: UUID
    solicitud_id: UUID
    plantilla_id: UUID
    titulo: str | None
    estado: EstadoInforme
    version_id: UUID
    numero_version: int
    contenido: dict[str, JsonValue]
    secciones_salida: list[SeccionSalidaResponse]
    estructura_legacy: bool
    origen: OrigenVersion
    modelo_ia: str | None
    created_at: datetime
    updated_at: datetime


def representar_informe(informe: Informe) -> InformeResponse:
    version = max(informe.versiones, key=lambda v: v.numero_version)
    return InformeResponse(
        informe_id=informe.id, solicitud_id=informe.solicitud_id, plantilla_id=informe.plantilla_id,
        titulo=informe.titulo, estado=informe.estado, version_id=version.id,
        numero_version=version.numero_version, contenido=version.contenido,
        secciones_salida=secciones_efectivas(version.secciones_salida),
        estructura_legacy=version.secciones_salida is None,
        origen=version.origen, modelo_ia=version.modelo_ia,
        created_at=informe.created_at, updated_at=informe.updated_at,
    )
