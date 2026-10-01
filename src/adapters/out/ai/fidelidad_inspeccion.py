"""Controles conservadores de fidelidad; no sustituyen la revisión humana."""
import json
import re
import unicodedata

from src.domain.services.errores import DatosInvalidos


def normalizar(texto):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", texto.lower())
                            if unicodedata.category(c) != "Mn").split())


def politica_inspeccion(plantilla, datos, sin_hechos):
    claves = {c.clave for c in plantilla.campos if c.activo}
    if not {"resultados_observados", "lugar_inspeccion", "fecha_inspeccion"} <= claves:
        return None
    pendientes = [c for c in ("lugar_inspeccion", "fecha_inspeccion", "resultados_observados", "referencias_conocidas")
                  if not str(datos.get(c, "")).strip()]
    return {"alcance": "Informe interno de inspección PILOTO, no supervisión formal acreditada",
            "sin_resultados": sin_hechos, "datos_pendientes": pendientes,
            "observaciones_aportadas": not sin_hechos and bool(str(datos.get("resultados_observados", "")).strip()),
            "permite_recomendaciones_especificas": not sin_hechos and not pendientes}


def validar_fidelidad_inspeccion(contenido, asunto, datos, contexto, politica):
    if politica is None:
        return
    fuente = normalizar(asunto + " " + json.dumps(datos, ensure_ascii=False))
    texto_original = " ".join(contenido.values())
    texto = normalizar(texto_original)
    if politica.get("observaciones_aportadas"):
        conclusion = normalizar(contenido.get("conclusiones", contenido.get("cuerpo", "")))
        if re.search(r"\b(?:no (?:hay|existen|se aportaron|se dispone de)|ausencia (?:total )?de) (?:observaciones|hallazgos)(?: confirmados)?\b", conclusion):
            raise DatosInvalidos("La conclusión descarta observaciones que sí fueron aportadas")
        # Una fuente que dice expresamente que el contenido de las bolsas es
        # desconocido no permite convertir la hipótesis del asunto en un hallazgo.
        observaciones = normalizar(str(datos.get("resultados_observados", "")))
        contenido_desconocido = re.search(r"(?:no .{0,100}(?:identifico|verifico|comprobo).{0,30}contenido|contenido.{0,30}(?:desconocido|no verificado))", observaciones)
        if contenido_desconocido and re.search(r"\b(?:bolsas? (?:con|de) (?:residuos|basura)|residuos (?:observados|encontrados|detectados))\b", normalizar(" ".join(v for k, v in contenido.items() if k not in {"antecedentes", "objetivo"}))):
            raise DatosInvalidos("Se atribuyó a las bolsas un contenido no verificado")
    # Una petición de parque no acredita su clase, incluso en una recomendación.
    for tipo in ("infantil", "recreativo", "ecologico", "zoologico", "deportivo", "acuatico", "industrial", "tematico"):
        termino = "parque " + tipo
        if termino in texto and termino not in fuente:
            raise DatosInvalidos("Se añadió una clase de parque no aportada")
    for fecha in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", texto):
        if fecha not in fuente:
            raise DatosInvalidos("Se añadió una fecha no aportada")
    # Nombres propios de lugares: no derivarlos de la unidad administrativa.
    for lugar in re.findall(r"(?:distrito|provincia|departamento|urbanización|parque) (?:de |del )?([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+(?: [A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)*)", texto_original):
        if normalizar(lugar) not in fuente:
            raise DatosInvalidos("Se añadió un lugar no aportado")
    normas = normalizar(" ".join((n.codigo or "") + " " + n.titulo for n in contexto.normas if n.id in contexto.normativa_ids))
    for cita in re.findall(r"\b(?:ley|ordenanza|decreto|resolucion|articulo)\s+(?:n[°ºo.]*\s*)?\d+[\w./-]*", texto):
        if cita not in fuente and cita not in normas:
            raise DatosInvalidos("Se añadió una referencia normativa no aportada")
    if politica["sin_resultados"]:
        if re.search(r"\b(?:se (?:ha |han )?(?:realiz[oó]|realizado|constato|constatado|observo|observado|detecto|detectado|encontro|encontrado)|no existen hallazgos|no se registraron incidencias)\b", texto):
            raise DatosInvalidos("Se afirmó una actuación o resultado no aportado")
        for afirmacion in re.finditer(r"\b(?:hay|existe[n]?|presenta[n]?|se evidencia[n]?)\s+(?:una |un |la |el |los |las )?(?:acumulacion|residuos|deterioro|danos|riesgos|contaminacion)\b", texto):
            # 'Verificar si hay residuos' es una comprobación propuesta, no un hallazgo.
            if not texto[:afirmacion.start()].endswith("si "):
                raise DatosInvalidos("Se afirmó un estado no sustentado del lugar")
        if re.search(r"\b(?:cesped|parque|suelo|lugar) (?:esta|se encuentra)\b", texto):
            raise DatosInvalidos("Se afirmó un estado no sustentado del lugar")
    if not politica["permite_recomendaciones_especificas"]:
        if re.search(r"\b(?:se recomienda|se debe|ordenar|disponer)\s+(?:la |el )?(?:retira\w*|limpi\w*|clausur\w*|sancion\w*|podar|repara\w*)", texto):
            raise DatosInvalidos("Se propuso una actuación material sin sustento suficiente")
