import EncabezadoDocumento from "./EncabezadoDocumento";
import { seccionesDelBorrador } from "../services/estructuraBorrador";
import { formatoMdt } from "../services/encabezadoDocumento";

export default function VistaPreviaInforme({ informe }) {
  const municipal = informe.contenido.encabezado?.formato_documento === formatoMdt;
  return <article className="informe-documento" aria-label={`Vista previa de la versión ${informe.numero_version}`}>
    <header><p className="informe-eyebrow">FORMATO WORD PILOTO NAXJI</p>
      <h2>{informe.titulo || "Informe"}</h2>
      <p>No es un formato institucional aprobado. Borrador sujeto a revisión humana.</p>
      {municipal && <p>Adaptación del Anexo 08 municipal de 2019. Vista del contenido guardado; descargue el DOCX para revisar márgenes y paginación. Su cuerpo se exporta sin títulos de apartados.</p>}
      <p>Versión guardada {informe.numero_version}</p>
      <p>{informe.plantilla_nombre || "Plantilla histórica"} · Versión de plantilla {informe.plantilla_version ?? "no registrada"}</p>
      {informe.titulo_versionado === false && <p>Versión anterior sin título propio guardado. Se muestra el título actual del informe.</p>}
    </header>
    <EncabezadoDocumento encabezado={informe.contenido.encabezado} />
    {seccionesDelBorrador(informe).map(s => <section key={s.clave}>
      <h3>{s.titulo}</h3><p className="informe-texto-guardado">{informe.contenido[s.clave] ?? ""}</p>
    </section>)}
  </article>;
}
