from src.application.ports.output.generador_borrador import (
    ContextoConfirmado, GeneradorBorrador, ResultadoBorrador,
)
from src.domain.entities.plantilla import Plantilla


class GeneradorBorradorMock(GeneradorBorrador):
    def generar(self, asunto: str, plantilla: Plantilla, datos: dict,
                contexto: ContextoConfirmado, instrucciones: str) -> ResultadoBorrador:
        return ResultadoBorrador(
            contenido={
                "antecedentes": datos.get("antecedentes", ""),
                "desarrollo": f"BORRADOR MOCK — {asunto}. {datos.get('detalle', '')}",
                "objetivo": datos.get("objetivo", ""),
                "conclusiones": datos.get("conclusiones", "Texto de demostración; requiere elaboración y revisión humana."),
                "recomendaciones": datos.get("recomendaciones", ""),
                "plantilla": plantilla.nombre,
                "datos": datos,
                "contexto": {
                    "tipo_informe_id": str(contexto.tipo_informe_id),
                    "area_destino_id": str(contexto.area_destino_id),
                    "normativa_ids": [str(n) for n in contexto.normativa_ids],
                },
                "instrucciones": instrucciones,
            }, modelo_ia="MOCK_GENERADOR_BORRADOR",
        )
