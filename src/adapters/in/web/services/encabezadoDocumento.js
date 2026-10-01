export const camposOficiales = [
  ["numero", "Número de informe"], ["emisor", "Emisor / unidad remitente"],
  ["destinatario", "Destinatario / unidad destinataria"], ["fecha", "Fecha del documento"],
  ["referencia", "Referencia administrativa"], ["firmante", "Nombre del firmante"],
  ["cargo_firmante", "Cargo del firmante"],
];
export const formatoMdt = "mdt_informe_anexo08_2019_revision1";
const camposMdt = [
  ["cargo_destinatario", "Cargo del destinatario"], ["lugar_emision", "Lugar de emisión"],
  ["registro_documento", "Registro administrativo del documento"], ["registro_expediente", "Expediente"],
  ["iniciales", "Iniciales de firmante y digitador"], ["copias", "Copias para conocimiento"],
  ["anexos", "Adjuntos que efectivamente acompañan al documento"],
];
export function camposDelEncabezado(encabezado) {
  return encabezado?.formato_documento === formatoMdt ? [...camposOficiales, ...camposMdt] : camposOficiales;
}
export function textoPublico(valor) {
  return typeof valor === "string" && !/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i.test(valor) ? valor.trim() : "";
}
export function datosOficiales(encabezado) {
  const datos = encabezado?.documento ?? { emisor: encabezado?.area_origen, destinatario: encabezado?.area_destino };
  return Object.fromEntries(camposDelEncabezado(encabezado).map(([clave]) => [clave, textoPublico(datos?.[clave])]));
}
export function plantillaPosterior(plantillas, id) {
  const actual = plantillas.find(p => p.id === id);
  return actual && plantillas.filter(p => p.activa !== false && p.nombre === actual.nombre &&
    p.tipo_informe_id === actual.tipo_informe_id && p.area_id === actual.area_id && p.version > actual.version)
    .sort((a, b) => b.version - a.version)[0];
}
