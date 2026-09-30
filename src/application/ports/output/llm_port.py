from abc import ABC, abstractmethod


class LLMPort(ABC):

    @abstractmethod
    def generar(self, prompt: str, *, sistema: str, esquema: dict) -> str:
        """
        Genera JSON sin streaming, con instrucciones de sistema y esquema de salida.
        Los fallos del proveedor se traducen a ErrorGeneracion sanitizado.
        """
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Nombre configurado del modelo utilizado, para el metadato de versión."""
        ...
