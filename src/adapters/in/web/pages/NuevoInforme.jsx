import { useEffect, useState } from "react";

import { mensajeError } from "../services/api";
import { puedeElaborar, obtenerUsuarioGuardado } from "../services/authService";
import {
  obtenerAreas,
  obtenerCamposPlantilla,
  obtenerPlantillas,
  obtenerTiposInforme,
} from "../services/catalogoService";
import { guardarBorrador } from "../services/informeService";
import {
  generarBorrador,
  predecirContexto,
  validarPrediccion,
  obtenerContexto,
} from "../services/iaService";
import {
  actualizarSolicitud,
  crearSolicitud,
  guardarValores,
  obtenerSolicitud,
  guardarSolicitudCompleta,
} from "../services/solicitudService";

const normalizarLista = (datos) => {
  if (Array.isArray(datos)) {
    return datos;
  }

  if (Array.isArray(datos?.data)) {
    return datos.data;
  }

  if (Array.isArray(datos?.items)) {
    return datos.items;
  }

  if (Array.isArray(datos?.results)) {
    return datos.results;
  }

  return [];
};

function NuevoInforme() {
  const elaboracionPermitida = puedeElaborar();

  const [tiposInforme, setTiposInforme] = useState([]);
  const [areas, setAreas] = useState([]);
  const [plantillas, setPlantillas] = useState([]);
  const [camposPlantilla, setCamposPlantilla] = useState([]);

  const [tipoInformeId, setTipoInformeId] = useState("");
  const [areaDestinoId, setAreaDestinoId] = useState("");
  const [areaOrigenId, setAreaOrigenId] = useState(obtenerUsuarioGuardado()?.area_id || "");
  const [plantillaId, setPlantillaId] = useState("");
  const [asunto, setAsunto] = useState("");
  const [valoresCampos, setValoresCampos] = useState({});
  const [instrucciones, setInstrucciones] = useState(
    "Respetar únicamente los datos registrados y la plantilla seleccionada. No presentar como hechos información que no haya sido proporcionada."
  );

  const [solicitud, setSolicitud] = useState(null);
  const [prediccion, setPrediccion] = useState(null);
  const [prediccionConfirmada, setPrediccionConfirmada] = useState(false);
  const [informe, setInforme] = useState(null);
  const [contenidoBorrador, setContenidoBorrador] = useState({});
  const [titulo, setTitulo] = useState("");

  const [cargando, setCargando] = useState(true);
  const [cargaFallida, setCargaFallida] = useState(false);
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  useEffect(() => {
    let activo = true;
    const cargarCatalogos = async () => {
      try {
        const [tipos, areasMunicipales] = await Promise.all([
          obtenerTiposInforme(), obtenerAreas(),
        ]);
        if (activo) {
          setTiposInforme(normalizarLista(tipos));
          setAreas(normalizarLista(areasMunicipales));
        }
        const id = new URLSearchParams(window.location.search).get("solicitud");
        if (id) {
          const guardada = await obtenerSolicitud(id);
          const [formatos, campos, contexto] = await Promise.all([
            guardada.tipo_informe_id ? obtenerPlantillas(guardada.tipo_informe_id) : [],
            guardada.plantilla_id ? obtenerCamposPlantilla(guardada.plantilla_id) : [],
            obtenerContexto(id),
          ]);
          if (activo) {
            setSolicitud(guardada);
            setAsunto(guardada.asunto);
            setTipoInformeId(guardada.tipo_informe_id || "");
            setAreaOrigenId(guardada.area_origen_id || "");
            setAreaDestinoId(guardada.area_destino_id || "");
            setPlantillaId(guardada.plantilla_id || "");
            setPlantillas(normalizarLista(formatos));
            setCamposPlantilla(normalizarLista(campos));
            setValoresCampos(Object.fromEntries(guardada.valores.map(v => [v.campo_plantilla_id, v.valor])));
            setPrediccion(contexto);
            setPrediccionConfirmada(["ACEPTADA", "CORREGIDA"].includes(contexto?.resultado_validacion));
            setMensaje("Solicitud recuperada de la base de datos.");
          }
        }
      } catch (err) {
        if (activo) {
          setCargaFallida(true);
          setError(mensajeError(err, "No se pudieron recuperar los catálogos o la solicitud. Recargue para reintentar."));
        }
      } finally {
        if (activo) setCargando(false);
      }
    };
    cargarCatalogos();
    return () => { activo = false; };
  }, []);

  const invalidarPrediccion = () => {
    setPrediccion(null);
    setPrediccionConfirmada(false);
  };

  const cargarPlantillas = async (tipoId) => {
    if (!tipoId) {
      setPlantillas([]);
      return;
    }

    const datos = await obtenerPlantillas(tipoId);
    setPlantillas(normalizarLista(datos));
  };

  const cargarCampos = async (idPlantilla) => {
    if (!idPlantilla) {
      setCamposPlantilla([]);
      setValoresCampos({});
      return;
    }

    const campos = normalizarLista(await obtenerCamposPlantilla(idPlantilla));
    setCamposPlantilla(campos);

    const valoresIniciales = {};
    campos.forEach((campo) => {
      valoresIniciales[campo.id] = campo.tipo_dato === "boolean" ? false : "";
    });
    setValoresCampos(valoresIniciales);
  };

  const cambiarTipoInforme = async (e) => {
    const id = e.target.value;

    setTipoInformeId(id);
    setPlantillaId("");
    setCamposPlantilla([]);
    setValoresCampos({});
    setPrediccionConfirmada(false);
    setError("");
    setMensaje("");

    try {
      setProcesando(true);
      await cargarPlantillas(id);
    } catch (err) {
      setError(mensajeError(err, "No se pudieron cargar las plantillas."));
    } finally {
      setProcesando(false);
    }
  };

  const cambiarArea = (e) => {
    setAreaDestinoId(e.target.value);
    setPrediccionConfirmada(false);
    setError("");
    setMensaje("");
  };

  const cambiarPlantilla = async (e) => {
    const id = e.target.value;

    setPlantillaId(id);
    setError("");
    setMensaje("");

    try {
      setProcesando(true);
      await cargarCampos(id);
    } catch (err) {
      setError(
        mensajeError(err, "No se pudieron cargar los campos de la plantilla.")
      );
    } finally {
      setProcesando(false);
    }
  };

  const cambiarAsunto = (e) => {
    setAsunto(e.target.value);

    if (prediccion) {
      invalidarPrediccion();
    }
  };

  const cambiarValorCampo = (campo, valor) => {
    setValoresCampos((anteriores) => ({
      ...anteriores,
      [campo.id]: valor,
    }));
  };

  const transformarValor = (campo, valor) => {
    if (campo.tipo_dato === "number") {
      return valor === "" ? null : Number(valor);
    }

    if (campo.tipo_dato === "boolean") {
      return Boolean(valor);
    }

    return valor;
  };

  const validarFormulario = () => {
    if (!areaOrigenId) {
      setError("Seleccione el área de origen.");
      return false;
    }
    if (!tipoInformeId) {
      setError("Seleccione un tipo de informe.");
      return false;
    }

    if (!areaDestinoId) {
      setError("Seleccione una gerencia o área.");
      return false;
    }

    if (!plantillaId) {
      setError("Seleccione una plantilla.");
      return false;
    }

    if (!asunto.trim()) {
      setError("Ingrese el asunto del informe.");
      return false;
    }

    for (const campo of camposPlantilla) {
      if (!campo.obligatorio) {
        continue;
      }

      const valor = valoresCampos[campo.id];

      if (valor === undefined || valor === null || (typeof valor === "string" && !valor.trim())) {
        setError(`Complete el campo obligatorio: ${campo.etiqueta}.`);
        return false;
      }
    }

    return true;
  };

  const armarValores = () => {
    const valores = [];

    camposPlantilla.forEach((campo) => {
      const valor = transformarValor(campo, valoresCampos[campo.id]);

      if (valor === null || valor === undefined || valor === "") {
        return;
      }

      valores.push({
        campo_plantilla_id: campo.id,
        valor,
      });
    });

    return valores;
  };

  const recordarSolicitud = (actual) => {
    setSolicitud(actual);
    const url = new URL(window.location.href);
    url.searchParams.set("solicitud", actual.id);
    window.history.replaceState(null, "", url);
  };

  const persistirSolicitud = async (completa = true) => {
    const datosSolicitud = {
      asunto: asunto.trim(),
      tipo_informe_id: tipoInformeId || null,
      plantilla_id: plantillaId || null,
      area_origen_id: areaOrigenId || null,
      area_destino_id: areaDestinoId || null,
    };

    if (completa) {
      const actual = await guardarSolicitudCompleta(solicitud?.id, {
        ...datosSolicitud, valores: armarValores(),
      });
      recordarSolicitud(actual);
      return actual;
    }

    let solicitudActual = solicitud
      ? await actualizarSolicitud(solicitud.id, datosSolicitud)
      : await crearSolicitud(datosSolicitud);

    recordarSolicitud(solicitudActual);
    if (plantillaId) solicitudActual = await guardarValores(solicitudActual.id, armarValores());
    recordarSolicitud(solicitudActual);
    return solicitudActual;
  };

  const guardarDatosSolicitud = async () => {
    if (!elaboracionPermitida) {
      setError("Su rol solo permite consultar. Use un funcionario o administrador para elaborar.");
      return null;
    }

    if (!validarFormulario()) {
      return null;
    }

    try {
      setProcesando(true);
      setError("");
      setMensaje("");

      const solicitudActual = await persistirSolicitud();
      setMensaje("Datos del informe guardados correctamente.");
      return solicitudActual;
    } catch (err) {
      setError(mensajeError(err, "No se pudieron guardar los datos del informe."));
      return null;
    } finally {
      setProcesando(false);
    }
  };

  const ejecutarPrediccion = async () => {
    if (!elaboracionPermitida) {
      setError("Su rol no permite solicitar predicciones.");
      return;
    }

    if (!asunto.trim()) {
      setError("Ingrese el asunto para solicitar una sugerencia.");
      return;
    }

    try {
      setProcesando(true);
      setError("");
      setMensaje("");

      const solicitudActual = await persistirSolicitud(false);
      const resultado = await predecirContexto(solicitudActual.id);

      setPrediccion(resultado);
      setPrediccionConfirmada(false);
      setMensaje("Se obtuvo una propuesta de estructura y contexto.");
    } catch (err) {
      setError(mensajeError(err, "No fue posible obtener la predicción."));
    } finally {
      setProcesando(false);
    }
  };

  const aplicarContextoConfirmado = async (resultado) => {
    setPrediccion(resultado);

    const estado = resultado.resultado_validacion;
    const aceptada = estado === "ACEPTADA" || estado === "CORREGIDA";
    setPrediccionConfirmada(aceptada);

    if (!aceptada) {
      return "";
    }

    const actual = await obtenerSolicitud(solicitud.id);
    recordarSolicitud(actual);
    const tipoConfirmado = actual.tipo_informe_id;
    const areaConfirmada = actual.area_destino_id;
    if (areaConfirmada) setAreaDestinoId(areaConfirmada);

    if (tipoConfirmado && (tipoConfirmado !== tipoInformeId || actual.plantilla_id !== plantillaId)) {
      setTipoInformeId(tipoConfirmado);
      setPlantillaId("");
      setCamposPlantilla([]);
      setValoresCampos({});
      await cargarPlantillas(tipoConfirmado);
      return "Contexto confirmado. La plantilla anterior no coincide con el tipo propuesto; seleccione una nueva.";
    }

    if (areaConfirmada) {
      setAreaDestinoId(areaConfirmada);
    }

    return "";
  };

  const confirmarPrediccion = async (resultado) => {
    if (!prediccion || !solicitud) {
      return;
    }

    if (resultado === "CORREGIDA" && (!tipoInformeId || !areaDestinoId)) {
      setError("Para corregir debe tener tipo de informe y área seleccionados.");
      return;
    }

    try {
      setProcesando(true);
      setError("");
      setMensaje("");

      const respuesta = await validarPrediccion(
        solicitud.id,
        prediccion.id,
        resultado,
        {
          tipoInformeId,
          areaDestinoId,
        }
      );

      const aviso = await aplicarContextoConfirmado(respuesta);

      if (aviso) {
        setMensaje(aviso);
      } else if (respuesta.resultado_validacion === "RECHAZADA") {
        setMensaje("Contexto rechazado. No se podrá generar un borrador con esta predicción.");
      } else if (respuesta.resultado_validacion === "CORREGIDA") {
        setMensaje("Se confirmó el contexto con las correcciones del funcionario.");
      } else {
        setMensaje("Contexto confirmado correctamente.");
      }
    } catch (err) {
      setError(mensajeError(err, "No fue posible confirmar el contexto."));
    } finally {
      setProcesando(false);
    }
  };

  const ejecutarGeneracion = async () => {
    if (!elaboracionPermitida) {
      setError("Su rol no permite generar borradores.");
      return;
    }

    if (!prediccionConfirmada) {
      setError("Primero debe aceptar o corregir el contexto propuesto.");
      return;
    }

    if (!solicitud) {
      setError("No existe una solicitud guardada.");
      return;
    }

    if (!validarFormulario()) return;

    try {
      setProcesando(true);
      setError("");
      setMensaje("");

      await persistirSolicitud();
      const resultado = await generarBorrador(
        solicitud.id,
        instrucciones.trim() ||
          "Respetar únicamente los datos registrados y la plantilla seleccionada. No presentar como hechos información que no haya sido proporcionada."
      );

      setInforme(resultado);
      setTitulo(resultado.titulo || asunto);
      setContenidoBorrador(resultado.contenido || {});
      setMensaje("Borrador generado correctamente.");
    } catch (err) {
      setError(mensajeError(err, "No se pudo generar el borrador."));
    } finally {
      setProcesando(false);
    }
  };

  const cambiarContenidoBorrador = (seccion, valor) => {
    setContenidoBorrador((anterior) => ({
      ...anterior,
      [seccion]: valor,
    }));
  };

  const guardarCambiosBorrador = async () => {
    if (!informe) {
      setError("Primero debe generar un borrador.");
      return;
    }

    try {
      setProcesando(true);
      setError("");
      setMensaje("");

      const resultado = await guardarBorrador(
        informe.informe_id,
        contenidoBorrador,
        informe.numero_version,
        titulo
      );

      setInforme(resultado);
      setContenidoBorrador(resultado.contenido);
      setMensaje(
        `Borrador guardado correctamente. Versión ${resultado.numero_version}.`
      );
    } catch (err) {
      setError(mensajeError(err, "No se pudo guardar el borrador."));
    } finally {
      setProcesando(false);
    }
  };

  const etiquetaCampo = (campo) => {
    return campo.etiqueta;
  };

  const renderCampo = (campo) => {
    const valor = valoresCampos[campo.id];

    if (campo.tipo_dato === "textarea") {
      return (
        <textarea
          id={`campo-${campo.id}`}
          rows="4"
          value={valor ?? ""}
          onChange={(e) => cambiarValorCampo(campo, e.target.value)}
        />
      );
    }

    if (campo.tipo_dato === "select") {
      const opciones = campo.configuracion?.opciones || [];

      return (
        <select
          id={`campo-${campo.id}`}
          value={valor ?? ""}
          onChange={(e) => cambiarValorCampo(campo, e.target.value)}
        >
          <option value="">Seleccione</option>
          {opciones.map((opcion) => (
            <option key={opcion} value={opcion}>
              {opcion}
            </option>
          ))}
        </select>
      );
    }

    if (campo.tipo_dato === "boolean") {
      return (
        <label className="checkbox-field">
          <input
            id={`campo-${campo.id}`}
            type="checkbox"
            checked={Boolean(valor)}
            onChange={(e) => cambiarValorCampo(campo, e.target.checked)}
          />
          Verificado
        </label>
      );
    }

    return (
      <input
        id={`campo-${campo.id}`}
        type={
          campo.tipo_dato === "date"
            ? "date"
            : campo.tipo_dato === "number"
              ? "number"
              : "text"
        }
        value={valor ?? ""}
        onChange={(e) => cambiarValorCampo(campo, e.target.value)}
      />
    );
  };

  return (
    <div className="nuevo-informe-page">
      <div className="page-title">
        <h1>PMV 1 - Generación estructurada</h1>
        <p>Preparación y redacción inicial</p>
        <p className="card-help">
          Borrador editable y almacenado con estructura institucional.
        </p>
      </div>

      {!elaboracionPermitida && (
        <div className="warning-message">
          Esta identidad solo puede consultar. Para guardar, predecir o generar
          use un funcionario o administrador.
        </div>
      )}

      {error && <div className="error-message">{error}</div>}
      {mensaje && <div className="success-message">{mensaje}</div>}
      {solicitud && <p>Solicitud guardada: <code>{solicitud.id}</code> · Estado: {solicitud.estado}</p>}
      <fieldset disabled={cargando || cargaFallida || procesando || (solicitud && !["BORRADOR", "LISTA_PARA_GENERAR"].includes(solicitud.estado))}
        style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>

      <div className="card">
        <h2>1. Selección de tipo de informe, gerencia y plantilla</h2>
        <p className="card-help">
          Puede escribir primero el asunto y pedir una sugerencia de IA sin
          elegir aún tipo, destino ni plantilla. Confirme la propuesta antes de generar.
        </p>

        {cargando ? (
          <p>Cargando información...</p>
        ) : (
          <>
            <div className="form-group">
              <label htmlFor="tipo-informe">Tipo de informe *</label>
              <select id="tipo-informe" value={tipoInformeId} onChange={cambiarTipoInforme}>
                <option value="">Seleccione un tipo de informe</option>
                {tiposInforme.map((tipo) => (
                  <option key={tipo.id} value={tipo.id}>
                    {tipo.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="area-origen">Área de origen *</label>
              <select id="area-origen" value={areaOrigenId} onChange={e => setAreaOrigenId(e.target.value)}>
                <option value="">Seleccione el área de origen</option>
                {areas.map(area => <option key={area.id} value={area.id}>{area.nombre}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="area-destino">Gerencia / Área de destino *</label>
              <select id="area-destino" value={areaDestinoId} onChange={cambiarArea}>
                <option value="">Seleccione un área</option>
                {areas.map((area) => (
                  <option key={area.id} value={area.id}>
                    {area.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="plantilla">Plantilla *</label>
              <select
                id="plantilla"
                value={plantillaId}
                onChange={cambiarPlantilla}
                disabled={!tipoInformeId}
              >
                <option value="">Seleccione una plantilla</option>
                {plantillas.map((plantilla) => (
                  <option key={plantilla.id} value={plantilla.id}>
                    {plantilla.nombre}
                  </option>
                ))}
              </select>
              {tipoInformeId && plantillas.length === 0 && <p>No hay plantillas activas para este tipo.</p>}
              {plantillaId && <p className="card-help">{plantillas.find(p => p.id === plantillaId)?.descripcion}</p>}
            </div>
          </>
        )}
      </div>

      <div className="card">
        <h2>2. Registro de asunto, antecedentes y datos</h2>
        <p className="card-help">
          Complete el asunto y los datos de la plantilla. Los campos
          obligatorios son necesarios para generar el borrador.
        </p>

        <div className="form-group">
          <label htmlFor="asunto">Asunto *</label>
          <input
            id="asunto"
            type="text"
            value={asunto}
            placeholder="Ejemplo: Inspección de un parque"
            onChange={cambiarAsunto}
            disabled={cargando}
          />
        </div>

        {camposPlantilla.length > 0 && (
          <div>
            <h3 className="section-subtitle">Antecedentes y datos</h3>
            {camposPlantilla.map((campo) => (
              <div className="form-group" key={campo.id}>
                <label htmlFor={`campo-${campo.id}`}>
                  {etiquetaCampo(campo)}
                  {campo.obligatorio ? " *" : ""}
                </label>
                {renderCampo(campo)}
              </div>
            ))}
          </div>
        )}

        <button
          className="btn-primary"
          type="button"
          disabled={procesando || !elaboracionPermitida || cargando}
          onClick={guardarDatosSolicitud}
        >
          Guardar datos
        </button>
      </div>

      <div className="card">
        <h2>3. Generación de un borrador estructurado</h2>
        <p className="card-help">
          Confirme el contexto propuesto y genere un borrador con la
          estructura de la plantilla institucional.
        </p>

        <button
          className="btn-primary"
          type="button"
          disabled={procesando || !elaboracionPermitida}
          onClick={ejecutarPrediccion}
        >
          {procesando ? "Procesando..." : "Predecir estructura y contexto"}
        </button>

        {prediccion && (
          <div className="prediccion-box">
            <h3>Contexto sugerido</h3>
            {prediccion.advertencias?.map(aviso => <p className="warning-inline" key={aviso}>{aviso}</p>)}

            {prediccion.es_mock && (
              <p className="warning-inline">
                Predicción de demostración del PMV 1. El backend usa un mock;
                no ejecuta el modelo real de RF-IA-01.
              </p>
            )}

            <p>
              <strong>Tipo sugerido:</strong>{" "}
              {prediccion.tipo_informe?.nombre || "No disponible"}
            </p>
            <p>
              <strong>Área sugerida:</strong>{" "}
              {prediccion.area_destino?.nombre || "No disponible"}
            </p>
            <p>
              <strong>Modelo:</strong> {prediccion.modelo}
            </p>
            <p>
              <strong>Estado:</strong>{" "}
              {prediccion.resultado_validacion || "PENDIENTE"}
            </p>

            <div className="normativas">
              <strong>Contexto normativo sugerido:</strong>
              {prediccion.normativas?.length > 0 ? (
                <ul>
                  {prediccion.normativas.map((norma) => (
                    <li key={norma.normativa_id}>
                      {norma.codigo ? `${norma.codigo} - ` : ""}
                      {norma.titulo}
                      {norma.confianza != null &&
                        ` (${Math.round(norma.confianza * 100)}% confianza)`}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No se propusieron normativas.</p>
              )}
            </div>

            <div className="btn-row">
              <button
                type="button"
                className="btn-primary"
                disabled={procesando || prediccionConfirmada || !elaboracionPermitida}
                onClick={() => confirmarPrediccion("ACEPTADA")}
              >
                Aceptar propuesta
              </button>

              <button
                type="button"
                className="btn-secondary"
                disabled={procesando || prediccionConfirmada || !elaboracionPermitida}
                onClick={() => confirmarPrediccion("CORREGIDA")}
              >
                Corregir con mis datos
              </button>

              <button
                type="button"
                className="btn-danger"
                disabled={procesando || prediccionConfirmada || !elaboracionPermitida}
                onClick={() => confirmarPrediccion("RECHAZADA")}
              >
                Rechazar
              </button>
            </div>
          </div>
        )}

        <div className="form-group">
          <label>Instrucciones para el generador</label>
          <textarea
            rows="4"
            value={instrucciones}
            onChange={(e) => setInstrucciones(e.target.value)}
          />
        </div>

        <button
          className="btn-primary"
          type="button"
          disabled={
            procesando ||
            !prediccionConfirmada ||
            Boolean(informe) ||
            !elaboracionPermitida
          }
          onClick={ejecutarGeneracion}
        >
          {procesando ? "Generando..." : "Generar borrador estructurado"}
        </button>
      </div>

      </fieldset>
      {informe && (
        <div className="card">
          <h2>4. Edición y guardado</h2>
          <p className="card-help">
            Edite el borrador y guárdelo. La entrega de este PMV es un
            borrador editable y almacenado con estructura institucional.
            No trate como hecho información que no haya registrado.
          </p>

          <div className="form-group">
            <label>Título</label>
            <input
              type="text"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
            />
          </div>

          {Object.entries(contenidoBorrador).map(([seccion, valor]) => (
            <div className="form-group" key={seccion}>
              <label className="label-capitalize">
                {seccion.replaceAll("_", " ")}
              </label>
              <textarea
                rows="6"
                value={
                  typeof valor === "string"
                    ? valor
                    : JSON.stringify(valor, null, 2)
                }
                onChange={(e) =>
                  cambiarContenidoBorrador(seccion, e.target.value)
                }
              />
            </div>
          ))}

          <p className="version-text">
            Versión actual: <strong>{informe.numero_version}</strong>
          </p>

          <button
            type="button"
            className="btn-primary"
            disabled={procesando || !elaboracionPermitida}
            onClick={guardarCambiosBorrador}
          >
            {procesando ? "Guardando..." : "Guardar borrador"}
          </button>
        </div>
      )}
    </div>
  );
}

export default NuevoInforme;
