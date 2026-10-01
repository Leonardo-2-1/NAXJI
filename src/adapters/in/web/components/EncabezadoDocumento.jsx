import { camposDelEncabezado, datosOficiales, textoPublico, formatoMdt } from "../services/encabezadoDocumento";

export default function EncabezadoDocumento({ encabezado, datos, onChange }) {
  const valores = datos ?? datosOficiales(encabezado);
  const camposOficiales = camposDelEncabezado(encabezado);
  return <section aria-label="Datos administrativos del documento" className="informe-encabezado">
    <h3>Encabezado administrativo</h3>
    {encabezado?.formato_documento === formatoMdt && <p className="hint-text">Base revisable: Anexo 08 de la Directiva 001-2019-MDT/GM. Confirme destinatario, cargo y ruta al superior inmediato. El emisor se identifica en el código y la firma; el DOCX no incorpora una fila «De». El logotipo vigente y la aprobación de esta adaptación siguen pendientes.</p>}
    {onChange && <p className="hint-text">Complete solo datos oficiales conocidos. Los vacíos se mostrarán como [POR COMPLETAR]. La fecha del documento es distinta de la fecha de inspección. Estos datos se guardan con su edición; Ollama no los redacta.</p>}
    {onChange ? <div className="informe-encabezado-campos">{camposOficiales.map(([clave, etiqueta]) =>
      <div className="form-group" key={clave}><label htmlFor={`oficial-${clave}`}>{etiqueta}</label>
        <input id={`oficial-${clave}`} type={clave === "fecha" ? "date" : "text"}
          maxLength={["referencia", "copias", "anexos"].includes(clave) ? 2000 : 300} value={valores[clave] ?? ""}
          placeholder="[POR COMPLETAR]" onChange={e => onChange(clave, e.target.value)} />
      </div>)}</div> : <dl>{camposOficiales.map(([clave, etiqueta]) =>
        <div key={clave}><dt>{etiqueta}</dt><dd>{valores[clave] || "[POR COMPLETAR]"}</dd></div>)}</dl>}
    <p><strong>Asunto de la solicitud: </strong>{textoPublico(encabezado?.asunto) || "[POR COMPLETAR]"}</p>
  </section>;
}
