import api from "./api";

export const obtenerContexto = async (id) => (await api.get(`/solicitudes/${id}/contexto`)).data;

export const predecirContexto = async (solicitudId) => {
  const response = await api.post(
    `/solicitudes/${solicitudId}/predecir-contexto`
  );

  return response.data;
};

export const validarPrediccion = async (
  solicitudId,
  prediccionId,
  resultado,
  correccion = {}
) => {
  const datos = {
    prediccion_id: prediccionId,
    resultado,
  };

  if (resultado === "CORREGIDA") {
    datos.tipo_informe_id = correccion.tipoInformeId;
    datos.area_destino_id = correccion.areaDestinoId;
  }

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
