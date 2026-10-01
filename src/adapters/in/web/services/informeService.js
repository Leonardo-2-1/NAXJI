import api from "./api";

export const obtenerInformePorSolicitud = async (solicitudId, opciones = {}) =>
  (await api.get(`/solicitudes/${solicitudId}/informe`, opciones)).data;

export const obtenerVersionInforme = async (informeId, numeroVersion) =>
  (await api.get(`/informes/${informeId}/versiones/${numeroVersion}`)).data;

export const descargarVersionDocx = async (informeId, numeroVersion) => {
  try {
    return (await api.get(`/informes/${informeId}/versiones/${numeroVersion}/docx`, { responseType: "blob" })).data;
  } catch (error) {
    if (error.response?.data instanceof Blob) {
      try { error.response.data = JSON.parse(await error.response.data.text()); }
      catch { /* Mantiene el error genérico si la respuesta no es JSON. */ }
    }
    throw error;
  }
};

export function guardarArchivoDocx(blob, nombre) {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const obtenerInforme = async (informeId) => {
  const response = await api.get(
    `/informes/${informeId}`
  );

  return response.data;
};

export const guardarBorrador = async (
  informeId,
  contenido,
  numeroVersion,
  titulo,
  encabezadoOficial
) => {
  const response = await api.put(
    `/informes/${informeId}`,
    {
      contenido,
      numero_version: numeroVersion,
      titulo: titulo?.trim() ? titulo.trim() : null,
      ...(encabezadoOficial ? { encabezado_oficial: encabezadoOficial } : {}),
    }
  );

  return response.data;
};
