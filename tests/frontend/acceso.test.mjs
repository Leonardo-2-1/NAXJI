import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

test("acceso y protección de rutas sin caché de permisos ni tokens persistidos", async t => {
  const dom = new JSDOM('<div id="root"></div>', { url: "http://localhost/" });
  const prev = new Map();
  for (const key of ["window", "document", "navigator", "HTMLElement", "Event", "localStorage", "sessionStorage"]) {
    prev.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true });
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const { default: React, act } = await import("react");
  const { createRoot } = await import("react-dom/client");
  const { BrowserRouter } = await import("react-router-dom");
  const { default: axios } = await import("axios");
  const { createServer } = await import("vite");
  const oldAdapter = axios.defaults.adapter;
  let root, vite, session, auth, api, requests, state;
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function settle(check) {
    for (let i = 0; i < 100; i++) {
      await act(async () => { await pause(10); });
      if (check()) return;
    }
    throw new Error("Estado no alcanzado: " + document.body.textContent);
  }
  async function setup(options = {}) {
    if (root) await act(async () => root.unmount());
    if (vite) await vite.close();
    sessionStorage.clear(); localStorage.clear();
    window.history.replaceState(null, "", options.path || "/");
    state = { mode: "supabase", cookie: false, profileStatus: 200, loginStatus: 200,
      refreshStatus: 200, configStatus: 200, sequence: 0, ...options };
    requests = [];
    axios.defaults.adapter = async config => {
      const request = { method: config.method, path: config.url };
      requests.push(request);
      await pause(15);
      let data, status = 200;
      if (config.url === "/auth/config") {
        status = state.configStatus;
        data = { mode: state.mode, persistence: state.mode === "mock" ? "memory" : "postgres" };
      } else if (config.url === "/auth/login") {
        status = state.loginStatus;
        if (status === 200) state.cookie = true;
        data = { access_token: `TOKEN_FICTICIO_${++state.sequence}`, expires_in: 3600 };
      } else if (config.url === "/auth/refresh") {
        status = !state.cookie ? 401 : state.profileStatus === 403 ? 403 : state.refreshStatus;
        data = { access_token: `TOKEN_FICTICIO_${++state.sequence}`, expires_in: 3600 };
      } else if (config.url === "/auth/logout") { state.cookie = false; status = 204; }
      else if (config.url === "/auth/me") {
        if (state.deferProfile) await state.deferProfile;
        status = state.profileStatus;
        data = { id: "usuario-ficticio", nombres: "Prueba", roles: ["FUNCIONARIO"], area_id: "a" };
      } else if (config.url === "/tipos-informe") data = [{ id: "t", nombre: "Tipo de prueba", activo: true }];
      else if (config.url === "/areas") data = [{ id: "a", nombre: "Área de prueba", activo: true }];
      else throw new Error(`Petición no prevista ${config.url}`);
      if (state.failOnce?.delete(config.url)) status = 401;
      request.status = status;
      if (status >= 400) throw new axios.AxiosError("Fallo simulado", "ERR_BAD_RESPONSE", config, null,
        { status, data: { detail: `Error de prueba HTTP ${status}` }, config });
      return { status, data, config, headers: {}, statusText: "OK" };
    };
    vite = await createServer({ logLevel: "error", server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
    const { default: App } = await vite.ssrLoadModule("/src/adapters/in/web/App.jsx");
    session = await vite.ssrLoadModule("/src/adapters/in/web/services/session.js");
    auth = await vite.ssrLoadModule("/src/adapters/in/web/services/authService.js");
    api = (await vite.ssrLoadModule("/src/adapters/in/web/services/api.js")).default;
    if (options.demoToken) sessionStorage.setItem("naxji_demo_token", options.demoToken);
    root = createRoot(document.getElementById("root"));
    await act(async () => root.render(React.createElement(React.StrictMode, null,
      React.createElement(BrowserRouter, null, React.createElement(App)))));
  }
  const count = path => requests.filter(r => r.path === path).length;
  const button = () => document.querySelector('button[type="submit"]');
  const listo = () => document.getElementById("asunto") && !document.getElementById("asunto").disabled;
  const text = () => document.body.textContent;
  async function input(id, value) {
    const el = document.getElementById(id);
    await act(async () => {
      Object.getOwnPropertyDescriptor(el.tagName === "SELECT" ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype, "value").set.call(el, value);
      el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
    });
  }
  async function submit() {
    assert.equal(button().disabled, false);
    await act(async () => document.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  }
  const retry = () => [...document.querySelectorAll("button")].find(b => b.textContent.includes("Reintentar"));
  try {
    for (const width of [1440, 390]) {
      await t.test(`login real y navegación con DOM a ${width}px; un perfil validado por entrada`, async () => {
        Object.defineProperty(window, "innerWidth", { value: width, configurable: true });
        await setup();
        await settle(() => button() && !button().disabled);
        assert.equal(count("/auth/config"), 1);
        assert.equal(count("/auth/refresh"), 1, "No reintenta una cookie inexistente");
        assert.equal(count("/auth/me"), 0);
        assert.equal(document.querySelector("nav"), null);
        assert.equal(document.querySelector(".informe-pasos"), null);
        for (const id of ["email", "password"]) assert.equal(document.getElementById(id).labels.length, 1);
        assert.equal(document.getElementById("password").type, "password");
        assert.equal(document.getElementById("password").autocomplete, "current-password");
        await input("email", "fixture@example.invalid"); await input("password", "valor-ficticio");
        await submit(); assert.equal(button().disabled, true);
        await settle(listo);
        assert.equal(count("/auth/login"), 1);
        assert.equal(count("/auth/me"), 1, "StrictMode comparte la petición pendiente");
        assert.equal(localStorage.length, 0);
        assert.equal(sessionStorage.length, 0, "No persiste tokens Supabase");
        assert.equal(auth.obtenerUsuarioGuardado().id, "usuario-ficticio");
        assert.equal(window.location.pathname, "/nuevo-informe");
      });
    }
    await t.test("sesión Supabase recuperada en acceso público y en ruta privada", async () => {
      for (const path of ["/", "/nuevo-informe"]) {
        await setup({ cookie: true, path });
        await settle(listo);
        assert.equal(count("/auth/refresh"), 1);
        assert.equal(count("/auth/me"), 1);
        assert.equal(count("/auth/login"), 0);
        assert.equal(localStorage.length + sessionStorage.length, 0);
      }
    });
    await t.test("demo conserva selector, acceso y recuperación sin solicitar credenciales reales", async () => {
      await setup({ mode: "mock" });
      await settle(() => button() && !button().disabled);
      assert.match(text(), /Entorno de demostración/);
      assert.equal(document.getElementById("email"), null);
      assert.equal(document.getElementById("usuario-demo").labels.length, 1);
      assert.equal(count("/auth/me"), 0);
      await submit(); await settle(listo);
      assert.equal(count("/auth/me"), 1);
      assert.equal(count("/auth/login") + count("/auth/refresh"), 0);
      assert.equal(sessionStorage.getItem("naxji_demo_token"), "demo-funcionario");
      await setup({ mode: "mock", demoToken: "demo-funcionario" });
      await settle(listo); assert.equal(count("/auth/me"), 1);
    });
    await t.test("configuración fallida permite reintentar; modo deshabilitado impide entrar", async () => {
      await setup({ configStatus: 503 });
      await settle(() => retry() && !retry().disabled);
      assert.equal(button().disabled, true);
      state.configStatus = 200;
      await act(async () => retry().click());
      await settle(() => button() && !button().disabled);
      assert.equal(count("/auth/config"), 2);
      await setup({ mode: "disabled" });
      await settle(() => text().includes("El acceso no está habilitado"));
      assert.equal(button().disabled, true);
      assert.equal(count("/auth/me"), 0);
    });
    await t.test("credenciales rechazadas conservan correo, limpian contraseña y muestran error", async () => {
      await setup({ loginStatus: 401 });
      await settle(() => button() && !button().disabled);
      await input("email", "fixture@example.invalid"); await input("password", "valor-ficticio");
      await submit();
      await settle(() => text().includes("Error de prueba HTTP 401") && !button().disabled);
      assert.equal(document.getElementById("password").value, "");
      assert.equal(document.getElementById("email").value, "fixture@example.invalid");
      assert.equal(document.querySelector(".nuevo-informe-page"), null);
      state.loginStatus = 200;
      await input("password", "nuevo-valor-ficticio"); await submit(); await settle(listo);
    });
    await t.test("fallo de perfil permite reintento sin mostrar contenido ni cargar catálogos", async () => {
      await setup({ cookie: true, path: "/nuevo-informe", profileStatus: 503 });
      await settle(() => document.querySelector(".estado-acceso [role=alert]"));
      assert.equal(document.getElementById("asunto"), null);
      assert.equal(count("/tipos-informe") + count("/areas"), 0);
      state.profileStatus = 200;
      await act(async () => retry().click()); await settle(listo);
      assert.equal(count("/auth/me"), 2, "El reintento vuelve a consultar el backend");
    });
    await t.test("403 deniega la ruta y limpia la sesión; no hay bucle de redirección", async () => {
      await setup({ cookie: true, profileStatus: 403, path: "/nuevo-informe" });
      await settle(() => button() && !button().disabled);
      assert.equal(document.getElementById("asunto"), null);
      assert.equal(session.storedUser(), null);
      const total = requests.length;
      await act(async () => { await pause(100); });
      assert.equal(requests.length, total);
    });
    await t.test("perfil rechazado después del login conserva el mensaje de error al regresar", async () => {
      await setup();
      await settle(() => button() && !button().disabled);
      await input("email", "fixture@example.invalid"); await input("password", "valor-ficticio");
      state.profileStatus = 403;
      await submit();
      await settle(() => count("/auth/me") === 1 && button() && !button().disabled);
      assert.match(text(), /Error de prueba HTTP 403/);
      assert.equal(document.querySelector(".nuevo-informe-page"), null);
    });
    await t.test("un 401 protegido renueva una vez y reintenta con token en memoria", async () => {
      await setup({ cookie: true }); await settle(listo);
      const prevRefresh = count("/auth/refresh");
      state.failOnce = new Set(["/areas", "/tipos-informe"]);
      await act(async () => { await Promise.all([api.get("/areas"), api.get("/tipos-informe")]); });
      assert.equal(count("/auth/refresh") - prevRefresh, 1);
      assert.equal(localStorage.length + sessionStorage.length, 0);
    });
    await t.test("comparte solo consultas simultáneas, nunca reutiliza un perfil resuelto", async () => {
      await setup({ cookie: true }); await settle(listo);
      const start = count("/auth/me");
      await act(async () => { await Promise.all([auth.obtenerUsuarioActual(), auth.obtenerUsuarioActual()]); });
      assert.equal(count("/auth/me") - start, 1);
      await act(async () => { await auth.obtenerUsuarioActual(); });
      assert.equal(count("/auth/me") - start, 2);
    });
    await t.test("una respuesta de perfil tardía no restaura un usuario tras cerrar sesión", async () => {
      await setup({ cookie: true }); await settle(listo);
      let resolve;
      state.deferProfile = new Promise(r => { resolve = r; });
      const pending = auth.obtenerUsuarioActual().catch(error => error);
      await settle(() => count("/auth/me") === 2);
      await act(async () => { session.clearSession(); resolve(); });
      assert.equal(axios.isCancel(await pending), true);
      assert.equal(session.storedUser(), null);
      state.cookie = false;
      await settle(() => button() && !button().disabled);
      assert.equal(document.querySelector(".nuevo-informe-page"), null);
    });
    await t.test("un fallo de carga del módulo diferido muestra una opción de recuperación", async () => {
      if (root) await act(async () => root.unmount());
      const { LimiteCarga } = await vite.ssrLoadModule("/src/adapters/in/web/components/EstadoAcceso.jsx");
      const originalError = console.error;
      console.error = () => {}; // React informa del fixture que lanza intencionadamente.
      try {
        function ModuloFallido() { throw new Error("Fallo de módulo simulado"); }
        root = createRoot(document.getElementById("root"));
        await act(async () => root.render(React.createElement(LimiteCarga, null, React.createElement(ModuloFallido))));
        assert.match(text(), /No se pudo cargar el formulario/);
        assert.ok(retry());
        assert.equal(document.querySelector(".nuevo-informe-page"), null);
      } finally { console.error = originalError; }
    });
  } finally {
    if (root) await act(async () => root.unmount());
    if (vite) await vite.close();
    axios.defaults.adapter = oldAdapter;
    dom.window.close();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
    for (const [key, descriptor] of prev) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});
