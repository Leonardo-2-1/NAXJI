import json
import re

from src.application.ports.output.generador_borrador import (
    ContextoConfirmado,
    GeneradorBorrador,
    ResultadoBorrador,
)
from src.domain.entities.plantilla import Plantilla
from src.adapters.out.ai.ollama_adapter import OllamaAdapter


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

Devuelve ÚNICAMENTE un objeto JSON válido con exactamente estas propiedades:

{{
"antecedentes": "Texto de antecedentes",
"desarrollo": "Texto del desarrollo",
"conclusiones": "Texto de conclusiones"
}}

No agregues explicaciones.
No utilices Markdown.
No coloques ```json.
"""

        respuesta = self.llm.generar(prompt)

        contenido = self._convertir_a_json(respuesta)

        return ResultadoBorrador(
            contenido=contenido,
            modelo_ia="qwen2.5-coder:7b",
            prompt_version="v1"
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

        for campo in (
            "antecedentes",
            "desarrollo",
            "conclusiones"
        ):
            if campo not in contenido:
                raise ValueError(
                    f"La IA no devolvió el campo requerido: {campo}"
                )

        return contenido
