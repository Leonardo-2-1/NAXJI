from uuid import UUID

from src.adapters.out.persistence.datos_demo import AREAS, NORMATIVAS, TIPOS
from src.application.ports.output.context_predictor import ContextPredictor
from src.domain.entities.prediccion_contexto import NormativaPredicha, PrediccionContexto


class ContextPredictorMock(ContextPredictor):
    """Respuesta fija de prueba; no ejecuta RF-IA-01 ni interpreta el asunto."""

    def predecir(self, asunto: str, solicitud_id: UUID) -> PrediccionContexto:
        return PrediccionContexto(
            solicitud_id=solicitud_id,
            tipo_informe_predicho_id=TIPOS[2].id,
            area_destino_predicha_id=AREAS[0].id,
            confianza_tipo=0.91, confianza_area=0.87,
            modelo="MOCK_CONTEXT_PREDICTOR", version_modelo="demo-1",
            parametros={"mock": True, "asunto": asunto},
            normativas=[NormativaPredicha(NORMATIVAS[0].id, 0.82, 1)],
        )
