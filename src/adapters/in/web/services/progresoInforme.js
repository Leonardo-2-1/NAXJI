import { armarValores, plantillaCompatible } from "./flujoInforme.js";

// El progreso depende de los datos actuales, nunca de haber visitado una pantalla.
export function progresoInforme({ form, prediccion, contextoVigente, asuntoPredicho,
  plantillas, campos, idCampos, estadoPlantillas, solicitud, informe }) {
  const plantillaLista = estadoPlantillas === "listo" && Boolean(form.plantillaId) &&
    idCampos === form.plantillaId && plantillas.some(p => p.id === form.plantillaId &&
      plantillaCompatible(p, form.tipoInformeId, form.areaDestinoId));
  const faltantes = campos.filter(c => c.activo && c.obligatorio &&
    (form.valores[c.id] == null || (typeof form.valores[c.id] === "string" && !form.valores[c.id].trim())));
  let valoresValidos = true;
  try { armarValores(campos, form.valores); } catch { valoresValidos = false; }
  const datosListos = contextoVigente && Boolean(form.tipoInformeId && form.areaDestinoId && form.areaOrigenId) &&
    plantillaLista && faltantes.length === 0 && valoresValidos;
  // Un documento existente conserva su acceso aunque su plantilla haya sido desactivada.
  const recuperandoBorrador = ["GENERADA", "PROCESANDO"].includes(solicitud?.estado);
  // Generar y editar pertenecen al paso 3. Solo el documento guardado habilita la vista previa.
  const pasoDisponible = informe ? 4 : recuperandoBorrador || contextoVigente ? 3 :
    prediccion && asuntoPredicho === form.asunto.trim() ? 2 : 1;
  return { pasoDisponible, datosListos, plantillaLista, faltantes, valoresValidos };
}
