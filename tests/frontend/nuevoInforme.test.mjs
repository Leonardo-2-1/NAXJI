// Recorrido del componente React con HTTP simulado: nunca escribe en Supabase.
import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

test("formulario guiado: navegación, invalidación, recuperación, reintento y versiones", async t => {
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
  const tipos = [{ id: "t1", nombre: "Tipo ficticio 1" }, { id: "t2", nombre: "Tipo ficticio 2" }];
  const areas = [{ id: "a1", nombre: "Área ficticia 1" }, { id: "a2", nombre: "Área ficticia 2" }];
  const plantilla = { id: "p1", nombre: "Plantilla DEMO", tipo_informe_id: "t1", activa: true,
    secciones_salida: [{ clave: "resumen", titulo: "Resumen de prueba", obligatoria: true },
      { clave: "pendientes", titulo: "Pendientes de prueba", obligatoria: true }] };
  const campos = [{ id: "c1", etiqueta: "Descripción", tipo_dato: "textarea", obligatorio: true, activo: true }];
  let solicitud, prediccion, informe, resolverPrediccion;
  let aplazar = false, fallarGeneracion = false, fallarCampos = false;
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
        contenido: { encabezado: { asunto: solicitud.asunto }, resumen: "Sin resultados de inspección.", pendientes: "Verificación pendiente." } };
    } else if (config.url === `/informes/${iid}`) {
      if (config.method === "put") informe = { ...informe, ...data, numero_version: informe.numero_version + 1 };
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
      assert.equal(boton("Guardar datos y continuar").matches(":disabled"), true);
      await escribir("campo-c1", "No hay resultados de inspección registrados.");
      actual(3); // Completar el último campo no cambia de pantalla mientras se escribe.
      assert.equal(paso(4).disabled, false);
      await pulsar(boton("Guardar datos y continuar")); actual(4);
    });
    await t.test("UUID recupera selección y datos; modificar tipo exige reconfirmar", async () => {
      await mount(`/nuevo-informe?solicitud=${sid}`); actual(4);
      await pulsar(paso(3));
      assert.equal(document.getElementById("campo-c1").value, "No hay resultados de inspección registrados.");
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
      await escribir("campo-c1", "No hay resultados de inspección registrados.");
      await pulsar(boton("Guardar datos y continuar")); actual(4);
    });
    await t.test("fallo de generación controlado, reintento, edición y recuperación de versión 2", async () => {
      fallarGeneracion = true;
      await pulsar(boton("Generar borrador estructurado"));
      assert.match(texto(), /Generador no disponible/); actual(4);
      fallarGeneracion = false;
      await pulsar(boton("Generar borrador estructurado"));
      assert.equal(document.getElementById("contenido-encabezado"), null);
      await escribir("contenido-pendientes", "Edición ficticia conservada.");
      await pulsar(boton("Guardar borrador"));
      assert.match(texto(), /Versión 2/);
      await mount(`/nuevo-informe?solicitud=${sid}&informe=${iid}`); actual(4);
      assert.equal(document.getElementById("contenido-pendientes").value, "Edición ficticia conservada.");
      await mount(`/nuevo-informe?solicitud=${sid}`); actual(4);
      await escribir("informe-id", iid); await pulsar(boton("Abrir borrador"));
      assert.equal(document.getElementById("contenido-pendientes").value, "Edición ficticia conservada.");
    });
    await t.test("PROCESANDO mantiene su reintento; los roles de consulta no editan", async () => {
      solicitud.estado = "PROCESANDO";
      await mount(`/nuevo-informe?solicitud=${sid}`); actual(4);
      const inicio = requests.length;
      await pulsar(boton("Reintentar generación"));
      assert.equal(requests.slice(inicio).some(r => r.url.endsWith("/completa")), false);
      saveUser({ id: "r", roles: ["REVISOR"] });
      await mount(`/nuevo-informe?solicitud=${sid}&informe=${iid}`); actual(4);
      assert.equal(document.getElementById("contenido-pendientes").matches(":disabled"), true);
      assert.equal(boton("Guardar borrador").matches(":disabled"), true);
    });
  } finally {
    if (root) await act(async () => root.unmount());
    await vite.close();
    axios.defaults.adapter = adapterAnterior;
    dom.window.close();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
    for (const [key, descriptor] of anteriores) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});
