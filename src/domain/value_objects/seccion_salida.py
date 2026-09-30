"""Estructura de documento; independiente de los campos del formulario."""
from dataclasses import asdict, dataclass
import re

from src.domain.services.errores import DatosInvalidos


CLAVES_TECNICAS = frozenset({"encabezado", "datos", "contexto", "plantilla", "instrucciones"})


@dataclass(frozen=True)
class SeccionSalida:
    clave: str
    titulo: str
    obligatoria: bool

    def __post_init__(self):
        if (not isinstance(self.clave, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", self.clave)
                or self.clave in CLAVES_TECNICAS):
            raise DatosInvalidos("Clave de sección inválida o reservada")
        if not isinstance(self.titulo, str) or not self.titulo.strip() or len(self.titulo) > 150:
            raise DatosInvalidos("La sección requiere un título de hasta 150 caracteres")
        if type(self.obligatoria) is not bool:
            raise DatosInvalidos("obligatoria debe ser un booleano")


def estructura_legacy() -> list[SeccionSalida]:
    """Contrato anterior, no un formato institucional nuevo."""
    return [SeccionSalida("antecedentes", "Antecedentes", True),
            SeccionSalida("desarrollo", "Desarrollo", True),
            SeccionSalida("conclusiones", "Conclusiones", True)]


def secciones_efectivas(secciones: list[SeccionSalida] | None) -> list[SeccionSalida]:
    if secciones is None:
        return estructura_legacy()
    if not isinstance(secciones, list) or not secciones or len(secciones) > 100:
        raise DatosInvalidos("La estructura debe contener entre 1 y 100 secciones")
    if any(not isinstance(s, SeccionSalida) for s in secciones):
        raise DatosInvalidos("Definición de sección inválida")
    if len({s.clave for s in secciones}) != len(secciones):
        raise DatosInvalidos("No se permiten claves de sección duplicadas")
    return list(secciones)


def secciones_desde_json(valor) -> list[SeccionSalida] | None:
    if valor is None:
        return None
    if not isinstance(valor, list):
        raise DatosInvalidos("La estructura debe ser una lista")
    try:
        secciones = [SeccionSalida(**s) for s in valor]
    except TypeError as error:
        raise DatosInvalidos("Definición JSON de secciones inválida") from error
    return secciones_efectivas(secciones)


def secciones_a_json(secciones: list[SeccionSalida] | None):
    return None if secciones is None else [asdict(s) for s in secciones_efectivas(secciones)]
