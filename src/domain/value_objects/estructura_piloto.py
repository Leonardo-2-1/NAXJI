"""Demostración técnica NAXJI; no es un formato oficial municipal."""
from .seccion_salida import SeccionSalida


def estructura_piloto():
    return [
        SeccionSalida("antecedentes", "Antecedentes", True),
        SeccionSalida("objetivo", "Objetivo del informe", True),
        SeccionSalida("analisis_tecnico", "Análisis técnico", True),
        SeccionSalida("conclusiones", "Conclusiones", True),
        SeccionSalida("recomendaciones", "Recomendaciones", False),
    ]
