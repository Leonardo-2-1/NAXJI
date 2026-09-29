import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { obtenerUsuarioActual } from "../services/authService";
import { mensajeError } from "../services/api";

function ProtectedRoute({ children }) {
  const [estado, setEstado] = useState("cargando");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const ended = () => setEstado("sin-sesion");
    window.addEventListener("naxji:session-ended", ended);
    obtenerUsuarioActual()
      .then(() => { if (active) setEstado("ok"); })
      .catch((err) => {
        if (!active) return;
        if ([401, 403].includes(err.response?.status)) setEstado("sin-sesion");
        else {
          setError(mensajeError(err, "No se pudo comprobar la sesión. Intente recargar."));
          setEstado("error");
        }
      });
    return () => { active = false; window.removeEventListener("naxji:session-ended", ended); };
  }, []);

  if (estado === "error") return <p role="alert">{error}</p>;

  if (estado === "cargando") {
    return <p style={{ padding: "30px" }}>Comprobando sesión con el backend...</p>;
  }

  if (estado === "sin-sesion") {
    return <Navigate to="/" replace />;
  }

  return children;
}

export default ProtectedRoute;
