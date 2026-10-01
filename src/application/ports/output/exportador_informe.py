from abc import ABC, abstractmethod

from src.domain.entities.informe import Informe, VersionInforme


class ExportadorInforme(ABC):
    @abstractmethod
    def exportar(self, informe: Informe, version: VersionInforme) -> bytes:
        """Representa una versión guardada, sin inferencia ni escrituras."""
        ...
