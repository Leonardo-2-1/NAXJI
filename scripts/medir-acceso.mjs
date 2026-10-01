import { JSDOM } from 'jsdom';
import { writeFile, mkdir } from 'node:fs/promises';
import { performance } from 'node:perf_hooks';
import { resolve } from 'node:path';

const phase = process.argv[2];
const mode = process.argv[3] || 'demo';
if (!['antes', 'despues'].includes(phase) || !['demo', 'real'].includes(mode)) throw new Error('Uso: medir-acceso.mjs antes|despues demo|real [--baseline]');
const baseline = process.argv.includes('--baseline');
const origin = mode === 'real' ? 'http://localhost:5174' : 'http://localhost:5173';
let credentials = null;
if (mode === 'real') {
  let input = '';
  for await (const part of process.stdin) input += part;
  try { credentials = JSON.parse(input); } catch { throw new Error('Se requiere un JSON de credenciales por stdin.'); }
  input = '';
}
const output = { phase, mode, origin, scope: 'React DOM sin motor visual; HTTP real, sin predicción/generación ni escritura de solicitudes', runs: [] };
const dom = new JSDOM('<div id="root"></div>', { url: origin });
for (const key of ['window', 'document', 'navigator', 'HTMLElement', 'Event', 'localStorage', 'sessionStorage'])
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { default: React, act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { BrowserRouter } = await import('react-router-dom');
const { default: axios } = await import('axios');
const { createServer } = await import('vite');
const transport = axios.getAdapter('http');
let jar = '', records = [], pending = 0, phaseStart = 0;
axios.defaults.adapter = async config => {
  if (!['/auth/config', '/auth/login', '/auth/refresh', '/auth/me', '/auth/logout', '/tipos-informe', '/areas'].includes(config.url)) {
    throw new Error('Petición fuera del alcance de la medición de acceso.');
  }
  const requestRecords = records;
  const started = performance.now();
  const offset = phaseStart;
  pending += 1;
  config.baseURL = origin + '/api';
  config.headers.set('Origin', origin);
  if (jar) config.headers.set('Cookie', jar);
  try {
    const response = await transport(config);
    const cookie = response.headers['set-cookie']?.find(c => c.startsWith('naxji_refresh='));
    if (cookie) jar = cookie.split(';')[0];
    requestRecords.push({ method: config.method, path: config.url, status: response.status, ms: Math.round(performance.now() - started), start_ms: Math.round(started - offset), end_ms: Math.round(performance.now() - offset) });
    return response;
  } catch (e) {
    requestRecords.push({ method: config.method, path: config.url, status: e.response?.status || 0, ms: Math.round(performance.now() - started), start_ms: Math.round(started - offset), end_ms: Math.round(performance.now() - offset) });
    throw e;
  } finally { pending -= 1; }
};
const settle = async predicate => {
  const started = performance.now();
  while (performance.now() - started < 180000) {
    await act(async () => { await new Promise(r => setTimeout(r, 30)); });
    if (predicate()) return;
  }
  throw new Error('Estado esperado no alcanzado; no se registra contenido sensible.');
};
const enter = async (id, value) => {
  const el = document.getElementById(id);
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
};
let vite, root;
async function mount(path) {
  if (root) await act(async () => root.unmount());
  if (vite) await vite.close();
  window.history.replaceState(null, '', path);
  vite = await createServer({ ...(baseline ? { root: resolve('.venv/login-baseline') } : {}),
    logLevel: 'error', server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  const { default: App } = await vite.ssrLoadModule('/src/adapters/in/web/App.jsx');
  root = createRoot(document.getElementById('root'));
  const started = performance.now();
  phaseStart = started;
  await act(async () => root.render(React.createElement(React.StrictMode, null,
    React.createElement(BrowserRouter, null, React.createElement(App)))));
  return started;
}
try {
  for (let i = 0; i < 3; i++) {
    records = [];
    const start = await mount('/');
    await settle(() => pending === 0 && records.some(r => r.path === '/auth/config' && r.status === 200)
      && document.querySelector('form button[type="submit"]')?.disabled === false);
    const anonymous = { ms: Math.round(performance.now() - start), requests: [...records] };
    records = [];
    if (mode === 'real') {
      await enter('email', credentials.email);
      await enter('password', credentials.password);
    }
    const loginStart = performance.now();
    phaseStart = loginStart;
    let loginVisible = null;
    await act(async () => document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    await settle(() => {
      const asunto = document.getElementById('asunto');
      if (asunto && loginVisible == null) loginVisible = Math.round(performance.now() - loginStart);
      return asunto && !asunto.disabled;
    });
    const login = { ms: Math.round(performance.now() - loginStart), report_visible_ms: loginVisible, requests: [...records] };
    records = [];
    const recoveryStart = await mount('/nuevo-informe');
    let recoveryVisible = null;
    await settle(() => {
      const asunto = document.getElementById('asunto');
      if (asunto && recoveryVisible == null) recoveryVisible = Math.round(performance.now() - recoveryStart);
      return asunto && !asunto.disabled;
    });
    const recovery = { ms: Math.round(performance.now() - recoveryStart), report_visible_ms: recoveryVisible, requests: [...records] };
    records = [];
    const { endSession } = await vite.ssrLoadModule('/src/adapters/in/web/services/session.js');
    await act(async () => { await endSession(); });
    await act(async () => root.unmount());
    root = null;
    await settle(() => pending === 0);
    jar = '';
    output.runs.push({ anonymous, login, recovery });
    console.log(JSON.stringify({ phase, mode, run: i + 1, anonymous: anonymous.ms, login: login.ms, recovery: recovery.ms }));
  }
} catch {
  output.failure = 'Medición incompleta. Revisar estados HTTP; se omiten cuerpos y credenciales.';
  process.exitCode = 1;
  console.error(output.failure);
} finally {
  credentials = null;
  if (root) await act(async () => root.unmount());
  if (vite) await vite.close();
  dom.window.close();
  await mkdir('docs/evidencias', { recursive: true });
  await writeFile(`docs/evidencias/login-${phase}-${mode}.json`, JSON.stringify(output, null, 2));
}
// Ejecutar desde la raíz. Real: JSON {email,password} únicamente por stdin.
// No escribe solicitudes; solo Auth (sesión local de prueba) y catálogos GET.
// --baseline lee la copia de src/adapters/in/web, package.json, index.html y
// vite.config.js del commit anterior en .venv/login-baseline (git archive).
