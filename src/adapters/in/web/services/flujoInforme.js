// Estado del formulario derivado de los contratos HTTP; no infiere resultados de IA.
export const esConfirmada = (prediccion) =>
  ["ACEPTADA", "CORREGIDA"].includes(prediccion?.resultado_validacion);

export const esEditable = (solicitud) =>
  !solicitud || ["BORRADOR", "LISTA_PARA_GENERAR"].includes(solicitud.estado);

export const esUUID = (valor) =>
  /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(valor || "");

export const mismaSeleccion = (a, b) =>
  a.length === b.length && new Set(a).size === a.length && a.every(id => b.includes(id));

export const seleccionInicial = (solicitud, prediccion) => ({
  // En CORREGIDA la respuesta de predicción conserva los IDs originales.
  tipoInformeId: (esConfirmada(prediccion) ? solicitud.tipo_informe_id : prediccion?.tipo_informe?.id) || "",
  areaDestinoId: (esConfirmada(prediccion) ? solicitud.area_destino_id : prediccion?.area_destino?.id) || "",
  normativaIds: (prediccion?.normativas || [])
    .filter(n => esConfirmada(prediccion) ? n.aceptada === true : n.aceptada !== false)
    .map(n => n.normativa_id),
});

export function construirValidacion(prediccion, seleccion, rechazar = false) {
  if (!prediccion?.id) throw new Error("Primero analice el asunto.");
  if (rechazar) return { prediccion_id: prediccion.id, resultado: "RECHAZADA" };
  const { tipoInformeId, areaDestinoId, normativaIds } = seleccion;
  if (!tipoInformeId || !areaDestinoId) throw new Error("Seleccione el tipo y el área de destino para confirmar.");
  const propuestas = (prediccion.normativas || []).map(n => n.normativa_id);
  if (new Set(normativaIds).size !== normativaIds.length || normativaIds.some(id => !propuestas.includes(id))) {
    throw new Error("Solo puede confirmar normas incluidas en esta predicción, sin duplicarlas.");
  }
  const corregida = tipoInformeId !== prediccion.tipo_informe?.id ||
    areaDestinoId !== prediccion.area_destino?.id || !mismaSeleccion(normativaIds, propuestas);
  return {
    prediccion_id: prediccion.id,
    resultado: corregida ? "CORREGIDA" : "ACEPTADA",
    ...(corregida ? {
      tipo_informe_id: tipoInformeId,
      area_destino_id: areaDestinoId,
      normativa_ids: [...normativaIds],
    } : {}),
  };
}

export const plantillaCompatible = (plantilla, tipoId, areaId) =>
  plantilla.activa && plantilla.tipo_informe_id === tipoId &&
  (!plantilla.area_id || plantilla.area_id === areaId);

export function valoresDePlantilla(campos, valores = {}) {
  return Object.fromEntries(campos.filter(c => c.activo).map(c => [
    c.id, Object.hasOwn(valores, c.id) ? valores[c.id] : c.tipo_dato === "boolean" ? false : "",
  ]));
}

export function armarValores(campos, valores) {
  return campos.filter(c => c.activo).flatMap(campo => {
    const valor = valores[campo.id];
    if (valor == null || (typeof valor === "string" && !valor.trim())) return [];
    const convertido = campo.tipo_dato === "number" ? Number(valor) : valor;
    if (campo.tipo_dato === "number" && !Number.isFinite(convertido)) {
      throw new Error(`Ingrese un número válido en ${campo.etiqueta}.`);
    }
    return [{ campo_plantilla_id: campo.id, valor: convertido }];
  });
}

// Cada edición invalida todos los resultados pendientes, incluso si vuelve al texto anterior.
export function crearVigencia() {
  let revision = 0;
  return {
    invalidar: () => { revision += 1; },
    capturar: () => {
      const actual = revision;
      return () => actual === revision;
    },
  };
}
