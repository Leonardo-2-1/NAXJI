import api from "./api";

export const obtenerTiposInforme = async (opciones = {}) => {
  const response = await api.get("/tipos-informe", opciones);
  return response.data;
};

export const obtenerAreas = async (opciones = {}) => {
  const response = await api.get("/areas", opciones);
  return response.data;
};

export const obtenerPlantillas = async (tipoInformeId, opciones = {}) => {
  const response = await api.get("/plantillas", {
    ...opciones,
    params: {
      tipo_informe_id: tipoInformeId,
    },
  });

  return response.data;
};

export const obtenerCamposPlantilla = async (plantillaId, opciones = {}) => {
  const response = await api.get(
    `/plantillas/${plantillaId}/campos`, opciones
  );

  return response.data;
};
