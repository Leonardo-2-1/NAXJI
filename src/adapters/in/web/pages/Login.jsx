import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { login, USUARIOS_DEMO } from "../services/authService";
import { authConfig, recuperarSesion } from "../services/session";
import { mensajeError } from "../services/api";
import { cargarFormulario } from "../services/cargarFormulario";

export default function Login() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const [usuario, setUsuario] = useState("demo-funcionario");
  const [cargando, setCargando] = useState(false);
  const [verificando, setVerificando] = useState(true);
  const [error, setError] = useState(() => typeof state?.errorAcceso === "string" ? state.errorAcceso : "");
  const [config, setConfig] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let active = true;
    async function comprobar() {
      try {
        const data = await authConfig();
        if (!active) return;
        setConfig(data);
        if (data.mode === "disabled") return;
        // La ruta privada comprueba el perfil antes de montar el formulario.
        if (await recuperarSesion() && active) navigate("/nuevo-informe", { replace: true });
      } catch (err) {
        if (active && ![401, 403].includes(err.response?.status)) {
          setError(mensajeError(err, "No se pudo comprobar el acceso. Intente nuevamente."));
        }
      } finally {
        if (active) setVerificando(false);
      }
    }
    comprobar();
    return () => { active = false; };
  }, [navigate, intento]);

  const demo = config?.mode === "mock" && config?.persistence === "memory";
  const disponible = demo || config?.mode === "supabase";
  const ocupado = cargando || verificando;

  const iniciarSesion = async (e) => {
    e.preventDefault();
    if (ocupado || !disponible) return;
    setCargando(true);
    setError("");
    cargarFormulario().catch(() => {}); // La ruta ofrece recuperación si falla la descarga.
    try {
      await login({ email, password, demoToken: usuario });
      navigate("/nuevo-informe", { replace: true });
    } catch (err) {
      setError(mensajeError(err, "No se pudo iniciar sesión. Verifique sus datos e intente nuevamente."));
    } finally {
      setPassword("");
      setCargando(false);
    }
  };

  function reintentar() {
    setError("");
    setVerificando(true);
    setIntento(n => n + 1);
  }

  return <main className="acceso-page">
    <section className="acceso-presentacion" aria-labelledby="acceso-bienvenida">
      <div className="acceso-brand"><span className="acceso-marca" aria-hidden="true">N</span>
        <div><strong>NAXJI</strong><span>Copilot Municipal</span></div>
      </div>
      <div className="acceso-mensaje">
        <p className="acceso-eyebrow">SU ESPACIO DE ELABORACIÓN</p>
        <h1 id="acceso-bienvenida">De sus datos a un<br className="acceso-salto" /> informe claro.</h1>
        <p>Organice la información, revise las sugerencias y dé forma a sus informes con asistencia de IA.</p>
        <div className="acceso-documento" aria-hidden="true">
          <div className="acceso-documento-icono">▤</div>
          <div className="acceso-documento-lineas"><i /><i /><i /></div>
          <span>✦</span>
        </div>
      </div>
      <p className="acceso-principio"><span aria-hidden="true">✦</span> La IA asiste. Usted revisa y confirma.</p>
    </section>

    <section className="acceso-formulario" aria-labelledby="acceso-titulo">
      <div className="acceso-card">
        <p className="acceso-eyebrow">BIENVENIDO A NAXJI</p>
        <h2 id="acceso-titulo">Iniciar sesión</h2>
        <p className="acceso-descripcion">Acceda a su espacio para elaborar y revisar informes municipales.</p>
        {config && <span className={`acceso-modalidad${demo ? " acceso-demo" : ""}`}>
          {demo ? "Entorno de demostración" : disponible ? "Acceso institucional" : "Acceso no habilitado"}
        </span>}

        {verificando && <p className="acceso-status" role="status">
          {!config ? "Cargando configuración de acceso…" : "Comprobando si tiene una sesión activa…"}
        </p>}
        {config && !disponible && <p className="acceso-aviso" role="alert">El acceso no está habilitado. Consulte al administrador.</p>}
        <form onSubmit={iniciarSesion} aria-labelledby="acceso-titulo">
          {config && (demo ? <>
            <div className="acceso-campo">
              <label htmlFor="usuario-demo">Identidad de demostración</label>
              <select id="usuario-demo" value={usuario} onChange={e => setUsuario(e.target.value)} disabled={ocupado}
                aria-describedby="acceso-ayuda-demo">
                {USUARIOS_DEMO.map(item => <option key={item.token} value={item.token}>{item.etiqueta}</option>)}
              </select>
            </div>
            <p id="acceso-ayuda-demo" className="acceso-ayuda">Este entorno utiliza datos temporales y no requiere correo ni contraseña.</p>
          </> : disponible && <>
            <div className="acceso-campo">
              <label htmlFor="email">Correo electrónico</label>
              <input id="email" name="email" type="email" autoComplete="username" autoCapitalize="none" spellCheck={false}
                required value={email} onChange={e => setEmail(e.target.value)} disabled={cargando}
                placeholder="Su correo institucional" />
            </div>
            <div className="acceso-campo">
              <label htmlFor="password">Contraseña</label>
              <input id="password" name="password" type="password" autoComplete="current-password" required
                value={password} onChange={e => setPassword(e.target.value)} disabled={cargando} />
            </div>
          </>)}
          {error && <div className="acceso-error" role="alert"><strong>No se pudo completar el acceso.</strong><p>{error}</p></div>}
          <button className="acceso-primary" type="submit" disabled={ocupado || !disponible}>
            {cargando ? "Ingresando…" : "Iniciar sesión"}{!cargando && <span aria-hidden="true"> →</span>}
          </button>
          {error && <button className="acceso-reintentar" type="button" onClick={reintentar} disabled={ocupado}>Reintentar comprobación de acceso</button>}
          {cargando && <p role="status" className="acceso-status">Validando su acceso…</p>}
        </form>
        <p className="acceso-pie">{demo ? "Seleccione el rol con el que desea explorar NAXJI." : "Utilice una cuenta autorizada por su institución."}</p>
      </div>
      <p className="acceso-firma">NAXJI · Copilot Municipal</p>
    </section>
  </main>;
}
