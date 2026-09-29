"""Traduce IDs de la PoC a IDs reales, sin insertar catálogos ficticios."""
from src.application.ports.output.context_predictor import ContextPredictor
from src.adapters.out.persistence.datos_demo import TIPOS, AREAS, NORMATIVAS
from src.domain.services.errores import DatosInvalidos


class ContextPredictorCatalogo(ContextPredictor):
    # Correspondencias de encaminamiento propuestas, sujetas a confirmación humana.
    # ROF 2020 MDT, art. 6, pp. 7-8. No implica validación experimental del modelo.
    AREAS_MDT = {
        'AREA_SERVICIOS_PUBLICOS': 'MDT_GSP',
        'AREA_DESARROLLO_ECONOMICO': 'MDT_GDE',
        'AREA_ASESORIA_JURIDICA': 'MDT_GAJ',
        'AREA_ECOLOGIA': 'MDT_SGGA',
        'AREA_DESARROLLO_URBANO': 'MDT_SGDUR',
    }
    def __init__(self, predictor, catalogos):
        self.predictor, self.catalogos = predictor, catalogos

    @staticmethod
    def resolve(identifier, labels, records, aliases=None):
        code = next((r.codigo for r in labels if r.id == identifier), None)
        if not any(r.codigo == code and r.activo for r in records):
            code = (aliases or {}).get(code, code)
        match = next((r for r in records if code is not None and r.codigo == code and r.activo), None)
        if match is None:
            raise DatosInvalidos("Falta un código del modelo en el catálogo PostgreSQL; revise los catálogos institucionales")
        return match.id

    def predecir(self, asunto, solicitud_id):
        result = self.predictor.predecir(asunto, solicitud_id)
        result.tipo_informe_predicho_id = self.resolve(
            result.tipo_informe_predicho_id, TIPOS, self.catalogos.tipos_informe())
        areas = self.catalogos.areas()
        # Los tests existentes pueden usar sus propios catálogos con códigos PoC.
        aliases = self.AREAS_MDT if any(a.codigo.startswith('MDT_') for a in areas if a.codigo) else {}
        result.area_destino_predicha_id = self.resolve(
            result.area_destino_predicha_id, AREAS, areas, aliases)
        warnings, resolved = [], []
        for norma in result.normativas:
            code = next((r.codigo for r in NORMATIVAS if r.id == norma.normativa_id), None)
            real = self.catalogos.normativa_por_codigo(code) if code else None
            if real is None or not real.activo:
                warnings.append("Contexto normativo pendiente de revisión institucional: " + (code or 'categoría desconocida'))
                continue
            norma.normativa_id = real.id
            resolved.append(norma)
        result.normativas = resolved
        result.parametros['advertencias_catalogo'] = warnings
        if aliases:
            result.parametros['advertencias_catalogo'].append(
                'Correspondencia de área propuesta con el ROF 2020; confirme el destino. Rendimiento institucional no validado.')
        return result
