"""Datos fuente de la versión 2 del piloto; no son secciones del documento."""
from uuid import NAMESPACE_URL, uuid5

from src.domain.entities.plantilla import CampoPlantilla
from src.domain.value_objects.estados import TipoDato


ESTADOS_RESULTADOS = [
    "Sin resultados de inspección",
    "Información parcial por verificar",
    "Resultados documentados disponibles",
]


def campos_fuente_piloto(plantilla_id):
    definiciones = [
        ("estado_resultados", "Información disponible", TipoDato.SELECT, True,
         {"opciones": ESTADOS_RESULTADOS,
          "ayuda": "Indique si existen resultados. Elegir una opción no acredita hechos ni sustituye sus fuentes."}),
        ("lugar_referencia", "Lugar de referencia conocido", TipoDato.TEXT, False,
         {"ayuda": "Opcional. Identifique el lugar solo si lo conoce; no implica que haya sido inspeccionado."}),
        ("fecha_referencia", "Fecha de referencia conocida", TipoDato.DATE, False,
         {"ayuda": "Opcional. Fecha del hecho o documento aportado; no supone una inspección realizada."}),
        ("hechos_conocidos", "Hechos y resultados conocidos", TipoDato.TEXTAREA, False,
         {"rol_fuente": "hechos", "ayuda": "Opcional. Describa solo hechos aportados, su origen y qué falta comprobar. Si no hay resultados, déjelo vacío o indíquelo expresamente."}),
        ("referencias_conocidas", "Documentos y referencias conocidos", TipoDato.TEXTAREA, False,
         {"rol_fuente": "referencias", "ayuda": "Opcional. Identifique documentos, enlaces o extractos disponibles. Un número o enlace no acredita su contenido, vigencia ni aplicabilidad."}),
        ("informacion_pendiente", "Información pendiente de obtener o verificar", TipoDato.TEXTAREA, False,
         {"ayuda": "Opcional. Señale datos faltantes. No necesita redactar antecedentes, análisis ni conclusiones."}),
    ]
    return [CampoPlantilla(uuid5(NAMESPACE_URL, f"naxji:{plantilla_id}:{clave}"), plantilla_id,
                          clave, etiqueta, tipo, obligatorio, orden, config)
            for orden, (clave, etiqueta, tipo, obligatorio, config) in enumerate(definiciones, 1)]
