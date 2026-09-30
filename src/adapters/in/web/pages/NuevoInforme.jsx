import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import EditorBorrador from "../components/EditorBorrador";
import { seccionesDePlantilla, validarSeccionesBorrador } from "../services/estructuraBorrador";

import { mensajeError } from "../services/api";
import { puedeElaborar, obtenerUsuarioGuardado } from "../services/authService";
import { obtenerAreas, obtenerCamposPlantilla, obtenerPlantillas, obtenerTiposInforme } from "../services/catalogoService";
import { guardarBorrador, obtenerInforme } from "../services/informeService";
import { generarBorrador, predecirContexto, validarPrediccion, obtenerContexto } from "../services/iaService";
import { actualizarSolicitud, crearSolicitud, obtenerSolicitud, guardarSolicitudCompleta } from "../services/solicitudService";
import {
  armarValores, construirValidacion, crearVigencia, esConfirmada, esEditable, esUUID,
  plantillaCompatible, seleccionInicial, valoresDePlantilla,
} from "../services/flujoInforme";

const INSTRUCCIONES = "Respetar únicamente los datos registrados y la plantilla seleccionada. No presentar como hechos información que no haya sido proporcionada.";
const sinBorde = { border: 0, padding: 0, margin: 0, minWidth: 0 };
const confianza = (valor) => valor == null ? "Confianza no disponible" : `${(valor * 100).toFixed(1)}% de confianza`;
const valoresGuardados = (solicitud) => Object.fromEntries((solicitud.valores || []).map(v => [v.campo_plantilla_id, v.valor]));

function describirError(err, respaldo) {
    return err?.isAxiosError ? mensajeError(err, respaldo) : err.message || respaldo;
  }


// La clave remonta el formulario al navegar a otra solicitud, sin mezclar respuestas.
export default function NuevoInforme() {
  const { search } = useLocation();
  const parametros = new URLSearchParams(search);
  const solicitudId = parametros.get("solicitud");
  return <FormularioInforme key={solicitudId || "nueva"} solicitudId={solicitudId}
    informeInicialId={parametros.get("informe") || ""} />;
}

function FormularioInforme({ solicitudId, informeInicialId }) {
  const elaboracionPermitida = puedeElaborar();
  const [form, setForm] = useState(() => ({
    asunto: "", tipoInformeId: "", areaDestinoId: "", normativaIds: [],
    areaOrigenId: obtenerUsuarioGuardado()?.area_id || "", plantillaId: "", valores: {},
  }));
  const [tipos, setTipos] = useState([]);
  const [areas, setAreas] = useState([]);
  const [solicitud, setSolicitud] = useState(null);
  const [prediccion, setPrediccion] = useState(null);
  const [confirmada, setConfirmada] = useState(false);
  const [asuntoPredicho, setAsuntoPredicho] = useState("");
  const [plantillas, setPlantillas] = useState([]);
  const [campos, setCampos] = useState([]);
  const [idCampos, setIdCampos] = useState("");
  const [estadoPlantillas, setEstadoPlantillas] = useState("pendiente");
  const [avisoPlantilla, setAvisoPlantilla] = useState("");
  const [instrucciones, setInstrucciones] = useState(INSTRUCCIONES);
  const [informe, setInforme] = useState(null);
  const [informeId, setInformeId] = useState(informeInicialId);
  const [contenido, setContenido] = useState({});
  const [titulo, setTitulo] = useState("");
  const [cargando, setCargando] = useState(true);
  const [cargaFallida, setCargaFallida] = useState(false);
  const [operacion, setOperacion] = useState("");
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [vigencia] = useState(crearVigencia);
  const montado = useRef(false);
  const enCurso = useRef(false);
  const solicitudActual = useRef(null);

  const contextoVigente = confirmada && asuntoPredicho === form.asunto.trim();
  const bloqueada = cargando || cargaFallida || !elaboracionPermitida || !esEditable(solicitud) || Boolean(informe);
  const ocupado = Boolean(operacion);

  const cargarFormatos = useCallback(async (actual, anterior, vigente, opciones = {}) => {
    if (!vigente()) return;
    setEstadoPlantillas("cargando");
    setIdCampos("");
    setAvisoPlantilla("");
    try {
      const formatos = (await obtenerPlantillas(actual.tipo_informe_id, opciones))
        .filter(p => plantillaCompatible(p, actual.tipo_informe_id, actual.area_destino_id));
      if (!vigente()) return;
      setPlantillas(formatos);
      const idAnterior = anterior.plantillaId;
      const compatible = formatos.find(p => p.id === idAnterior);
      if (!compatible) {
        setCampos([]);
        setForm(prev => ({ ...prev, plantillaId: "", valores: {} }));
        if (idAnterior) setAvisoPlantilla("La plantilla anterior ya no es compatible o está inactiva. Seleccione otra plantilla; sus campos no se trasladarán a otro formato.");
      } else {
        const camposActuales = await obtenerCamposPlantilla(compatible.id, opciones);
        if (!vigente()) return;
        setCampos(camposActuales.filter(c => c.activo));
        setIdCampos(compatible.id);
        setForm(prev => ({ ...prev, plantillaId: compatible.id, valores: valoresDePlantilla(camposActuales, anterior.valores) }));
      }
      if (vigente()) setEstadoPlantillas("listo");
    } catch (err) {
      if (vigente()) {
        setEstadoPlantillas("error");
        setAvisoPlantilla(describirError(err, "No se pudieron cargar las plantillas o sus campos."));
      }
    }
  }, []);

  useEffect(() => {
    let activo = true;
    montado.current = true;
    const controller = new AbortController();
    const opciones = { signal: controller.signal };
    async function recuperar() {
      try {
        if (solicitudId && !esUUID(solicitudId)) throw new Error("El identificador de solicitud no es un UUID válido.");
        const [listaTipos, listaAreas] = await Promise.all([obtenerTiposInforme(opciones), obtenerAreas(opciones)]);
        if (!activo) return;
        setTipos(listaTipos);
        setAreas(listaAreas);
        if (!solicitudId) return;
        const [actual, contexto] = await Promise.all([obtenerSolicitud(solicitudId, opciones), obtenerContexto(solicitudId, opciones)]);
        if (!activo) return;
        solicitudActual.current = actual;
        setSolicitud(actual);
        const seleccion = seleccionInicial(actual, contexto);
        const datos = {
          asunto: actual.asunto, ...seleccion, areaOrigenId: actual.area_origen_id || "",
          plantillaId: actual.plantilla_id || "", valores: valoresGuardados(actual),
        };
        setForm(datos);
        setPrediccion(contexto);
        setConfirmada(esConfirmada(contexto));
        setAsuntoPredicho(contexto ? actual.asunto.trim() : "");
        setMensaje("Solicitud recuperada. Se conserva el contexto confirmado y los datos compatibles.");
        if (esConfirmada(contexto)) {
          await cargarFormatos(actual, datos, () => activo, opciones);
        }
        if (activo && actual.estado === "GENERADA" && informeInicialId) {
          try {
            const borrador = await obtenerInforme(informeInicialId);
            if (borrador.solicitud_id !== actual.id) throw new Error("El informe no pertenece a esta solicitud.");
            if (activo) mostrarInforme(borrador);
          } catch (err) {
            if (activo) setError(describirError(err, "No se pudo recuperar el borrador. Puede volver a abrirlo por su ID."));
          }
        }
      } catch (err) {
        if (activo) {
          setCargaFallida(true);
          setError(describirError(err, "No se pudo recuperar la solicitud o los catálogos. Recargue para reintentar."));
        }
      } finally {
        if (activo) setCargando(false);
      }
    }
    recuperar();
    return () => {
      activo = false;
      montado.current = false;
      vigencia.invalidar();
      controller.abort();
    };
  }, [solicitudId, informeInicialId, vigencia, cargarFormatos]);


  function recordar(actual, borradorId) {
    if (!montado.current) return;
    solicitudActual.current = actual;
    setSolicitud(actual);
    const url = new URL(window.location.href);
    url.searchParams.set("solicitud", actual.id);
    if (borradorId) url.searchParams.set("informe", borradorId);
    // Mantiene la solicitud recién creada sin remontar el componente a mitad de un POST.
    window.history.replaceState(window.history.state, "", url);
  }

  function mostrarInforme(actual) {
    setInforme(actual);
    setInformeId(actual.informe_id);
    setTitulo(actual.titulo || "");
    setContenido(actual.contenido || {});
  }


  // Serializa escrituras: una edición invalida su resultado, pero no crea POST concurrentes.
  async function ejecutar(nombre, tarea) {
    if (enCurso.current || !montado.current) return;
    enCurso.current = true;
    const actual = vigencia.capturar();
    const vigente = () => montado.current && actual();
    setOperacion(nombre);
    setError("");
    setMensaje("");
    try {
      await tarea(vigente);
    } catch (err) {
      if (vigente()) setError(describirError(err, "No se pudo completar la operación. Intente nuevamente."));
    } finally {
      enCurso.current = false;
      if (montado.current) setOperacion("");
    }
  }

  function cambiarAsunto(valor) {
    vigencia.invalidar();
    setForm(prev => ({ ...prev, asunto: valor }));
    setPrediccion(null);
    setConfirmada(false);
    setAsuntoPredicho("");
    setError("");
    setMensaje("El asunto cambió. Analícelo y confirme una nueva propuesta antes de generar.");
  }

  function cambiarContexto(cambios) {
    vigencia.invalidar();
    setForm(prev => ({ ...prev, ...cambios }));
    setConfirmada(false);
    setError("");
    setMensaje("Hay cambios en el contexto. Confirme nuevamente para continuar.");
  }

  function analizar() {
    if (bloqueada || ocupado) return;
    if (!form.asunto.trim()) { setError("Escriba el asunto para analizarlo."); return; }
    vigencia.invalidar();
    setPrediccion(null);
    setConfirmada(false);
    const asunto = form.asunto.trim();
    ejecutar("analizar", async vigente => {
      const existente = solicitudActual.current;
      const actual = existente
        ? await actualizarSolicitud(existente.id, { asunto })
        : await crearSolicitud({ asunto });
      // Retiene el ID aunque el usuario haya editado durante la creación: evita duplicados.
      recordar(actual);
      if (!vigente()) return;
      const resultado = await predecirContexto(actual.id);
      if (!vigente()) return;
      setPrediccion(resultado);
      setAsuntoPredicho(asunto);
      setForm(prev => ({ ...prev, ...seleccionInicial(actual, resultado) }));
      setMensaje("Revise el tipo, el área y las normas sugeridas antes de confirmar.");
    });
  }

  function confirmar(rechazar = false) {
    if (bloqueada || ocupado || !prediccion || asuntoPredicho !== form.asunto.trim()) return;
    let datos;
    try { datos = construirValidacion(prediccion, form, rechazar); }
    catch (err) { setError(err.message); return; }
    ejecutar("confirmar", async vigente => {
      const respuesta = await validarPrediccion(solicitudActual.current.id, prediccion, form, rechazar);
      if (!vigente()) return;
      const actual = await obtenerSolicitud(solicitudActual.current.id);
      if (!vigente()) return;
      recordar(actual);
      setPrediccion(respuesta);
      setConfirmada(esConfirmada(respuesta));
      if (rechazar) {
        setMensaje("Propuesta rechazada. Analice nuevamente o confirme una selección válida para continuar.");
        return;
      }
      setForm(prev => ({ ...prev, ...seleccionInicial(actual, respuesta) }));
      setMensaje(datos.resultado === "ACEPTADA" ? "Propuesta completa confirmada." : "Correcciones y selección de normas confirmadas.");
      await cargarFormatos(actual, form, vigente);
    });
  }

  function cambiarPlantilla(id) {
    if (ocupado || bloqueada) return;
    setForm(prev => ({ ...prev, plantillaId: id, valores: {} }));
    setIdCampos("");
    setCampos([]);
    setAvisoPlantilla("");
    if (!id) return;
    ejecutar("campos", async vigente => {
      const nuevos = await obtenerCamposPlantilla(id);
      if (!vigente()) return;
      const actual = solicitudActual.current;
      const guardados = actual?.plantilla_id === id ? valoresGuardados(actual) : {};
      setCampos(nuevos.filter(c => c.activo));
      setIdCampos(id);
      setForm(prev => ({ ...prev, valores: valoresDePlantilla(nuevos, guardados) }));
    });
  }

  async function persistirDatos() {
    if (!contextoVigente) throw new Error("Analice el asunto y confirme el contexto antes de guardar o generar.");
    if (!form.areaOrigenId) throw new Error("Seleccione el área de origen.");
    if (idCampos !== form.plantillaId || estadoPlantillas !== "listo" || !plantillas.some(p => p.id === form.plantillaId)) {
      throw new Error("Seleccione una plantilla compatible.");
    }
    // Los campos deben haberse cargado, incluso si una plantilla no tiene obligatorios.
    for (const campo of campos) {
      const valor = form.valores[campo.id];
      if (campo.obligatorio && (valor == null || (typeof valor === "string" && !valor.trim()))) {
        throw new Error(`Complete el campo obligatorio: ${campo.etiqueta}.`);
      }
    }
    const actual = await guardarSolicitudCompleta(solicitudActual.current.id, {
      asunto: form.asunto.trim(), tipo_informe_id: form.tipoInformeId,
      area_destino_id: form.areaDestinoId, area_origen_id: form.areaOrigenId,
      plantilla_id: form.plantillaId, valores: armarValores(campos, form.valores),
    });
    recordar(actual);
    return actual;
  }

  function guardarDatos() {
    if (bloqueada || !contextoVigente) return;
    ejecutar("guardar", async vigente => {
      await persistirDatos();
      if (vigente()) setMensaje("Datos guardados correctamente.");
    });
  }

  function generar() {
    if (bloqueada || !contextoVigente) return;
    ejecutar("generar", async vigente => {
      const actual = await persistirDatos();
      if (!vigente()) return;
      const resultado = await generarBorrador(actual.id, instrucciones.trim() || INSTRUCCIONES);
      if (!vigente()) return;
      mostrarInforme(resultado);
      recordar({ ...actual, estado: "GENERADA" }, resultado.informe_id);
      setMensaje("Borrador generado. Puede editarlo y guardar una nueva versión.");
    });
  }

  function guardarEdicion() {
    if (!elaboracionPermitida || informe?.estado !== "BORRADOR") return;
    ejecutar("editar", async vigente => {
      validarSeccionesBorrador(informe, contenido);
      const resultado = await guardarBorrador(informe.informe_id, contenido, informe.numero_version, titulo);
      if (!vigente()) return;
      mostrarInforme(resultado);
      setMensaje(`Borrador guardado. Versión ${resultado.numero_version}.`);
    });
  }

  function abrirInforme() {
    if (!esUUID(informeId)) { setError("Ingrese un UUID de informe válido."); return; }
    ejecutar("abrir", async vigente => {
      const resultado = await obtenerInforme(informeId);
      if (!vigente()) return;
      if (resultado.solicitud_id !== solicitud.id) throw new Error("El informe no pertenece a esta solicitud.");
      mostrarInforme(resultado);
      recordar(solicitud, resultado.informe_id);
    });
  }

  function renderCampo(campo) {
    const props = {
      id: `campo-${campo.id}`, value: form.valores[campo.id] ?? "",
      onChange: e => setForm(prev => ({ ...prev, valores: { ...prev.valores, [campo.id]: e.target.value } })),
    };
    if (campo.tipo_dato === "textarea") return <textarea {...props} rows="4" />;
    if (campo.tipo_dato === "select") return <select {...props}>
      <option value="">Seleccione</option>
      {(campo.configuracion?.opciones || []).map(opcion => <option key={opcion} value={opcion}>{opcion}</option>)}
    </select>;
    if (campo.tipo_dato === "boolean") return <input id={props.id} type="checkbox"
      checked={Boolean(form.valores[campo.id])}
      onChange={e => setForm(prev => ({ ...prev, valores: { ...prev.valores, [campo.id]: e.target.checked } }))} />;
    return <input {...props} type={campo.tipo_dato === "number" ? "number" : campo.tipo_dato === "date" ? "date" : "text"}
      step={campo.tipo_dato === "number" ? "any" : undefined} />;
  }

  let modoConfirmacion = "ACEPTADA";
  try { modoConfirmacion = construirValidacion(prediccion, form).resultado; }
  catch { /* Una propuesta incompleta se puede completar con los catálogos. */ }

  return <div className="nuevo-informe-page">
    <div className="page-title"><h1>Nuevo informe</h1><p>Asunto → sugerencia y confirmación → plantilla y datos → borrador</p></div>
    {!elaboracionPermitida && <p className="warning-message">Su rol solo permite consultar. Use un funcionario o administrador para elaborar.</p>}
    {cargando && <p role="status">Recuperando catálogos y solicitud…</p>}
    {ocupado && <p role="status">{({ analizar: "Analizando asunto…", confirmar: "Confirmando contexto…", campos: "Cargando campos…", guardar: "Guardando datos…", generar: "Generando borrador…", editar: "Guardando borrador…", abrir: "Recuperando borrador…" })[operacion]}</p>}
    {error && <div className="error-message" role="alert">{error}</div>}
    {cargaFallida && <button type="button" onClick={() => window.location.reload()}>Reintentar carga</button>}
    {mensaje && <div className="success-message" role="status">{mensaje}</div>}
    {solicitud && <p>Solicitud: <code>{solicitud.id}</code> · Estado: {solicitud.estado}</p>}
    {solicitud && !esEditable(solicitud) && <p className="warning-message">Esta solicitud está en estado {solicitud.estado} y sus datos no admiten cambios.</p>}

    <section className="card" aria-labelledby="etapa-asunto">
      <h2 id="etapa-asunto">1. Asunto</h2>
      <p className="card-help">Escriba el asunto para obtener una sugerencia. El tipo, destino y plantilla se eligen después.</p>
      <label htmlFor="asunto">Asunto *</label>
      <input id="asunto" type="text" value={form.asunto} onChange={e => cambiarAsunto(e.target.value)}
        disabled={bloqueada || (ocupado && !["analizar", "confirmar"].includes(operacion))} />
      <button type="button" className="btn-primary" disabled={bloqueada || ocupado || !form.asunto.trim()} onClick={analizar}>Analizar asunto</button>
    </section>

    <section className="card" aria-labelledby="etapa-contexto">
      <h2 id="etapa-contexto">2. Sugerencia y confirmación</h2>
      {!prediccion ? <p>Analice el asunto para revisar la propuesta.</p> : <>
        {prediccion.advertencias?.map((aviso, indice) => <p className="warning-inline" role="alert" key={indice}>{aviso}</p>)}
        {prediccion.es_mock && <p className="warning-inline">Predicción de demostración; no corresponde al modelo real.</p>}
        <p><strong>Tipo sugerido:</strong> {prediccion.tipo_informe?.nombre || "No disponible"} · {confianza(prediccion.tipo_informe?.confianza)}</p>
        <p><strong>Área sugerida:</strong> {prediccion.area_destino?.nombre || "No disponible"} · {confianza(prediccion.area_destino?.confianza)}</p>
        <p>Modelo: {prediccion.modelo} · {prediccion.version_modelo}</p>
        <p>Validación guardada: {prediccion.resultado_validacion}. {contextoVigente ? "Contexto confirmado." : "Confirmación pendiente para continuar."}</p>
        <fieldset disabled={bloqueada || ocupado} style={sinBorde}>
          <div className="form-group"><label htmlFor="tipo-informe">Tipo de informe a confirmar *</label>
            <select id="tipo-informe" value={form.tipoInformeId} onChange={e => cambiarContexto({ tipoInformeId: e.target.value })}>
              <option value="">Seleccione un tipo</option>
              {tipos.map(tipo => <option key={tipo.id} value={tipo.id}>{tipo.nombre}</option>)}
            </select>
          </div>
          <div className="form-group"><label htmlFor="area-destino">Área de destino a confirmar *</label>
            <select id="area-destino" value={form.areaDestinoId} onChange={e => cambiarContexto({ areaDestinoId: e.target.value })}>
              <option value="">Seleccione un área</option>
              {areas.map(area => <option key={area.id} value={area.id}>{area.nombre}</option>)}
            </select>
          </div>
          <fieldset><legend>Normas propuestas que confirma</legend>
            {!prediccion.normativas?.length && <p>La API no propuso normas para este asunto.</p>}
            {prediccion.normativas?.map(norma => <div key={norma.normativa_id}>
              <label className="checkbox-field"><input type="checkbox" checked={form.normativaIds.includes(norma.normativa_id)}
                onChange={e => cambiarContexto({ normativaIds: e.target.checked
                  ? [...form.normativaIds, norma.normativa_id] : form.normativaIds.filter(id => id !== norma.normativa_id) })} />
                {norma.codigo ? `${norma.codigo} — ` : ""}{norma.titulo} · {confianza(norma.confianza)}
              </label>
            </div>)}
          </fieldset>
          <p>Puede desmarcar normas propuestas. No se agregan normas externas a esta predicción.</p>
          <div className="btn-row">
            <button type="button" className="btn-primary" disabled={contextoVigente || !form.tipoInformeId || !form.areaDestinoId} onClick={() => confirmar()}>
              {modoConfirmacion === "ACEPTADA" ? "Aceptar propuesta" : "Confirmar correcciones"}
            </button>
            <button type="button" className="btn-danger" onClick={() => confirmar(true)}>Rechazar propuesta</button>
          </div>
        </fieldset>
      </>}
    </section>

    <section className="card" aria-labelledby="etapa-datos">
      <h2 id="etapa-datos">3. Plantilla y datos</h2>
      {!contextoVigente ? <p>Confirme el contexto para seleccionar la plantilla y completar sus datos.</p> : <>
        {estadoPlantillas === "cargando" && <p role="status">Cargando plantillas compatibles y campos…</p>}
        {avisoPlantilla && <p className="warning-message" role="alert">{avisoPlantilla}</p>}
        {estadoPlantillas === "error" && <button type="button" disabled={ocupado}
          onClick={() => ejecutar("campos", vigente => cargarFormatos(solicitudActual.current, form, vigente))}>Reintentar plantillas</button>}
        {estadoPlantillas === "listo" && !plantillas.length && <p className="warning-message" role="status">No hay una plantilla activa compatible con el tipo y el área confirmados. No se puede generar todavía.</p>}
        <fieldset disabled={bloqueada || ocupado || estadoPlantillas !== "listo"} style={sinBorde}>
          <div className="form-group"><label htmlFor="plantilla">Plantilla *</label>
            <select id="plantilla" value={form.plantillaId} onChange={e => cambiarPlantilla(e.target.value)}>
              <option value="">Seleccione una plantilla</option>
              {plantillas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
            <p className="card-help">{plantillas.find(p => p.id === form.plantillaId)?.descripcion}</p>
            {form.plantillaId && <div>
              <p>Secciones del borrador resultante:</p>
              <ol>{seccionesDePlantilla(plantillas.find(p => p.id === form.plantillaId)).map(seccion =>
                <li key={seccion.clave}>{seccion.titulo}{seccion.obligatoria ? " (obligatoria)" : " (opcional)"}</li>)}</ol>
              <p className="card-help">Los campos siguientes son los datos de entrada para elaborarlo.</p>
            </div>}
          </div>
          <div className="form-group"><label htmlFor="area-origen">Área de origen *</label>
            <select id="area-origen" value={form.areaOrigenId} onChange={e => setForm(prev => ({ ...prev, areaOrigenId: e.target.value }))}>
              <option value="">Seleccione un área</option>
              {areas.map(area => <option key={area.id} value={area.id}>{area.nombre}</option>)}
            </select>
          </div>
          {form.plantillaId && idCampos !== form.plantillaId && !ocupado && <button type="button" onClick={() => cambiarPlantilla(form.plantillaId)}>Reintentar carga de campos</button>}
          {campos.map(campo => <div className="form-group" key={campo.id}>
            <label htmlFor={`campo-${campo.id}`}>{campo.etiqueta}{campo.obligatorio ? " *" : ""}</label>{renderCampo(campo)}
          </div>)}
          <button type="button" className="btn-primary" disabled={!form.plantillaId || idCampos !== form.plantillaId} onClick={guardarDatos}>Guardar datos</button>
        </fieldset>
      </>}
    </section>

    <section className="card" aria-labelledby="etapa-borrador">
      <h2 id="etapa-borrador">4. Borrador</h2>
      {!informe && solicitud?.estado !== "GENERADA" && <fieldset disabled={bloqueada || ocupado || !contextoVigente || estadoPlantillas !== "listo" || !form.plantillaId || idCampos !== form.plantillaId} style={sinBorde}>
        <p>Complete la plantilla y los datos requeridos para generar. Se guardarán antes de llamar al generador.</p>
        <label htmlFor="instrucciones">Instrucciones para el generador</label>
        <textarea id="instrucciones" rows="4" value={instrucciones} onChange={e => setInstrucciones(e.target.value)} />
        <button type="button" className="btn-primary" onClick={generar}>Generar borrador estructurado</button>
      </fieldset>}
      {!informe && solicitud?.estado === "GENERADA" && <div>
        <p>Esta solicitud ya tiene un informe. Para recuperarlo, abra su enlace guardado o ingrese el ID del informe.</p>
        <label htmlFor="informe-id">ID del informe</label>
        <input id="informe-id" value={informeId} onChange={e => setInformeId(e.target.value)} disabled={ocupado} />
        <button type="button" onClick={abrirInforme} disabled={ocupado}>Abrir borrador</button>
      </div>}
      {informe && <fieldset disabled={ocupado || !elaboracionPermitida || informe.estado !== "BORRADOR"} style={sinBorde}>
        <p>Informe: <code>{informe.informe_id}</code> · Estado: {informe.estado} · Versión: {informe.numero_version}</p>
        <div className="form-group"><label htmlFor="titulo">Título</label>
          <input id="titulo" value={titulo} onChange={e => setTitulo(e.target.value)} />
        </div>
        <EditorBorrador informe={informe} contenido={contenido}
          onChange={(clave, valor) => setContenido(prev => ({ ...prev, [clave]: valor }))} />
        <button type="button" className="btn-primary" onClick={guardarEdicion}>Guardar borrador</button>
      </fieldset>}
    </section>
  </div>;
}
