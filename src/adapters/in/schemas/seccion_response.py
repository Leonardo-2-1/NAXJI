from .base import ResponseModel


class SeccionSalidaResponse(ResponseModel):
    clave: str
    titulo: str
    obligatoria: bool
