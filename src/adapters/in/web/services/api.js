import axios from "axios";
import { authConfig, clearSession, getAccessToken, revisionSesion } from "./session";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(async (config) => {
  const revision = revisionSesion();
  const token = await getAccessToken();
  if (revision !== revisionSesion()) throw new axios.CanceledError("La sesión cambió.");
  config._sessionRevision = revision;
  config._apiAutenticada = true;

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

api.interceptors.response.use(
  (response) => {
    if (response.config._sessionRevision !== revisionSesion()) throw new axios.CanceledError("La sesión cambió.");
    return response;
  },
  async (error) => {
    // Un 401 de /auth/refresh en el interceptor de petición no es un fallo
    // de la API protegida: no debe disparar otra renovación de la misma cookie.
    if (error.config?._apiAutenticada && error.config._sessionRevision !== revisionSesion()) {
      throw new axios.CanceledError("La sesión cambió.");
    }
    if (error.response?.status === 401 && error.config?._apiAutenticada) {
      if (error.config && !error.config._authRetried && (await authConfig()).mode === "supabase") {
        error.config._authRetried = true;
        try {
          await getAccessToken(true);
          return api(error.config);
        } catch (refreshError) {
          return Promise.reject(refreshError);
        }
      }
      clearSession();
    }

    return Promise.reject(error);
  }
);

export const mensajeError = (error, respaldo) => {
  const detalle = error?.response?.data?.detail;

  if (typeof detalle === "string" && detalle.trim()) {
    return detalle;
  }

  if (Array.isArray(detalle)) {
    const textos = detalle
      .map((item) => item?.msg || item?.detail || "")
      .filter(Boolean);

    if (textos.length > 0) {
      return textos.join(" ");
    }
  }

  if (!error?.response) {
    return "No se pudo conectar con el backend. Verifique que esté encendido en http://127.0.0.1:8000.";
  }

  return respaldo;
};

export default api;
