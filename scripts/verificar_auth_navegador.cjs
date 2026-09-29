// Login manual: las contraseñas solo se escriben en la UI.
// Las sesiones viajan al verificador por stdin, nunca por argv, archivos o logs.
const path = require('node:path');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const { chromium } = require(path.join(root, 'venv/ui-check/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: false });
  const sessions = {};
  const pages = [];
  let phase = 'login';
  try {
    for (const [letter, email] of [['A', 'funcionario1.naxji@gmail.com'], ['B', 'funcionario2.naxji@gmail.com']]) {
      const context = await browser.newContext();
      const page = await context.newPage();
      pages.push(page);
      const verified = page.waitForResponse(async response => {
        if (new URL(response.url()).pathname !== '/api/auth/me' || response.status() !== 200) return false;
        const data = await response.json();
        return data.email === email && data.roles.includes('FUNCIONARIO');
      }, { timeout: 1200000 });
      await page.goto('http://127.0.0.1:5173/');
      await page.getByLabel('Correo electrónico').fill(email);
      await page.getByLabel('Contraseña').focus();
      await page.bringToFront();
      console.log(`ESPERANDO_LOGIN_MANUAL_FUNCIONARIO_${letter}`);
      const response = await verified;
      await page.waitForURL('**/nuevo-informe');
      const header = await response.request().headerValue('authorization');
      const cookie = (await context.cookies()).find(item => item.name === 'naxji_refresh');
      if (!header?.startsWith('Bearer ') || !cookie?.httpOnly || cookie.sameSite !== 'Strict') throw new Error('SESSION_CHECK_FAILED');
      const persisted = await page.evaluate(() => localStorage.getItem('token') || localStorage.getItem('usuario'));
      if (persisted) throw new Error('TOKEN_PERSISTENCE_CHECK_FAILED');
      sessions[letter] = { access_token: header.slice(7), refresh_token: cookie.value };
      console.log(`LOGIN_REACT_SUPABASE_Y_PERFIL_${letter}: OK`);
      console.log(`COOKIE_HTTPONLY_Y_TOKEN_EN_MEMORIA_${letter}: OK`);
    }
    phase = 'backend-verification';
    const child = spawn(path.join(root, '.venv/Scripts/python.exe'),
      [path.join(root, 'scripts/verificar_auth_supabase.py'), '--browser-sessions-stdin'],
      { cwd: root, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    child.stdout.on('data', data => process.stdout.write(data));
    // El verificador emite errores sanitizados por stdout; evita volcar objetos internos.
    child.stderr.on('data', () => {});
    child.stdin.end(JSON.stringify(sessions));
    const code = await new Promise(resolve => child.on('close', resolve));
    if (code !== 0) throw new Error('REAL_AUTH_VERIFICATION_FAILED');
    phase = 'ui-logout';
    for (const page of pages) {
      // El usuario o la gestión de expiración pueden haber regresado ya al login.
      if (new URL(page.url()).pathname !== '/') {
        await page.getByRole('button', { name: 'Cerrar sesión' }).click();
      }
      await page.waitForURL('http://127.0.0.1:5173/');
    }
    console.log('CIERRE_SESION_REACT: OK');
    console.log('VERIFICACION_MANUAL_COMPLETA: OK');
  } catch (error) {
    console.error(`VERIFICACION_MANUAL_NO_COMPLETADA: ${phase}; ${error.name}; sin datos privados.`);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
