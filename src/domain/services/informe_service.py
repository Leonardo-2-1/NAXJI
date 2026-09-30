import json

from src.domain.services.errores import DatosInvalidos
from src.domain.value_objects.seccion_salida import SeccionSalida, secciones_efectivas


def validar_contenido(contenido: dict, secciones: list[SeccionSalida] | None = None) -> None:
    if not isinstance(contenido, dict):
        raise DatosInvalidos("El contenido debe ser un objeto JSON")
    for seccion in secciones_efectivas(secciones):
        texto = contenido.get(seccion.clave)
        if seccion.obligatoria and (not isinstance(texto, str) or not texto.strip()):
            raise DatosInvalidos(f"La sección {seccion.titulo} ({seccion.clave}) es obligatoria")
        if seccion.clave in contenido and not isinstance(texto, str):
            raise DatosInvalidos(f"La sección {seccion.titulo} debe contener texto")
    try:
        json.dumps(contenido, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise DatosInvalidos("El contenido debe ser JSON válido") from error
