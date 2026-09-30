from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
    codigo: str | None = None


RESPUESTAS_ERROR = {
    codigo: {"model": ErrorResponse, "description": descripcion}
    for codigo, descripcion in {
        400: "Datos de negocio inválidos", 401: "Usuario no autenticado",
        403: "Operación no autorizada", 404: "Recurso inexistente",
        409: "Conflicto de estado o versión", 500: "Error interno",
        502: "Respuesta inválida o fallo del generador", 503: "Servicio o modelo no disponible",
        504: "Tiempo máximo de generación agotado",
    }.items()
}
