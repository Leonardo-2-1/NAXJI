from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from src.domain.value_objects.estados import TipoDato
from src.domain.value_objects.seccion_salida import SeccionSalida


@dataclass
class CampoPlantilla:
    """Dato de entrada que completa el funcionario; no define una sección de salida."""
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
    # El orden de la lista es el orden del documento. None conserva el contrato anterior.
    secciones_salida: list[SeccionSalida] | None = None
    # None conserva la exportación piloto anterior. Se copia al encabezado de cada versión.
    formato_documento: str | None = None
