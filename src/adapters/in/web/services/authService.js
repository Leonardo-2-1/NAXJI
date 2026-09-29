import api from "./api";
import { clearSession, endSession, saveUser, startSession, storedUser } from "./session";

const ROLES_ELABORACION = ["FUNCIONARIO", "ADMINISTRADOR"];

const ETIQUETAS_ROL = {
  FUNCIONARIO: "Funcionario municipal",
  ADMINISTRADOR: "Administrador",
  REVISOR: "Revisor",
  APROBADOR: "Aprobador",
};

export const USUARIOS_DEMO = [
  {
    token: "demo-funcionario",
    etiqueta: "Funcionario municipal",
  },
  {
    token: "demo-admin",
    etiqueta: "Administrador",
  },
  {
    token: "demo-revisor",
    etiqueta: "Revisor (solo lectura)",
  },
  {
    token: "demo-aprobador",
    etiqueta: "Aprobador (solo lectura)",
  },
  {
    token: "demo-otro",
    etiqueta: "Otro funcionario",
  },
];

export const login = async (credentials) => {
  try {
    await startSession(credentials);
    const response = await api.get("/auth/me");
    saveUser(response.data);
    return response.data;
  } catch (error) {
    clearSession();
    throw error;
  }
};

export const obtenerUsuarioActual = async () => {
  const response = await api.get("/auth/me");
  saveUser(response.data);
  return response.data;
};

export const logout = endSession;
export const obtenerUsuarioGuardado = storedUser;

export const rolesUsuario = (usuario = obtenerUsuarioGuardado()) => {
  if (!usuario?.roles) {
    return [];
  }

  if (Array.isArray(usuario.roles)) {
    return usuario.roles;
  }

  return Object.values(usuario.roles);
};

export const puedeElaborar = (usuario = obtenerUsuarioGuardado()) => {
  return rolesUsuario(usuario).some((rol) =>
    ROLES_ELABORACION.includes(rol)
  );
};

export const etiquetaUsuario = (usuario = obtenerUsuarioGuardado()) => {
  const roles = rolesUsuario(usuario);
  const rol = roles.find((item) => ETIQUETAS_ROL[item]);
  const nombre = usuario?.nombres || usuario?.email;
  const etiqueta = ETIQUETAS_ROL[rol] || "Usuario";
  return nombre ? `${nombre} — ${etiqueta}` : etiqueta;
};
