from datetime import datetime
from uuid import UUID

from pydantic import JsonValue

from src.domain.entities.informe import Informe
from src.application.use_cases.exportar_informe import version_guardada
from src.domain.value_objects.estados import EstadoInforme, OrigenVersion
from src.domain.value_objects.seccion_salida import secciones_efectivas
from .base import ResponseModel
from .seccion_response import SeccionSalidaResponse


class InformeResponse(ResponseModel):
    informe_id: UUID
    solicitud_id: UUID
    plantilla_id: UUID
    titulo: str | None
    titulo_versionado: bool
    plantilla_nombre: str | None = None
    plantilla_version: int | None = None
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


def representar_informe(informe: Informe, numero_version: int | None = None) -> InformeResponse:
    version = (version_guardada(informe, numero_version) if numero_version is not None
               else max(informe.versiones, key=lambda v: v.numero_version))
    encabezado = version.contenido.get("encabezado", {})
    encabezado = encabezado if isinstance(encabezado, dict) else {}
    return InformeResponse(
        informe_id=informe.id, solicitud_id=informe.solicitud_id, plantilla_id=informe.plantilla_id,
        titulo=version.titulo if version.titulo is not None else informe.titulo,
        titulo_versionado=version.titulo is not None, estado=informe.estado, version_id=version.id,
        plantilla_nombre=encabezado.get("plantilla_nombre"), plantilla_version=encabezado.get("plantilla_version"),
        numero_version=version.numero_version, contenido=version.contenido,
        secciones_salida=secciones_efectivas(version.secciones_salida),
        estructura_legacy=version.secciones_salida is None,
        origen=version.origen, modelo_ia=version.modelo_ia,
        created_at=informe.created_at, updated_at=informe.updated_at,
    )
