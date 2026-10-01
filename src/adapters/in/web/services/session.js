import axios from "axios";

// Sesión real: access token en memoria; refresh token en cookie HttpOnly del backend.
const authHttp = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  withCredentials: true,
  headers: { "Content-Type": "application/json", "X-NAXJI-Client": "web" },
});

let accessToken = null;
let expiresAt = 0;
let refreshing = null;
let configPromise = null;
let currentUser = null;
let revision = 0;

// Retira credenciales persistidas por la implementación demo anterior.
localStorage.removeItem("token");
localStorage.removeItem("usuario");

export const authConfig = () => {
  configPromise ??= authHttp.get("/auth/config").then(({ data }) => data).catch((error) => {
    configPromise = null;
    throw error;
  });
  return configPromise;
};

export const storedUser = () => currentUser;
export const saveUser = (user) => { currentUser = user; };
export const revisionSesion = () => revision;

export const clearSession = () => {
  revision += 1;
  accessToken = null;
  expiresAt = 0;
  currentUser = null;
  sessionStorage.removeItem("naxji_demo_token");
  window.dispatchEvent(new Event("naxji:session-ended"));
};

const acceptSession = ({ access_token, expires_in }) => {
  accessToken = access_token;
  expiresAt = Date.now() + expires_in * 1000;
  return accessToken;
};

export const getAccessToken = async (forceRefresh = false) => {
  const config = await authConfig();
  if (config.mode === "mock" && config.persistence === "memory") {
    return sessionStorage.getItem("naxji_demo_token");
  }
  if (config.mode !== "supabase") return null;
  if (!forceRefresh && accessToken && expiresAt > Date.now() + 30000) return accessToken;
  if (!refreshing) {
    const actual = revision;
    refreshing = authHttp.post("/auth/refresh").then(({ data }) => {
      if (actual !== revision) throw new axios.CanceledError("La sesión cambió.");
      return acceptSession(data);
    }).catch((error) => {
      if (actual === revision && [401, 403].includes(error.response?.status)) clearSession();
      throw error;
    }).finally(() => { refreshing = null; });
  }
  return refreshing;
};

// Solo comprueba si puede recuperarse un token. ProtectedRoute valida el perfil
// contra /auth/me antes de mostrar contenido, tanto en demo como en Supabase.
export const recuperarSesion = async () => Boolean(await getAccessToken());

export const startSession = async ({ email, password, demoToken }) => {
  // Una renovación iniciada al cargar la página no debe borrar el login nuevo.
  if (refreshing) await refreshing.catch(() => null);
  clearSession();
  const config = await authConfig();
  if (config.mode === "mock" && config.persistence === "memory") {
    sessionStorage.setItem("naxji_demo_token", demoToken);
    return;
  }
  const actual = revision;
  const { data } = await authHttp.post("/auth/login", { email, password });
  if (actual !== revision) throw new axios.CanceledError("La sesión cambió.");
  acceptSession(data);
};

export const endSession = async () => {
  if (refreshing) await refreshing.catch(() => null);
  const config = await authConfig();
  if (config.mode === "supabase") {
    // Si caducó el access token, permite que el backend renueve y revoque la sesión.
    const token = expiresAt > Date.now() ? accessToken : null;
    await authHttp.post("/auth/logout", {}, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  }
  clearSession();
};
