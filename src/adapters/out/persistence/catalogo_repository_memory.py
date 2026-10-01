from copy import deepcopy
from uuid import UUID

from src.adapters.out.persistence.datos_demo import (
    AREAS,
    NORMATIVAS,
    TIPOS,
)
from src.application.ports.output.catalogo_repository import (
    CatalogoRepository,
)


class CatalogoRepositoryMemory(
    CatalogoRepository
):

    def __init__(self, *, normativas=None, correspondencias=()):
        self.normativas = deepcopy(NORMATIVAS if normativas is None else normativas)
        self.correspondencias = deepcopy(list(correspondencias))

    def tipos_informe(self):
        return deepcopy(TIPOS)

    def areas(self):
        return deepcopy(AREAS)

    def normativa(
        self,
        normativa_id: UUID
    ):
        normativa = next(
            (
                n
                for n in self.normativas
                if n.id == normativa_id
            ),
            None
        )

        return deepcopy(normativa)

    def correspondencias_normativas(self, etiquetas):
        return deepcopy([c for c in self.correspondencias if c.etiqueta in etiquetas])
