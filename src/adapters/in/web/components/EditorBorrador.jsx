import { seccionesDelBorrador, tituloDato } from "../services/estructuraBorrador";
import EncabezadoDocumento from "./EncabezadoDocumento";

export function DatoLegible({ valor }) {
  if (valor == null || valor === "") return <span>No registrado</span>;
  if (typeof valor === "boolean") return <span>{valor ? "Sí" : "No"}</span>;
  if (Array.isArray(valor)) return valor.length
    ? <ul>{valor.map((dato, indice) => <li key={indice}><DatoLegible valor={dato} /></li>)}</ul>
    : <span>Ninguno</span>;
  if (typeof valor === "object") return <dl>{Object.entries(valor).map(([clave, dato]) =>
    <div key={clave}><dt><strong>{tituloDato(clave)}</strong></dt><dd><DatoLegible valor={dato} /></dd></div>)}</dl>;
  return <span style={{ whiteSpace: "pre-wrap" }}>{String(valor)}</span>;
}

export default function EditorBorrador({ informe, contenido, onChange, encabezadoOficial, onEncabezadoChange }) {
  const secciones = seccionesDelBorrador(informe);
  const claves = new Set(secciones.map(s => s.clave));
  const adicionales = Object.entries(contenido).filter(([clave]) => clave !== "encabezado" && !claves.has(clave));
  return <>
    <EncabezadoDocumento encabezado={contenido.encabezado} datos={encabezadoOficial} onChange={onEncabezadoChange} />
    {secciones.map(seccion => <div className="form-group" key={seccion.clave}>
      <label htmlFor={`contenido-${seccion.clave}`}>{seccion.titulo}{seccion.obligatoria ? " *" : " (opcional)"}</label>
      <textarea id={`contenido-${seccion.clave}`} rows="6" required={seccion.obligatoria}
        value={contenido[seccion.clave] ?? ""}
        onChange={e => onChange(seccion.clave, e.target.value)} />
    </div>)}
    {adicionales.length > 0 && <details><summary>Datos conservados del documento (solo lectura)</summary>
      {adicionales.map(([clave, valor]) => <section key={clave}><h3>{tituloDato(clave)}</h3><DatoLegible valor={valor} /></section>)}
    </details>}
  </>;
}
