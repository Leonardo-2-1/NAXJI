import { useNavigate } from "react-router-dom";
import { useState } from "react";

import { etiquetaUsuario, logout } from "../services/authService";
import { mensajeError } from "../services/api";

function Header() {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  const cerrarSesion = async () => {
    try {
      await logout();
      navigate("/");
    } catch (err) {
      setError(mensajeError(err, "No se pudo cerrar la sesión. Inténtelo nuevamente."));
    }
  };

  return (
    <header className="header">
      <div className="header-brand">
        <span className="brand-mark" aria-hidden="true">N</span>
        <div><h2>NAXJI</h2><span>Copilot Municipal</span></div>
      </div>

      <div className="header-user">
        <span>{etiquetaUsuario()}</span>
        {error && <span role="alert">{error}</span>}

        <button type="button" onClick={cerrarSesion}>
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}

export default Header;
