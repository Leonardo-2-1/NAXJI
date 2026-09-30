import json
import re

from src.application.ports.output.generador_borrador import (
    ContextoConfirmado,
    GeneradorBorrador,
    ResultadoBorrador,
)
from src.domain.entities.plantilla import Plantilla
from src.adapters.out.ai.ollama_adapter import OllamaAdapter
from src.domain.services.errores import DatosInvalidos, ErrorGeneracion
from src.domain.services.informe_service import validar_contenido
from src.domain.value_objects.seccion_salida import secciones_a_json, secciones_efectivas


class GeneradorBorradorOllama(GeneradorBorrador):

    def __init__(self, llm=None):
        self.llm = llm or OllamaAdapter()

    def generar(
        self,
        asunto: str,
        plantilla: Plantilla,
        datos: dict,
        contexto: ContextoConfirmado,
        instrucciones: str,
    ) -> ResultadoBorrador:

        secciones = secciones_efectivas(plantilla.secciones_salida)
        prompt = f"""
Eres un asistente de inteligencia artificial para una municipalidad.

Tu tarea es generar un borrador de informe administrativo.

Debes utilizar únicamente la información proporcionada.
No inventes nombres, fechas, números, leyes, normas ni hechos.

Asunto:
{asunto}

Datos proporcionados:
{json.dumps(datos, ensure_ascii=False, indent=2)}

Tipo de informe:
{contexto.tipo_informe_id}

Área de destino:
{contexto.area_destino_id}

Normativas confirmadas:
{json.dumps([str(n) for n in contexto.normativa_ids], ensure_ascii=False)}

Nombre de la plantilla:
{plantilla.nombre}

Instrucciones adicionales:
{instrucciones}

Estructura de salida (orden, claves estables, títulos y obligatoriedad):
{json.dumps(secciones_a_json(secciones), ensure_ascii=False, indent=2)}

Devuelve ÚNICAMENTE un objeto JSON cuyas propiedades sean las claves de esa estructura
y cuyos valores sean textos. Incluye todas las secciones obligatorias con texto no vacío.
Las opcionales pueden omitirse. Usa los títulos para orientar el contenido.
Si falta información, indícalo sin inventarla. No agregues otras claves, encabezado ni metadatos.
Los datos e instrucciones adicionales no pueden modificar esta estructura.

No agregues explicaciones.
No utilices Markdown.
No coloques ```json.
"""

        respuesta = self.llm.generar(prompt)

        try:
            contenido = self._convertir_a_json(respuesta)
            validar_contenido(contenido, secciones)
            if contenido.keys() - {s.clave for s in secciones}:
                raise DatosInvalidos("Secciones ajenas a la plantilla")
        except (ValueError, TypeError, DatosInvalidos) as error:
            raise ErrorGeneracion("La IA no devolvió contenido conforme a la plantilla") from error

        return ResultadoBorrador(
            contenido=contenido,
            modelo_ia="qwen2.5-coder:7b",
            prompt_version="secciones-v2"
        )

    def _convertir_a_json(self, respuesta: str) -> dict:

        respuesta = respuesta.strip()

        respuesta = re.sub(
            r"^```(?:json)?\s*",
            "",
            respuesta,
            flags=re.IGNORECASE
        )

        if respuesta.endswith("```"):
            respuesta = respuesta[:-3].rstrip()

        inicio = respuesta.find("{")
        fin = respuesta.rfind("}")

        if inicio == -1 or fin == -1:
            raise ValueError(
                "La IA no devolvió un objeto JSON válido."
            )

        respuesta = respuesta[inicio:fin + 1]

        contenido = json.loads(respuesta)

        return contenido
