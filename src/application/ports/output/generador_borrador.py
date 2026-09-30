from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.entities.plantilla import Plantilla


@dataclass(frozen=True)
class NormaConfirmada:
    id: UUID
    codigo: str | None
    titulo: str


@dataclass(frozen=True)
class ContextoConfirmado:
    tipo_informe_id: UUID
    area_destino_id: UUID
    normativa_ids: tuple[UUID, ...]
    tipo_informe_nombre: str | None = None
    area_destino_nombre: str | None = None
    normas: tuple[NormaConfirmada, ...] = ()


@dataclass(frozen=True)
class ResultadoBorrador:
    contenido: dict[str, Any]
    modelo_ia: str
    prompt_version: str | None = None


class GeneradorBorrador(ABC):
    @abstractmethod
    def generar(
        self, asunto: str, plantilla: Plantilla, datos: dict[str, Any],
        contexto: ContextoConfirmado, instrucciones: str,
    ) -> ResultadoBorrador:
        """Devuelve {clave_seccion: texto} conforme a plantilla.secciones_salida.

        La aplicación entrega la estructura efectiva, ordenada y no vacía. Las
        obligatorias deben ser texto no vacío; las opcionales pueden omitirse.
        No devuelve encabezado ni metadatos: los incorpora la aplicación.
        Ante fallos del proveedor lanza ErrorGeneracion.
        """
        ...
