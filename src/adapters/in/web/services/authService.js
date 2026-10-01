import api from "./api";
import axios from "axios";
import { clearSession, endSession, saveUser, startSession, storedUser, revisionSesion } from "./session";

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
    // La ruta protegida consulta /auth/me antes de montar el área privada.
    // /auth/login ya valida identidad, actividad y roles en el backend real.
  } catch (error) {
    clearSession();
    throw error;
  }
};

let perfilPendiente = null;
export const obtenerUsuarioActual = () => {
  const revision = revisionSesion();
  if (perfilPendiente?.revision === revision) return perfilPendiente.promise;
  const consulta = { revision };
  consulta.promise = api.get("/auth/me").then(({ data }) => {
    if (revision !== revisionSesion()) throw new axios.CanceledError("La sesión cambió.");
    saveUser(data);
    return data;
  }).finally(() => {
    if (perfilPendiente === consulta) perfilPendiente = null;
  });
  // Comparte solo peticiones simultáneas, sin caché de permisos ni de perfiles.
  perfilPendiente = consulta;
  return consulta.promise;
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
