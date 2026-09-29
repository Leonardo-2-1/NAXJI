import axios from "axios";
import { authConfig, clearSession, getAccessToken } from "./session";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(async (config) => {
  const token = await getAccessToken();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
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
