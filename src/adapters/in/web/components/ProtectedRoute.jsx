import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { isCancel } from "axios";

import { obtenerUsuarioActual } from "../services/authService";
import { mensajeError } from "../services/api";
import { clearSession } from "../services/session";
import EstadoAcceso from "./EstadoAcceso";
import { cargarFormulario } from "../services/cargarFormulario";

function ProtectedRoute({ children }) {
  const [estado, setEstado] = useState("cargando");
  const [error, setError] = useState("");
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let active = true;
    const ended = () => setEstado("sin-sesion");
    window.addEventListener("naxji:session-ended", ended);
    cargarFormulario().catch(() => {});
    obtenerUsuarioActual()
      .then(() => { if (active) setEstado("ok"); })
      .catch((err) => {
        if (!active || isCancel(err)) return;
        if ([401, 403].includes(err.response?.status)) {
          setError(mensajeError(err, "Su sesión no permite acceder. Inicie sesión nuevamente."));
          clearSession();
          setEstado("sin-sesion");
        }
        else {
          setError(mensajeError(err, "No se pudo comprobar la sesión. Intente recargar."));
          setEstado("error");
        }
      });
    return () => { active = false; window.removeEventListener("naxji:session-ended", ended); };
  }, [intento]);

  if (estado === "error") return <EstadoAcceso error={error} onRetry={() => {
    setError(""); setEstado("cargando"); setIntento(i => i + 1);
  }} />;

  if (estado === "cargando") {
    return <EstadoAcceso>Comprobando su sesión con el backend…</EstadoAcceso>;
  }

  if (estado === "sin-sesion") {
    return <Navigate to="/" replace state={error ? { errorAcceso: error } : null} />;
  }

  return children;
}

export default ProtectedRoute;
