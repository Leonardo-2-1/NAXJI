from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.domain.entities.solicitud import ahora
from src.domain.value_objects.estados import EstadoInforme, OrigenVersion
from src.domain.value_objects.seccion_salida import SeccionSalida


@dataclass
class VersionInforme:
    informe_id: UUID
    numero_version: int
    contenido: dict[str, Any]
    origen: OrigenVersion
    creado_por: UUID | None
    id: UUID = field(default_factory=uuid4)
    modelo_ia: str | None = None
    prompt_version: str | None = None
    resumen_cambios: str | None = None
    created_at: datetime = field(default_factory=ahora)
    # Las versiones antiguas no tenían título propio; no se reconstruye su historia.
    titulo: str | None = None
    # Snapshot inmutable en cada versión. None identifica versiones anteriores al paso 3.
    secciones_salida: list[SeccionSalida] | None = None


@dataclass
class Informe:
    solicitud_id: UUID
    plantilla_id: UUID
    creado_por: UUID | None
    titulo: str | None = None
    id: UUID = field(default_factory=uuid4)
    estado: EstadoInforme = EstadoInforme.BORRADOR
    versiones: list[VersionInforme] = field(default_factory=list)
    created_at: datetime = field(default_factory=ahora)
    updated_at: datetime = field(default_factory=ahora)
