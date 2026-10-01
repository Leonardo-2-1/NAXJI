import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import EditorBorrador from "../components/EditorBorrador";
import NormativasSugeridas from "../components/NormativasSugeridas";
import PasosInforme from "../components/PasosInforme";
import { progresoInforme } from "../services/progresoInforme";
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
  const [pasoElegido, setPasoElegido] = useState(null);
  const [vigencia] = useState(crearVigencia);
  const montado = useRef(false);
  const enCurso = useRef(false);
  const solicitudActual = useRef(null);

  const contextoVigente = confirmada && asuntoPredicho === form.asunto.trim();
  const bloqueada = cargando || cargaFallida || !elaboracionPermitida || !esEditable(solicitud) || Boolean(informe);
  const ocupado = Boolean(operacion);
  const progreso = progresoInforme({ form, prediccion, contextoVigente, asuntoPredicho,
    plantillas, campos, idCampos, estadoPlantillas, solicitud, informe });
  const pasoDisponible = cargando || cargaFallida ? 1 : progreso.pasoDisponible;
  const pasoActual = Math.min(pasoElegido ?? pasoDisponible, pasoDisponible);
  const titulosPasos = ["Cuéntenos qué necesita", "Revise y confirme la propuesta", "Elija la plantilla y complete los datos", "Revise su borrador"];
  const encabezadoPaso = useRef(null);

  useEffect(() => {
    if (!cargando) encabezadoPaso.current?.focus();
  }, [pasoActual, cargando]);

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
    setPasoElegido(1);
    vigencia.invalidar();
    setForm(prev => ({ ...prev, asunto: valor }));
    setPrediccion(null);
    setConfirmada(false);
    setAsuntoPredicho("");
    setError("");
    setMensaje("El asunto cambió. Analícelo y confirme una nueva propuesta antes de generar.");
  }

  function cambiarContexto(cambios) {
    setPasoElegido(2);
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
      setPasoElegido(2);
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
      setPasoElegido(3);
      setMensaje(datos.resultado === "ACEPTADA" ? "Propuesta completa confirmada." : "Correcciones y selección de normas confirmadas.");
      await cargarFormatos(actual, form, vigente);
    });
  }

  function cambiarPlantilla(id) {
    if (ocupado || bloqueada) return;
    setPasoElegido(3);
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
      if (vigente()) {
        setMensaje("Datos guardados correctamente. Ya puede generar el borrador.");
        setPasoElegido(4);
      }
    });
  }

  function generar() {
    if (bloqueada || !contextoVigente) return;
    ejecutar("generar", async vigente => {
      const actual = await persistirDatos();
      if (!vigente()) return;
      await solicitarBorrador(actual, vigente);
    });
  }

  async function solicitarBorrador(actual, vigente) {
    try {
      const resultado = await generarBorrador(actual.id, instrucciones.trim() || INSTRUCCIONES);
      if (!vigente()) return;
      mostrarInforme(resultado);
      recordar({ ...actual, estado: "GENERADA" }, resultado.informe_id);
      setMensaje("Borrador generado. Puede editarlo y guardar una nueva versión.");
    } catch (err) {
      // Si el cliente perdió conexión, el backend puede continuar PROCESANDO.
      try {
        const recuperada = await obtenerSolicitud(actual.id);
        if (vigente()) recordar(recuperada);
      } catch { /* Mantiene el error original; el enlace permite recuperar después. */ }
      throw err;
    }
  }

  function reintentarGeneracion() {
    if (!elaboracionPermitida || ocupado || solicitud?.estado !== "PROCESANDO") return;
    ejecutar("generar", vigente => solicitarBorrador(solicitudActual.current, vigente));
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
      required: campo.obligatorio,
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
    <div className="informe-intro">
      <div><p className="informe-eyebrow">ESPACIO DE ELABORACIÓN</p>
        <h1>Un informe, paso a paso.</h1>
        <p>Empiece con el asunto. Revise la propuesta y transforme sus datos en un borrador.</p>
      </div>
      <span className="informe-insignia"><span aria-hidden="true">✦</span> Asistencia con IA · Revisión humana</span>
    </div>
    <PasosInforme actual={pasoActual} disponible={pasoDisponible} disabled={cargando || cargaFallida || ocupado}
      onChange={setPasoElegido} />
    <div className="informe-avisos">
    {!elaboracionPermitida && <p className="warning-message">Su rol solo permite consultar. Use un funcionario o administrador para elaborar.</p>}
    {cargando && <p className="informe-carga" role="status">Recuperando catálogos y solicitud…</p>}
    {ocupado && <p className="informe-carga" role="status">{({ analizar: "Analizando asunto…", confirmar: "Confirmando contexto…", campos: "Cargando campos…", guardar: "Guardando datos…", generar: "Generando borrador… Puede tardar unos minutos.", editar: "Guardando borrador…", abrir: "Recuperando borrador…" })[operacion]}</p>}
    {error && <div className="error-message" role="alert">{error}</div>}
    {cargaFallida && <button type="button" className="btn-secondary" onClick={() => window.location.reload()}>Reintentar carga</button>}
    {mensaje && <div className="success-message" role="status">{mensaje}</div>}
    {solicitud && !esEditable(solicitud) && <p className="warning-message">Esta solicitud está en estado {solicitud.estado} y sus datos no admiten cambios.</p>}
    </div>

    <div className="informe-espacio">
    <div className="informe-trabajo">
    <div className="informe-card-heading">
      <p className="informe-eyebrow">PASO {pasoActual} DE 4</p>
      <h2 tabIndex={-1} ref={encabezadoPaso} id="titulo-paso">{titulosPasos[pasoActual - 1]}</h2>
      <p>Los campos marcados con * son obligatorios.</p>
    </div>
    <section id="panel-paso-1" className="informe-panel" hidden={pasoActual !== 1} aria-labelledby="titulo-paso">
      <p className="card-help">Describa el propósito del informe. Con el asunto es suficiente para comenzar; elegirá el tipo, el destino y la plantilla después.</p>
      <div className="form-group"><label htmlFor="asunto">Asunto *</label>
      <textarea id="asunto" rows="4" required value={form.asunto} onChange={e => cambiarAsunto(e.target.value)}
        aria-describedby="ayuda-asunto" placeholder="Escriba aquí el asunto de su informe…"
        disabled={bloqueada || (ocupado && !["analizar", "confirmar"].includes(operacion))} />
      <p id="ayuda-asunto" className="hint-text">Incluya solo información que conozca. Podrá aportar más detalles en el paso de datos.</p></div>
      <div className="informe-nota"><strong>Usted decide.</strong><p>La sugerencia del modelo es un punto de partida. Revísela y confírmela antes de continuar.</p></div>
      <div className="informe-acciones"><button type="button" className="btn-primary" disabled={bloqueada || ocupado || !form.asunto.trim()} onClick={analizar}>{operacion === "analizar" ? "Analizando asunto…" : "Analizar asunto"}<span aria-hidden="true"> →</span></button></div>
    </section>

    <section id="panel-paso-2" className="informe-panel" hidden={pasoActual !== 2} aria-labelledby="titulo-paso">
      {!prediccion ? <p>Analice el asunto para revisar la propuesta.</p> : <>
        <p className="card-help">Compruebe la sugerencia, ajuste el tipo y el área si es necesario, y elija las normas que desea confirmar.</p>
        {prediccion.advertencias?.map((aviso, indice) => <p className="warning-inline" role="alert" key={indice}>{aviso}</p>)}
        {prediccion.es_mock && <p className="warning-inline">Predicción de demostración; no corresponde al modelo real.</p>}
        <div className="informe-sugerencias">
          <div><span>Tipo sugerido</span><strong>{prediccion.tipo_informe?.nombre || "No disponible"}</strong><small>{confianza(prediccion.tipo_informe?.confianza)}</small></div>
          <div><span>Área sugerida</span><strong>{prediccion.area_destino?.nombre || "No disponible"}</strong><small>{confianza(prediccion.area_destino?.confianza)}</small></div>
        </div>
        <p className="hint-text">Modelo: {prediccion.modelo} · {prediccion.version_modelo}. Validación guardada: {prediccion.resultado_validacion}.</p>
        <p className={contextoVigente ? "informe-confirmado" : "card-help"}>{contextoVigente ? "✓ Contexto confirmado. Puede continuar a la plantilla." : "Confirmación pendiente para continuar."}</p>
        <fieldset disabled={bloqueada || ocupado} style={sinBorde}>
          <div className="informe-form-grid">
          <div className="form-group"><label htmlFor="tipo-informe">Tipo de informe a confirmar *</label>
            <select id="tipo-informe" required value={form.tipoInformeId} onChange={e => cambiarContexto({ tipoInformeId: e.target.value })}>
              <option value="">Seleccione un tipo</option>
              {tipos.map(tipo => <option key={tipo.id} value={tipo.id}>{tipo.nombre}</option>)}
            </select>
          </div>
          <div className="form-group"><label htmlFor="area-destino">Área de destino a confirmar *</label>
            <select id="area-destino" required value={form.areaDestinoId} onChange={e => cambiarContexto({ areaDestinoId: e.target.value })}>
              <option value="">Seleccione un área</option>
              {areas.map(area => <option key={area.id} value={area.id}>{area.nombre}</option>)}
            </select>
          </div>
          </div>
          <div className="informe-normativas">
          <NormativasSugeridas prediccion={prediccion} seleccionadas={form.normativaIds}
            onChange={normativaIds => cambiarContexto({ normativaIds })} />
          <p className="hint-text">Puede desmarcar normas propuestas. No se agregan normas externas a esta predicción.</p>
          </div>
          <div className="informe-acciones">
            <button type="button" className="btn-danger" onClick={() => confirmar(true)}>Rechazar propuesta</button>
            <button type="button" className="btn-primary" disabled={contextoVigente || !form.tipoInformeId || !form.areaDestinoId} onClick={() => confirmar()}>
              {modoConfirmacion === "ACEPTADA" ? "Aceptar propuesta" : "Confirmar correcciones"}
            </button>
          </div>
        </fieldset>
      </>}
    </section>

    <section id="panel-paso-3" className="informe-panel" hidden={pasoActual !== 3} aria-labelledby="titulo-paso">
      {!contextoVigente ? <p>Confirme el contexto para seleccionar la plantilla y completar sus datos.</p> : <>
        <p className="card-help">La plantilla define la estructura del documento. Complete los datos que servirán para redactarlo.</p>
        {estadoPlantillas === "cargando" && <p role="status">Cargando plantillas compatibles y campos…</p>}
        {avisoPlantilla && <p className="warning-message" role="alert">{avisoPlantilla}</p>}
        {estadoPlantillas === "error" && <button type="button" className="btn-secondary" disabled={ocupado}
          onClick={() => ejecutar("campos", vigente => cargarFormatos(solicitudActual.current, form, vigente))}>Reintentar plantillas</button>}
        {estadoPlantillas === "listo" && !plantillas.length && <p className="warning-message" role="status">No hay una plantilla activa compatible con el tipo y el área confirmados. No se puede generar todavía.</p>}
        <fieldset disabled={bloqueada || ocupado || estadoPlantillas !== "listo"} style={sinBorde}>
          <div className="form-group"><label htmlFor="plantilla">Plantilla *</label>
            <select id="plantilla" required value={form.plantillaId} onChange={e => cambiarPlantilla(e.target.value)}>
              <option value="">Seleccione una plantilla</option>
              {plantillas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
            <p className="card-help">{plantillas.find(p => p.id === form.plantillaId)?.descripcion}</p>
            {form.plantillaId && <div className="informe-estructura">
              <h3>Así se organizará su borrador</h3>
              <ol>{seccionesDePlantilla(plantillas.find(p => p.id === form.plantillaId)).map(seccion =>
                <li key={seccion.clave}>{seccion.titulo}<small>{seccion.obligatoria ? "Obligatoria" : "Opcional"}</small></li>)}</ol>
              <p className="card-help">Los campos siguientes son los datos de entrada para elaborarlo.</p>
            </div>}
          </div>
          <div className="form-group"><label htmlFor="area-origen">Área de origen *</label>
            <select id="area-origen" required value={form.areaOrigenId} onChange={e => setForm(prev => ({ ...prev, areaOrigenId: e.target.value }))}>
              <option value="">Seleccione un área</option>
              {areas.map(area => <option key={area.id} value={area.id}>{area.nombre}</option>)}
            </select>
          </div>
          {form.plantillaId && idCampos !== form.plantillaId && !ocupado && <button type="button" className="btn-secondary" onClick={() => cambiarPlantilla(form.plantillaId)}>Reintentar carga de campos</button>}
          {campos.map(campo => <div className="form-group" key={campo.id}>
            <label htmlFor={`campo-${campo.id}`}>{campo.etiqueta}{campo.obligatorio ? " *" : ""}</label>{renderCampo(campo)}
          </div>)}
          {progreso.plantillaLista && !progreso.datosListos && <p className="informe-pendientes" id="datos-pendientes">
            {!form.areaOrigenId && "Seleccione el área de origen. "}
            {progreso.faltantes.length > 0 && `Faltan ${progreso.faltantes.length} campos obligatorios: ${progreso.faltantes.map(c => c.etiqueta).join(", ")}. `}
            {!progreso.valoresValidos && "Revise los valores numéricos."}
          </p>}
          <div className="informe-acciones"><button type="button" className="btn-primary" disabled={!progreso.datosListos}
            aria-describedby={progreso.plantillaLista && !progreso.datosListos ? "datos-pendientes" : undefined}
            onClick={guardarDatos}>Guardar datos y continuar <span aria-hidden="true">→</span></button></div>
        </fieldset>
      </>}
    </section>

    <section id="panel-paso-4" className="informe-panel" hidden={pasoActual !== 4} aria-labelledby="titulo-paso">
      {!informe && solicitud?.estado === "PROCESANDO" && <div>
        <p>Hay una generación en curso. Si se interrumpió, puede reintentar cuando venza su tiempo de espera. Se utilizarán los datos ya guardados.</p>
        <button type="button" className="btn-primary" disabled={ocupado || !elaboracionPermitida}
          onClick={reintentarGeneracion}>Reintentar generación</button>
      </div>}
      {!informe && !["GENERADA", "PROCESANDO"].includes(solicitud?.estado) && <fieldset disabled={bloqueada || ocupado || !progreso.datosListos} style={sinBorde}>
        <div className="informe-nota"><strong>Todo listo para elaborar el borrador.</strong><p>Los datos se guardarán antes de generar. Después podrá revisar cada sección y guardar sus cambios como una nueva versión.</p></div>
        <div className="form-group">
        <label htmlFor="instrucciones">Instrucciones para el generador</label>
        <textarea id="instrucciones" rows="4" value={instrucciones} onChange={e => setInstrucciones(e.target.value)} />
        </div>
        <p className="hint-text">Revise el resultado antes de usarlo. Si falta información, manténgala pendiente de verificación.</p>
        <div className="informe-acciones"><button type="button" className="btn-primary" onClick={generar}>Generar borrador estructurado</button></div>
      </fieldset>}
      {!informe && solicitud?.estado === "GENERADA" && <div>
        <p>Esta solicitud ya tiene un informe. Para recuperarlo, abra su enlace guardado o ingrese el ID del informe.</p>
        <div className="form-group"><label htmlFor="informe-id">ID del informe</label>
        <input id="informe-id" value={informeId} onChange={e => setInformeId(e.target.value)} disabled={ocupado} />
        </div><button type="button" className="btn-primary" onClick={abrirInforme} disabled={ocupado}>Abrir borrador</button>
      </div>}
      {informe && <fieldset disabled={ocupado || !elaboracionPermitida || informe.estado !== "BORRADOR"} style={sinBorde}>
        <div className="informe-version"><strong>Versión {informe.numero_version}</strong><span>{informe.estado}</span></div>
        <p className="hint-text">Informe: <code>{informe.informe_id}</code></p>
        <div className="form-group"><label htmlFor="titulo">Título</label>
          <input id="titulo" value={titulo} onChange={e => setTitulo(e.target.value)} />
        </div>
        <EditorBorrador informe={informe} contenido={contenido}
          onChange={(clave, valor) => setContenido(prev => ({ ...prev, [clave]: valor }))} />
        <div className="informe-acciones"><button type="button" className="btn-primary" onClick={guardarEdicion}>Guardar borrador</button></div>
      </fieldset>}
    </section>
    <div className="informe-navegacion">
      <span>{pasoActual === 1 ? "Comience por el asunto" : `Paso ${pasoActual} de 4`}</span>
      <div>{pasoActual > 1 && <button type="button" className="btn-secondary" disabled={ocupado || cargando}
        onClick={() => setPasoElegido(pasoActual - 1)}><span aria-hidden="true">← </span>Volver</button>}
      {pasoActual < pasoDisponible && pasoActual !== 3 && <button type="button" className="btn-secondary" disabled={ocupado || cargando}
        onClick={() => setPasoElegido(pasoActual + 1)}>Continuar <span aria-hidden="true">→</span></button>}
      {pasoActual === 3 && (informe || ["GENERADA", "PROCESANDO"].includes(solicitud?.estado)) &&
        <button type="button" className="btn-secondary" disabled={ocupado} onClick={() => setPasoElegido(4)}>Volver al borrador →</button>}
      </div>
    </div>
    </div>
    <aside className="informe-resumen" aria-label="Resumen del informe">
      <p className="informe-eyebrow">SU INFORME</p>
      <h2>{informe ? "Borrador disponible" : "En preparación"}</h2>
      <dl>
        <div><dt>Asunto</dt><dd>{form.asunto.trim() || "Aún por definir"}</dd></div>
        <div><dt>Tipo y destino</dt><dd>{contextoVigente ? <>{tipos.find(t => t.id === form.tipoInformeId)?.nombre || "Tipo confirmado"}<br />{areas.find(a => a.id === form.areaDestinoId)?.nombre || "Área confirmada"}</> : "Pendientes de confirmación"}</dd></div>
        <div><dt>Normas confirmadas</dt><dd>{contextoVigente ? form.normativaIds.length ? `${form.normativaIds.length} seleccionadas` : "Ninguna seleccionada" : "Pendientes de revisión"}</dd></div>
        <div><dt>Plantilla</dt><dd>{contextoVigente ? plantillas.find(p => p.id === form.plantillaId)?.nombre || "Pendiente de selección" : "Disponible tras confirmar"}</dd></div>
      </dl>
      {solicitud && <details className="informe-identificador"><summary>Datos de la solicitud</summary>
        <p>Estado: {solicitud.estado}</p><code>{solicitud.id}</code>
      </details>}
      <p className="informe-resumen-ayuda">La IA asiste en la redacción. Usted revisa y confirma la información.</p>
    </aside>
    </div>
  </div>;
}
