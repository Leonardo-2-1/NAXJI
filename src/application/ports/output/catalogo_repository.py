from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.catalogo import AreaMunicipal, Normativa, TipoInforme
from src.domain.entities.correspondencia_normativa import CorrespondenciaNormativa


class CatalogoRepository(ABC):
    @abstractmethod
    def tipos_informe(self) -> list[TipoInforme]: ...

    @abstractmethod
    def areas(self) -> list[AreaMunicipal]: ...

    @abstractmethod
    def normativa(self, normativa_id: UUID) -> Normativa | None: ...

    def correspondencias_normativas(self, etiquetas: list[str]) -> list[CorrespondenciaNormativa]:
        """Solo relaciones explícitas; vacío significa curación pendiente, nunca inferir por código."""
        return []
