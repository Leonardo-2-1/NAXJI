class ErrorDominio(Exception):
    """Error esperado y seguro para mostrar al cliente."""


class DatosInvalidos(ErrorDominio):
    pass


class NoAutorizado(ErrorDominio):
    pass


class NoEncontrado(ErrorDominio):
    pass


class ConflictoEstado(ErrorDominio):
    pass


class ErrorGeneracion(ErrorDominio):
    MENSAJES = {
        "GENERACION_FALLIDA": "No se pudo generar el borrador",
        "OLLAMA_NO_DISPONIBLE": "No se pudo conectar con Ollama. Verifique que el servicio local esté encendido y reintente.",
        "OLLAMA_MODELO_NO_INSTALADO": "El modelo configurado no está disponible en Ollama. Instálelo o revise NAXJI_OLLAMA_MODEL y reintente.",
        "OLLAMA_TIMEOUT": "Ollama superó el tiempo máximo de generación. Puede reintentar o ajustar NAXJI_OLLAMA_TIMEOUT_SECONDS.",
        "OLLAMA_RESPUESTA_INVALIDA": "Ollama devolvió un borrador inválido o incompleto. No se guardó; puede reintentar.",
        "OLLAMA_ERROR": "Ollama no pudo completar la generación. Revise el servicio local y reintente.",
    }

    def __init__(self, mensaje="No se pudo generar el borrador", *, codigo="GENERACION_FALLIDA"):
        # El detalle arbitrario nunca se utiliza en la respuesta HTTP.
        self.codigo = codigo if codigo in self.MENSAJES else "GENERACION_FALLIDA"
        self.mensaje_publico = self.MENSAJES[self.codigo]
        super().__init__(mensaje)
