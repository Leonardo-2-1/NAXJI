// Recorrido del componente React con HTTP simulado: nunca escribe en Supabase.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { JSDOM } from "jsdom";

const fixture = JSON.parse(await readFile(new URL("../fixtures/inspeccion_piloto.json", import.meta.url), "utf8"));

for (const esMdt of [false, true]) test(`inspección ${esMdt ? "v2 Anexo 08" : "v1 piloto"}: formulario, invalidación, recuperación, reintento y versiones`, async t => {
  const dom = new JSDOM('<div id="root"></div>', { url: "http://localhost/nuevo-informe" });
  const anteriores = new Map();
  for (const key of ["window", "document", "navigator", "HTMLElement", "Event", "localStorage", "sessionStorage"]) {
    anteriores.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true });
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const { default: React, act } = await import("react");
  const { createRoot } = await import("react-dom/client");
  const { BrowserRouter } = await import("react-router-dom");
  const { default: axios } = await import("axios");
  const { createServer } = await import("vite");
  const adapterAnterior = axios.defaults.adapter;
  const sid = "11111111-1111-4111-8111-111111111111";
  const iid = "33333333-3333-4333-8333-333333333333";
  const tipos = [{ id: "t1", nombre: "Informe de Inspección" }, { id: "t2", nombre: "Tipo sin plantilla" }];
  const areas = [{ id: "a1", nombre: "Subgerencia de Gestión Ambiental" }, { id: "a2", nombre: "Área ficticia 2" }];
  const { plantilla, campos } = structuredClone(fixture);
  if (esMdt) {
    plantilla.version = 2;
    plantilla.formato_documento = "mdt_informe_anexo08_2019_revision1";
    plantilla.secciones_salida = [{ clave: "cuerpo", titulo: "Cuerpo del informe interno", obligatoria: true }];
  }
  const campoEditado = esMdt ? "contenido-cuerpo" : "contenido-hallazgos";
  let solicitud, prediccion, informe, resolverPrediccion;
  let aplazar = false, fallarGeneracion = false, fallarCampos = false;
  let fallarDescarga = false;
  const versiones = new Map();
  const descargas = [];
  const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
  URL.createObjectURL = blob => { descargas.push(blob); return "blob:prueba-docx"; };
  URL.revokeObjectURL = () => {};
  dom.window.HTMLAnchorElement.prototype.click = function () { descargas.push(this.download); };
  const requests = [];
  axios.defaults.adapter = async config => {
    const data = typeof config.data === "string" ? JSON.parse(config.data) : config.data;
    requests.push({ url: config.url, method: config.method, data });
    const error = detalle => Object.assign(new Error(detalle), { isAxiosError: true, config,
      response: { status: 503, data: { detail: detalle } } });
    let result;
    if (config.url === "/auth/config") result = { mode: "mock", persistence: "memory" };
    else if (config.url === "/tipos-informe") result = tipos;
    else if (config.url === "/areas") result = areas;
    else if (config.url === "/solicitudes") result = solicitud = { id: sid, estado: "BORRADOR", valores: [], ...data };
    else if (config.url.endsWith("/predecir-contexto")) {
      prediccion = { id: "p", resultado_validacion: "PENDIENTE", modelo: "PRUEBA SIMULADA", es_mock: true,
        tipo_informe: { id: "t1", nombre: tipos[0].nombre, confianza: .9 },
        area_destino: { id: "a1", nombre: areas[0].nombre, confianza: .8 },
        normativas: ["n1", "n2"].map(id => ({ normativa_id: id, titulo: `Norma ficticia ${id}`, aceptada: null })) };
      if (aplazar) await new Promise(resolve => { resolverPrediccion = resolve; });
      result = prediccion;
    } else if (config.url.endsWith("/validar-prediccion")) {
      const corregida = data.resultado === "CORREGIDA";
      solicitud.tipo_informe_id = corregida ? data.tipo_informe_id : "t1";
      solicitud.area_destino_id = corregida ? data.area_destino_id : "a1";
      prediccion.resultado_validacion = data.resultado;
      prediccion.normativas.forEach(n => { n.aceptada = corregida ? data.normativa_ids.includes(n.normativa_id) : true; });
      result = prediccion;
    } else if (config.url.endsWith("/contexto")) result = prediccion;
    else if (config.url.endsWith("/completa")) result = solicitud = { ...solicitud, ...data, estado: "LISTA_PARA_GENERAR" };
    else if (config.url === `/solicitudes/${sid}`) {
      if (config.method === "put") solicitud = { ...solicitud, ...data };
      result = solicitud;
    } else if (config.url === "/plantillas") result = config.params.tipo_informe_id === "t1" ? [plantilla] : [];
    else if (config.url.endsWith("/campos")) {
      if (fallarCampos) throw error("Fallo de campos simulado");
      result = campos;
    } else if (config.url.endsWith("/generar-borrador")) {
      if (fallarGeneracion) throw error("Generador no disponible (prueba simulada)");
      solicitud.estado = "GENERADA";
      result = informe = { informe_id: iid, solicitud_id: sid, estado: "BORRADOR", numero_version: 1,
        titulo: "Borrador de prueba", secciones_salida: plantilla.secciones_salida,
        plantilla_nombre: plantilla.nombre, plantilla_version: plantilla.version,
        contenido: { encabezado: { asunto: solicitud.asunto, formato_documento: plantilla.formato_documento, autor_id: "99999999-9999-4999-8999-999999999999" }, ...Object.fromEntries(plantilla.secciones_salida.map(s =>
          [s.clave, "Pendiente de verificación: no se aportaron resultados de inspección."])) } };
      versiones.set(1, structuredClone(informe));
    } else if (config.url === `/solicitudes/${sid}/informe`) {
      result = informe;
    } else if (config.url.endsWith("/docx")) {
      if (fallarDescarga) {
        const fallo = error("Error de descarga");
        fallo.response.data = new Blob([JSON.stringify({ detail: "No tiene acceso a este recurso" })], { type: "application/json" });
        fallo.response.status = 403;
        throw fallo;
      }
      result = new Blob([JSON.stringify(versiones.get(Number(config.url.split("/").at(-2))).contenido)],
        { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
    } else if (config.url.startsWith(`/informes/${iid}/versiones/`)) {
      result = versiones.get(Number(config.url.split("/").at(-1)));
    } else if (config.url === `/informes/${iid}`) {
      if (config.method === "put") {
        informe = { ...informe, ...data, numero_version: informe.numero_version + 1 };
        if (data.encabezado_oficial) informe.contenido = { ...data.contenido,
          encabezado: { ...data.contenido.encabezado, documento: data.encabezado_oficial } };
        versiones.set(informe.numero_version, structuredClone(informe));
      }
      result = informe;
    } else throw new Error(`HTTP no previsto: ${config.method} ${config.url}`);
    return { data: structuredClone(result), status: 200, statusText: "OK", headers: {}, config };
  };
  let root;
  const vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: Page } = await vite.ssrLoadModule("/src/adapters/in/web/pages/NuevoInforme.jsx");
    const { saveUser } = await vite.ssrLoadModule("/src/adapters/in/web/services/session.js");
    saveUser({ id: "u", roles: ["FUNCIONARIO"], area_id: "a1" });
    sessionStorage.setItem("naxji_demo_token", "demo-funcionario");
    const visible = el => el && !el.closest("[hidden]");
    const texto = () => document.body.textContent;
    const esperar = async check => {
      for (let i = 0; i < 100; i++) {
        await act(async () => { await new Promise(r => setTimeout(r, 10)); });
        if (check()) return;
      }
      throw new Error("Estado esperado no alcanzado: " + texto());
    };
    const mount = async (url = "/nuevo-informe") => {
      if (root) await act(async () => root.unmount());
      window.history.replaceState(null, "", url);
      root = createRoot(document.getElementById("root"));
      await act(async () => root.render(React.createElement(BrowserRouter, null, React.createElement(Page))));
      await esperar(() => !texto().includes("Recuperando catálogos"));
    };
    const paso = n => document.querySelectorAll(".informe-pasos button")[n - 1];
    const actual = n => assert.equal(paso(n).getAttribute("aria-current"), "step");
    const pulsar = async el => {
      assert.ok(visible(el), "Control visible");
      assert.equal(el.matches(":disabled"), false, "Control habilitado");
      await act(async () => el.click());
    };
    const boton = titulo => [...document.querySelectorAll("button")].find(b => visible(b) && b.textContent.includes(titulo));
    const escribir = async (id, valor) => {
      const el = document.getElementById(id);
      assert.ok(visible(el), `${id} visible`);
      assert.equal(el.matches(":disabled"), false, `${id} editable`);
      await act(async () => {
        const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype :
          el.tagName === "SELECT" ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, "value").set.call(el, valor);
        el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
      });
    };
    await t.test("asunto solo y descarte de una norma habilitan la plantilla tras confirmar", async () => {
      await mount(); actual(1);
      assert.equal(paso(2).disabled, true);
      await escribir("asunto", "PRUEBA NAXJI: inspección sin resultados");
      await pulsar(boton("Analizar asunto")); actual(2);
      assert.equal(document.activeElement.id, "titulo-paso");
      assert.deepEqual(requests.find(r => r.url === "/solicitudes").data, { asunto: "PRUEBA NAXJI: inspección sin resultados" });
      assert.equal(paso(3).disabled, true);
      await pulsar(document.querySelectorAll('.informe-normativas input[type="checkbox"]')[1]);
      await pulsar(boton("Confirmar correcciones")); actual(3);
      assert.deepEqual(requests.find(r => r.url.endsWith("/validar-prediccion")).data.normativa_ids, ["n1"]);
      assert.equal(paso(4).disabled, true);
    });
    await t.test("campos fallidos se reintentan; datos incompletos bloquean el avance", async () => {
      fallarCampos = true;
      await escribir("plantilla", "p1");
      assert.match(texto(), /Fallo de campos simulado/);
      assert.equal(paso(4).disabled, true);
      fallarCampos = false;
      await pulsar(boton("Reintentar carga de campos"));
      assert.equal(boton("Guardar datos fuente").matches(":disabled"), true);
      assert.equal(boton("Generar propuesta con Ollama").matches(":disabled"), true);
      assert.match(texto(), /No constituye un formato municipal oficial/);
      assert.doesNotMatch(texto(), /seleccione la v2|Existe una versión de plantilla más reciente/);
      for (const campo of campos) assert.ok(document.getElementById(`campo-${campo.id}`));
      assert.equal(document.getElementById("contenido-hallazgos"), null, "Los datos fuente no exigen redactar secciones");
      await escribir("campo-c1", "Sin resultados de inspección");
      actual(3); // Completar el último campo no cambia de pantalla mientras se escribe.
      assert.equal(paso(4).disabled, true, "Sin versión guardada no hay vista previa");
      await pulsar(boton("Guardar datos fuente")); actual(3);
    });
    await t.test("UUID recupera selección y datos; modificar tipo exige reconfirmar", async () => {
      await mount(`/nuevo-informe?solicitud=${sid}`); actual(3);
      await pulsar(paso(3));
      assert.equal(document.getElementById("campo-c1").value, "Sin resultados de inspección");
      await pulsar(paso(2));
      assert.equal(document.querySelectorAll('.informe-normativas input[type="checkbox"]')[1].checked, false);
      await escribir("tipo-informe", "t2"); actual(2);
      assert.equal(paso(4).disabled, true);
      await pulsar(boton("Confirmar correcciones")); actual(3);
      assert.match(texto(), /No hay una plantilla activa compatible/);
      assert.match(texto(), /plantilla anterior ya no es compatible/);
      await pulsar(paso(2)); await escribir("tipo-informe", "t1");
      await pulsar(boton("Confirmar correcciones"));
    });
    await t.test("editar asunto invalida los pasos y descarta una respuesta tardía", async () => {
      await pulsar(paso(1));
      await escribir("asunto", "PRUEBA NAXJI modificada"); actual(1);
      assert.equal(paso(2).disabled, true);
      aplazar = true;
      await pulsar(boton("Analizar asunto")); await esperar(() => Boolean(resolverPrediccion));
      await escribir("asunto", "PRUEBA NAXJI definitiva");
      await act(async () => resolverPrediccion());
      actual(1); assert.equal(paso(2).disabled, true);
      aplazar = false;
      await pulsar(boton("Analizar asunto")); await pulsar(boton("Aceptar propuesta"));
      await escribir("plantilla", "p1");
      await escribir("campo-c1", "Sin resultados de inspección");
      await pulsar(boton("Guardar datos fuente")); actual(3);
    });
    await t.test("fallo de generación controlado, reintento, edición y recuperación de versión 2", async () => {
      fallarGeneracion = true;
      await pulsar(boton("Generar propuesta con Ollama"));
      assert.match(texto(), /Generador no disponible/); actual(3);
      fallarGeneracion = false;
      await pulsar(boton("Generar propuesta con Ollama")); actual(3);
      assert.equal(paso(4).disabled, false);
      assert.equal(document.getElementById("contenido-encabezado"), null);
      assert.deepEqual([...document.querySelectorAll('textarea[id^="contenido-"]')].map(el => el.id),
        plantilla.secciones_salida.map(s => `contenido-${s.clave}`));
      await escribir(campoEditado, "Edición ficticia conservada.");
      assert.doesNotMatch(texto(), /99999999-9999-4999-8999-999999999999/);
      await escribir("oficial-numero", "PRUEBA-LOCAL");
      await escribir("oficial-referencia", "Ficha ficticia E1");
      if (esMdt) await escribir("oficial-cargo_destinatario", "Cargo ficticio de prueba");
      await pulsar(boton("Guardar borrador"));
      assert.match(texto(), /Versión 2/);
      assert.ok(texto().includes(`Versión de plantilla ${plantilla.version}`));
      assert.equal(requests.findLast(r => r.method === "put" && r.url === `/informes/${iid}`).data.encabezado_oficial.numero, "PRUEBA-LOCAL");
      await mount(`/nuevo-informe?solicitud=${sid}&informe=${iid}`); actual(4);
      assert.equal(document.getElementById(campoEditado).value, "Edición ficticia conservada.");
      assert.equal(document.getElementById("oficial-numero").value, "PRUEBA-LOCAL");
      if (esMdt) assert.equal(document.getElementById("oficial-cargo_destinatario").value, "Cargo ficticio de prueba");
      await mount(`/nuevo-informe?solicitud=${sid}`); actual(4);
      assert.ok(requests.some(r => r.url === `/solicitudes/${sid}/informe`), "Se recupera automáticamente por UUID");
      assert.equal(document.getElementById(campoEditado).value, "Edición ficticia conservada.");
    });
    await t.test("vista previa y DOCX usan la versión guardada, excluyen cambios sin guardar y conservan anteriores", async () => {
      const preview = () => document.querySelector(".informe-documento").textContent;
      assert.match(preview(), /Edición ficticia conservada/);
      assert.match(preview(), /PRUEBA-LOCAL/);
      await pulsar(paso(3));
      await escribir(campoEditado, "Texto sin guardar que no se debe descargar.");
      await escribir("oficial-numero", "NUMERO-SIN-GUARDAR");
      await pulsar(paso(4));
      assert.match(texto(), /Hay cambios sin guardar/);
      assert.doesNotMatch(preview(), /Texto sin guardar/);
      assert.doesNotMatch(preview(), /NUMERO-SIN-GUARDAR/);
      const inicio = requests.length;
      await pulsar(boton("Descargar DOCX"));
      assert.deepEqual(requests.slice(inicio).map(r => [r.method, r.url]), [["get", `/informes/${iid}/versiones/2/docx`]]);
      assert.match(await descargas[0].text(), /Edición ficticia conservada/);
      assert.doesNotMatch(await descargas[0].text(), /Texto sin guardar/);
      assert.equal(descargas[1], `NAXJI-${iid}-v2.docx`);
      await escribir("version-vista", "1");
      assert.match(preview(), /Pendiente de verificación/);
      assert.doesNotMatch(preview(), /Edición ficticia conservada/);
      assert.doesNotMatch(preview(), /PRUEBA-LOCAL|99999999-9999-4999-8999-999999999999/);
      await pulsar(boton("Descargar DOCX"));
      assert.equal(requests.at(-1).url, `/informes/${iid}/versiones/1/docx`);
      fallarDescarga = true;
      await pulsar(boton("Descargar DOCX"));
      assert.match(texto(), /No tiene acceso a este recurso/);
      fallarDescarga = false;
      await pulsar(boton("Descargar DOCX"));
      assert.match(texto(), /Descarga preparada/);
    });
    await t.test("PROCESANDO mantiene su reintento; los roles de consulta no editan", async () => {
      solicitud.estado = "PROCESANDO";
      await mount(`/nuevo-informe?solicitud=${sid}`); actual(3);
      const inicio = requests.length;
      await pulsar(boton("Reintentar generación"));
      assert.equal(requests.slice(inicio).some(r => r.url.endsWith("/completa")), false);
      saveUser({ id: "r", roles: ["REVISOR"] });
      await mount(`/nuevo-informe?solicitud=${sid}&informe=${iid}`); actual(4);
      assert.equal(boton("Descargar DOCX").matches(":disabled"), false, "Lectura no depende de permiso de edición");
      await pulsar(paso(3));
      assert.equal(document.getElementById(campoEditado).matches(":disabled"), true);
      assert.equal(boton("Guardar borrador").matches(":disabled"), true);
    });
  } finally {
    if (root) await act(async () => root.unmount());
    await vite.close();
    axios.defaults.adapter = adapterAnterior;
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
    dom.window.close();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
    for (const [key, descriptor] of anteriores) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});
