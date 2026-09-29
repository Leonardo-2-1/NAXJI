from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from src.domain.value_objects.estados import TipoDato


@dataclass
class CampoPlantilla:
    id: UUID
    plantilla_id: UUID
    clave: str
    etiqueta: str
    tipo_dato: TipoDato
    obligatorio: bool
    orden: int
    configuracion: dict[str, Any] = field(default_factory=dict)
    activo: bool = True


@dataclass
class Plantilla:
    id: UUID
    nombre: str
    tipo_informe_id: UUID
    area_id: UUID | None = None
    version: int = 1
    activa: bool = True
    campos: list[CampoPlantilla] = field(default_factory=list)
    descripcion: str | None = None
