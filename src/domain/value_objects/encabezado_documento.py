"""Datos administrativos aportados por personas; nunca se redactan con el LLM."""
from copy import deepcopy
from datetime import date
import re

from src.domain.services.errores import DatosInvalidos

MARCADOR = "[POR COMPLETAR]"
CAMPOS_OFICIALES = ("numero", "emisor", "destinatario", "fecha", "referencia", "firmante", "cargo_firmante")
FORMATO_MDT = "mdt_informe_anexo08_2019_revision1"
CAMPOS_MDT = ("cargo_destinatario", "lugar_emision", "registro_documento", "registro_expediente", "iniciales", "copias", "anexos")
UUID_TEXTO = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)


def texto_publico(valor):
    # Nunca convierte un UUID técnico o un objeto en el nombre de un funcionario.
    return valor.strip() if isinstance(valor, str) and not UUID_TEXTO.search(valor) else ""


def datos_oficiales(encabezado):
    h = encabezado if isinstance(encabezado, dict) else {}
    documento = h.get("documento")
    if not isinstance(documento, dict):
        documento = {"emisor": h.get("area_origen"), "destinatario": h.get("area_destino")}
    return {clave: texto_publico(documento.get(clave)) for clave in campos_oficiales(h)}


def campos_oficiales(encabezado):
    return CAMPOS_OFICIALES + (CAMPOS_MDT if encabezado.get("formato_documento") == FORMATO_MDT else ())


def crear_encabezado(asunto, plantilla, contexto, area_origen):
    encabezado = {"asunto": asunto, "area_origen": area_origen, "area_destino": contexto.area_destino_nombre,
            "tipo_documento": contexto.tipo_informe_nombre or "Informe",
            "plantilla_nombre": plantilla.nombre, "plantilla_version": plantilla.version,
            "documento": {**dict.fromkeys(CAMPOS_OFICIALES, ""),
                          "emisor": texto_publico(area_origen),
                          "destinatario": texto_publico(contexto.area_destino_nombre)}}
    formato = getattr(plantilla, "formato_documento", None)
    if formato:
        if formato != FORMATO_MDT:
            raise DatosInvalidos("El formato documental de la plantilla no está disponible")
        encabezado["formato_documento"] = formato
        # El catálogo identifica áreas, no acredita destinatario personal, cargo ni firma.
        encabezado["documento"] = dict.fromkeys(campos_oficiales(encabezado), "")
    return encabezado


def actualizar_datos_oficiales(encabezado, cambios):
    if not isinstance(cambios, dict) or cambios.keys() - set(campos_oficiales(encabezado or {})):
        raise DatosInvalidos("El encabezado contiene campos administrativos no permitidos")
    datos = datos_oficiales(encabezado)
    for clave, valor in cambios.items():
        if not isinstance(valor, str) or len(valor) > (2000 if clave in {"referencia", "anexos", "copias"} else 300):
            raise DatosInvalidos(f"El dato administrativo {clave} debe ser texto breve")
        if UUID_TEXTO.search(valor):
            raise DatosInvalidos("Use nombres o denominaciones en el encabezado, no UUID técnicos")
        datos[clave] = valor.strip()
    if datos["fecha"]:
        try:
            if date.fromisoformat(datos["fecha"]).isoformat() != datos["fecha"]:
                raise ValueError
        except ValueError:
            raise DatosInvalidos("La fecha del documento debe usar AAAA-MM-DD o quedar pendiente") from None
    nuevo = deepcopy(encabezado) if isinstance(encabezado, dict) else {}
    nuevo["documento"] = datos
    return nuevo
