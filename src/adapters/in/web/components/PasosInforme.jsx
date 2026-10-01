const PASOS = [
  ["Asunto", "Defina qué necesita"],
  ["Confirmación", "Revise la sugerencia"],
  ["Plantilla y datos", "Complete la información"],
  ["Borrador", "Genere y revise"],
];

export default function PasosInforme({ actual, disponible, disabled, onChange }) {
  return <nav className="informe-pasos" aria-label="Pasos para crear el informe">
    <ol>{PASOS.map(([titulo, ayuda], indice) => {
      const paso = indice + 1;
      const pendiente = paso > disponible;
      const estado = paso === actual ? "actual" : pendiente ? "pendiente" : paso < disponible ? "completo" : "disponible";
      return <li key={titulo} data-estado={estado}>
        <button type="button" disabled={disabled || pendiente} aria-current={paso === actual ? "step" : undefined}
          aria-controls={`panel-paso-${paso}`} onClick={() => onChange(paso)}>
          <span className="paso-numero" aria-hidden="true">{estado === "completo" ? "✓" : `0${paso}`}</span>
          <span className="paso-texto"><strong>{titulo}</strong><span>{ayuda}</span>
            <small>{estado === "actual" ? "Paso actual" : pendiente ? "Pendiente" : estado === "completo" ? "Completado · Revisar" : "Disponible"}</small>
          </span>
        </button>
      </li>;
    })}</ol>
  </nav>;
}
