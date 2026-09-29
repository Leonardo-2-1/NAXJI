import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { login, obtenerUsuarioActual, USUARIOS_DEMO } from "../services/authService";
import { authConfig } from "../services/session";
import { mensajeError } from "../services/api";

function Login() {
  const navigate = useNavigate();

  const [usuario, setUsuario] = useState("demo-funcionario");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [config, setConfig] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    let active = true;
    authConfig().then(async (data) => {
      if (!active) return;
      setConfig(data);
      try {
        await obtenerUsuarioActual();
        if (active) navigate("/nuevo-informe", { replace: true });
      } catch (err) {
        if (active && ![401, 403].includes(err.response?.status)) {
          setError(mensajeError(err, "No se pudo comprobar la sesión."));
        }
      }
    }).catch((err) => { if (active) setError(mensajeError(err, "No se pudo cargar el acceso.")); });
    return () => { active = false; };
  }, [navigate]);
  const demo = config?.mode === "mock" && config?.persistence === "memory";

  const iniciarSesion = async (e) => {
    e.preventDefault();

    setCargando(true);
    setError("");

    try {
      await login({ email, password, demoToken: usuario });
      navigate("/nuevo-informe");
    } catch (err) {
      setError(
        mensajeError(
          err,
          "No se pudo iniciar sesión. Verifique que el backend esté encendido."
        )
      );
    } finally {
      setPassword("");
      setCargando(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">🏛️</div>

        <h1>NAXJI</h1>

        <p className="login-subtitle">
          Copilot Generativo para la Elaboración de Informes Municipales
        </p>

        <form onSubmit={iniciarSesion}>
          {demo ? <>
          <div className="form-group">
            <label>Identidad de demostración</label>

            <select
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
            >
              {USUARIOS_DEMO.map((item) => (
                <option key={item.token} value={item.token}>
                  {item.etiqueta}
                </option>
              ))}
            </select>
          </div>

          <p className="hint-text">
            Acceso de demostración con datos temporales.
          </p>
          </> : <>
            <div className="form-group">
              <label htmlFor="email">Correo electrónico</label>
              <input id="email" type="email" autoComplete="username" required value={email}
                onChange={(e) => setEmail(e.target.value)} disabled={cargando} />
            </div>
            <div className="form-group">
              <label htmlFor="password">Contraseña</label>
              <input id="password" type="password" autoComplete="current-password" required value={password}
                onChange={(e) => setPassword(e.target.value)} disabled={cargando} />
            </div>
          </>}

          {error && <p className="error-message">{error}</p>}

          <button className="btn-primary" type="submit" disabled={cargando || !config || config.mode === "disabled"}>
            {cargando ? "Ingresando..." : "Iniciar sesión"}
          </button>
        </form>

        <p className="demo-text">{demo ? "Acceso de demostración - PMV 1" : "Acceso institucional - NAXJI"}</p>
      </div>
    </div>
  );
}

export default Login;
