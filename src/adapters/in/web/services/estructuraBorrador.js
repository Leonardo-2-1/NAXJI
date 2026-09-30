// Los campos de entrada pertenecen al formulario; estas secciones pertenecen al documento.
const tecnicas = new Set(["encabezado", "datos", "contexto", "plantilla", "instrucciones"]);
const anteriores = [
  { clave: "antecedentes", titulo: "Antecedentes", obligatoria: true },
  { clave: "desarrollo", titulo: "Desarrollo", obligatoria: true },
  { clave: "conclusiones", titulo: "Conclusiones", obligatoria: true },
];

export function tituloDato(clave) {
  const titulos = { asunto: "Asunto", area_origen: "Área de origen", area_destino: "Área de destino",
    autor_id: "ID del autor", tipo_informe_id: "ID del tipo de informe", area_destino_id: "ID del área de destino",
    normativa_ids: "IDs de normas confirmadas", encabezado: "Encabezado" };
  return titulos[clave] || clave.replaceAll("_", " ").replace(/^./, letra => letra.toUpperCase());
}

export function seccionesDePlantilla(plantilla) {
  return plantilla?.secciones_salida ?? anteriores;
}

export function seccionesDelBorrador(informe) {
  // La estructura de la versión tiene prioridad: nunca se usa la plantilla actual.
  const secciones = seccionesDePlantilla(informe);
  const legacy = informe.estructura_legacy ?? informe.secciones_salida == null;
  if (!legacy) return secciones;
  const claves = new Set(secciones.map(s => s.clave));
  const adicionales = Object.entries(informe.contenido || {})
    .filter(([clave, valor]) => !claves.has(clave) && !tecnicas.has(clave) && typeof valor === "string")
    .map(([clave]) => ({ clave, titulo: tituloDato(clave), obligatoria: false }));
  return [...secciones, ...adicionales];
}

export function validarSeccionesBorrador(informe, contenido) {
  for (const seccion of seccionesDelBorrador(informe)) {
    const texto = contenido[seccion.clave];
    if (seccion.obligatoria && (typeof texto !== "string" || !texto.trim())) {
      throw new Error(`Complete la sección «${seccion.titulo}».`);
    }
    if (Object.hasOwn(contenido, seccion.clave) && typeof texto !== "string") throw new Error(`La sección «${seccion.titulo}» debe contener texto.`);
  }
}
