import { Component } from "react";

// Si falla la descarga del módulo diferido, conserva una salida recuperable.
export class LimiteCarga extends Component {
  state = { fallo: false };
  static getDerivedStateFromError() { return { fallo: true }; }
  render() {
    return this.state.fallo
      ? <EstadoAcceso error="No se pudo cargar el formulario. Recargue para volver a intentarlo."
        onRetry={() => window.location.reload()} />
      : this.props.children;
  }
}

export default function EstadoAcceso({ error, onRetry, children }) {
  return <main className="estado-acceso">
    <div className="estado-acceso-card">
      <span className="acceso-marca" aria-hidden="true">N</span>
      <h1>{error ? "No pudimos completar el acceso" : "Preparando su espacio"}</h1>
      {error ? <p className="acceso-error" role="alert">{error}</p> : <p role="status">{children}</p>}
      {error && onRetry && <button type="button" className="acceso-primary" onClick={onRetry}>Reintentar</button>}
    </div>
  </main>;
}
