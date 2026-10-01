from src.domain.services.errores import DatosInvalidos


def verificar_referencias_normativas(catalogos, prediccion, seleccionadas):
    """Revalidar la curación antes de aceptar/generar; conservar lectura histórica."""
    if not seleccionadas or prediccion.parametros.get("mapeo_normativo_version") != 1:
        return
    evidencias = prediccion.parametros.get("correspondencias_normativas", {})
    etiquetas = {e["etiqueta"] for nid in seleccionadas for e in evidencias.get(str(nid), [])}
    actuales = catalogos.correspondencias_normativas(sorted(etiquetas))
    for nid in seleccionadas:
        originales = evidencias.get(str(nid), [])
        if not any(c.normativa.id == nid and c.elegible()
                   and any(c.evidencia() == {k: v for k, v in e.items() if k != "confianza_tema"}
                           for e in originales) for c in actuales):
            raise DatosInvalidos("La verificación de una referencia normativa cambió o no está disponible. Vuelva a analizar y confirmar el asunto.")
