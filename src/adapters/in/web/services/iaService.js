import api from "./api";
import { construirValidacion } from "./flujoInforme";

export const obtenerContexto = async (id, opciones = {}) =>
  (await api.get(`/solicitudes/${id}/contexto`, opciones)).data;

export const predecirContexto = async (solicitudId) => {
  const response = await api.post(
    `/solicitudes/${solicitudId}/predecir-contexto`
  );

  return response.data;
};

export const validarPrediccion = async (solicitudId, prediccion, seleccion, rechazar = false) => {
  const datos = construirValidacion(prediccion, seleccion, rechazar);

  const response = await api.post(
    `/solicitudes/${solicitudId}/validar-prediccion`,
    datos
  );

  return response.data;
};

export const generarBorrador = async (solicitudId, instrucciones) => {
  const response = await api.post(
    `/solicitudes/${solicitudId}/generar-borrador`,
    {
      instrucciones,
    }
  );

  return response.data;
};
