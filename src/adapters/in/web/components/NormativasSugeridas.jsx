function confianzaTema(valor) {
  return Number.isFinite(valor) ? `${Math.round(valor * 100)} %` : "no disponible";
}

function fuenteSegura(url) {
  try { return new URL(url).protocol === "https:"; }
  catch { return false; }
}

export default function NormativasSugeridas({ prediccion, seleccionadas, onChange }) {
  return <>
    {!!prediccion.temas_normativos?.length && <div>
      <p><strong>Temas identificados por el modelo</strong></p>
      <ul>{prediccion.temas_normativos.map(tema => <li key={tema.codigo}>
        {tema.etiqueta} ({tema.codigo}) · Confianza temática: {confianzaTema(tema.confianza)}
        {!tema.normativa_ids.length && <p className="warning-inline">Solo se identificó el tema. No hay una norma verificable asociada; revisión documental pendiente.</p>}
      </li>)}</ul>
    </div>}
    <fieldset><legend>Referencias normativas propuestas que confirma</legend>
      <p>La confianza del modelo mide afinidad temática; no acredita vigencia ni aplicabilidad jurídica.
        Aceptar una referencia requiere revisión humana para este caso. Su contenido jurídico no ha sido verificado por el generador.</p>
      {!prediccion.normativas?.length && <p>No hay documentos normativos verificables propuestos para este asunto.</p>}
      {prediccion.normativas?.map(norma => <div key={norma.normativa_id}>
        <label className="checkbox-field"><input type="checkbox" checked={seleccionadas.includes(norma.normativa_id)}
          onChange={e => onChange(e.target.checked ? [...seleccionadas, norma.normativa_id]
            : seleccionadas.filter(id => id !== norma.normativa_id))} />
          {norma.codigo ? `${norma.codigo} — ` : ""}{norma.titulo} · Afinidad temática: {confianzaTema(norma.confianza)}
        </label>
        {!norma.correspondencias?.length && <p className="warning-inline">Propuesta anterior o de demostración sin evidencia de correspondencia documental. Revisión pendiente.</p>}
        {norma.correspondencias?.map(c => <div key={c.etiqueta} className="card-help">
          <p>Tema: {c.etiqueta}. Revisión documental: {c.verificado_en}. Vigencia registrada en la fuente: {c.vigencia}.</p>
          <p>Ámbito: {c.ambito}</p><p>Relación temática: {c.justificacion}</p>
          {fuenteSegura(c.fuente_url) && <a href={c.fuente_url} target="_blank" rel="noreferrer">Documento oficial</a>}
          {" · "}
          {fuenteSegura(c.fuente_vigencia_url) && <a href={c.fuente_vigencia_url} target="_blank" rel="noreferrer">Fuente de vigencia consultada</a>}
        </div>)}
      </div>)}
    </fieldset>
  </>;
}
