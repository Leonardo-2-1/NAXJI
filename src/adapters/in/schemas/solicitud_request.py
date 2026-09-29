from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from src.domain.value_objects.estado_solicitud import EstadoSolicitud
from .base import RequestModel, Texto


class SolicitudRequest(RequestModel):
    asunto: Texto
    tipo_informe_id: UUID | None = None
    plantilla_id: UUID | None = None
    area_origen_id: UUID | None = None
    area_destino_id: UUID | None = None


class ActualizarSolicitudRequest(RequestModel):
    asunto: Texto | None = None
    tipo_informe_id: UUID | None = None
    plantilla_id: UUID | None = None
    area_origen_id: UUID | None = None
    area_destino_id: UUID | None = None
    estado: EstadoSolicitud | None = None

    @model_validator(mode="after")
    def validar_cambios(self):
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un campo")
        for campo in ("asunto", "estado"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser null")
        return self


class ValorRequest(RequestModel):
    campo_plantilla_id: UUID
    valor: JsonValue


class ValoresSolicitudRequest(RequestModel):
    valores: list[ValorRequest] = Field(max_length=200)

    @model_validator(mode="after")
    def sin_duplicados(self):
        ids = [v.campo_plantilla_id for v in self.valores]
        if len(ids) != len(set(ids)):
            raise ValueError("No repita campos de plantilla")
        return self


class SolicitudCompletaRequest(SolicitudRequest, ValoresSolicitudRequest):
    """Extensión explícita: datos y valores se validan/guardan en una transacción."""
    tipo_informe_id: UUID
    plantilla_id: UUID
    area_destino_id: UUID
