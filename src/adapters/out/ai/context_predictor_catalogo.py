"""Traduce IDs de la PoC a IDs reales, sin insertar catálogos ficticios."""
from src.application.ports.output.context_predictor import ContextPredictor
from src.adapters.out.persistence.datos_demo import TIPOS, AREAS, NORMATIVAS
from src.domain.services.errores import DatosInvalidos
from src.domain.entities.prediccion_contexto import NormativaPredicha
from math import isfinite


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
        warnings, resolved, temas, evidencias = [], {}, [], {}
        etiquetas = {n.id: n for n in NORMATIVAS}
        codigos = [etiquetas[n.normativa_id].codigo for n in result.normativas if n.normativa_id in etiquetas]
        correspondencias = self.catalogos.correspondencias_normativas(codigos)
        for norma in result.normativas:
            tema = etiquetas.get(norma.normativa_id)
            if tema is None:
                warnings.append("Tema normativo desconocido; correspondencia documental pendiente de revisión.")
                continue
            if norma.confianza is not None and (not isfinite(norma.confianza) or not 0 <= norma.confianza <= 1):
                raise DatosInvalidos("La confianza temática debe estar entre 0 y 1")
            asociadas = [c for c in correspondencias if c.etiqueta == tema.codigo and c.elegible()]
            ids = []
            for c in asociadas:
                nid = c.normativa.id
                if str(nid) not in ids:
                    ids.append(str(nid))
                if nid not in resolved:
                    resolved[nid] = NormativaPredicha(nid, norma.confianza, len(resolved) + 1)
                elif norma.confianza is not None:
                    anterior = resolved[nid].confianza
                    resolved[nid].confianza = max(anterior, norma.confianza) if anterior is not None else norma.confianza
                evidencias.setdefault(str(nid), []).append({**c.evidencia(), "confianza_tema": norma.confianza})
            temas.append({"codigo": tema.codigo, "etiqueta": tema.titulo, "confianza": norma.confianza,
                          "normativa_ids": ids})
            if not ids:
                warnings.append(f"Tema identificado: {tema.codigo}. No existe una norma verificable asociada; revisión documental pendiente.")
        result.normativas = list(resolved.values())
        result.parametros.update({"mapeo_normativo_version": 1, "temas_normativos": temas,
                                  "correspondencias_normativas": evidencias})
        if temas:
            warnings.append("La confianza corresponde al tema detectado; no acredita vigencia ni aplicabilidad jurídica. Confirme cada referencia documental para este caso.")
        result.parametros['advertencias_catalogo'] = warnings
        if aliases:
            result.parametros['advertencias_catalogo'].append(
                'Correspondencia de área propuesta con el ROF 2020; confirme el destino. Rendimiento institucional no validado.')
        return result
