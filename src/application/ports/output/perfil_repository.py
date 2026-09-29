from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.usuario_actual import UsuarioActual


class PerfilRepository(ABC):
    @abstractmethod
    def obtener_usuario(self, usuario_id: UUID, email: str | None) -> UsuarioActual | None:
        """Carga perfil y roles vigentes de una identidad verificada por el proveedor."""
