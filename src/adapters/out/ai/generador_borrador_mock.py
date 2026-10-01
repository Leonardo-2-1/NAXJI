from src.application.ports.output.generador_borrador import (
    ContextoConfirmado, GeneradorBorrador, ResultadoBorrador,
)
from src.domain.entities.plantilla import Plantilla
from src.domain.value_objects.seccion_salida import secciones_efectivas


class GeneradorBorradorMock(GeneradorBorrador):
    def generar(self, asunto: str, plantilla: Plantilla, datos: dict,
                contexto: ContextoConfirmado, instrucciones: str) -> ResultadoBorrador:
        contenido = {}
        for seccion in secciones_efectivas(plantilla.secciones_salida):
            valor = datos.get(seccion.clave)
            if seccion.clave in {"desarrollo", "analisis_tecnico"}:
                valor = datos.get("detalle", valor)
            texto = valor if isinstance(valor, str) and valor.strip() else "Pendiente de verificación: no se aportaron hechos para esta sección."
            contenido[seccion.clave] = f"DEMOSTRACIÓN MOCK — {seccion.titulo}. {texto}"
        return ResultadoBorrador(contenido=contenido, modelo_ia="MOCK_GENERADOR_BORRADOR",
                                 prompt_version="secciones-v2")
