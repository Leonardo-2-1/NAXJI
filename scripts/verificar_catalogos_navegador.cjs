// Inicio manual real. No graba contraseñas, cookies ni tokens en archivos o logs.
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const { chromium } = require(path.join(root, 'venv/ui-check/node_modules/playwright'));
const origin = 'http://127.0.0.1:5173';
const resumeId = process.argv.find(arg => arg.startsWith('--solicitud='))?.split('=')[1];
if (resumeId && !/^[0-9a-f-]{36}$/i.test(resumeId)) throw new Error('UUID de solicitud inválido');
const check = (condition, label) => { if (!condition) throw new Error(label); console.log(label + ': OK'); };

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: false });
  const tokens = {};
  let phase = 'login-A';
  let saved;
  const pages = [];
  try {
    for (const [letter, email] of [['A','funcionario1.naxji@gmail.com'],['B','funcionario2.naxji@gmail.com']]) {
      phase = 'login-' + letter;
      const context = await browser.newContext();
      const page = await context.newPage();
      page.setDefaultTimeout(60000);
      pages.push(page);
      const verified = page.waitForResponse(async r => {
        if (new URL(r.url()).pathname !== '/api/auth/me' || r.status() !== 200) return false;
        return (await r.json()).email === email;
      }, { timeout: 1200000 });
      verified.catch(() => {});
      await page.goto(origin);
      await page.getByLabel('Correo electrónico').fill(email);
      await page.getByLabel('Contraseña').focus();
      await page.bringToFront();
      console.log('ESPERANDO_LOGIN_MANUAL_' + letter);
      const me = await verified;
      tokens[letter] = (await me.request().headerValue('authorization')).slice(7);
      await page.waitForURL('**/nuevo-informe');
      check((await me.json()).roles.includes('FUNCIONARIO'), 'LOGIN_REAL_' + letter);
      if (letter === 'B') continue;
      phase = 'catalogos-formulario';
      await page.locator('#tipo-informe option').nth(4).waitFor({ state: 'attached' });
      check(await page.locator('#area-origen option').count() === 10, 'REACT_NUEVE_AREAS');
      check(await page.locator('#tipo-informe option').count() === 5, 'REACT_CUATRO_TIPOS');
      if (resumeId) {
        phase = 'recuperar-solicitud-existente';
        const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/solicitudes/'+resumeId && r.request().method()==='GET');
        await page.goto(origin+'/nuevo-informe?solicitud='+encodeURIComponent(resumeId));
        const recovered = await response;
        check(recovered.status()===200,'REACT_RECUPERA_SOLICITUD_EXISTENTE');
        saved=await recovered.json();
        check(saved.asunto.includes('DEMO_PMV1_') && saved.valores.length===7,'SOLICITUD_DEMO_EXISTENTE_SIETE_VALORES');
        await page.getByText('Solicitud recuperada de la base de datos.',{exact:true}).waitFor();
        for (const item of saved.valores) {
          check(await page.locator('#campo-'+item.campo_plantilla_id).inputValue()===item.valor,'REACT_RECUPERA_CAMPO_EXISTENTE');
        }
        console.log('REANUDACION_SIN_CREAR_SOLICITUD: OK');
        continue;
      }
      const asunto = 'Evaluación técnica del mantenimiento de parques y áreas verdes. DEMO_PMV1_' + crypto.randomUUID();
      await page.getByLabel('Asunto', { exact: false }).fill(asunto);
      const predictionResponse = page.waitForResponse(r => r.url().endsWith('/predecir-contexto'));
      await page.getByRole('button', {name:'Predecir estructura y contexto'}).click();
      const prediction = await predictionResponse;
      check(prediction.status()===200, 'RF_IA_DESDE_ASUNTO_SIN_SELECCIONES');
      await page.locator('#tipo-informe').selectOption({ label:'Informe Técnico' });
      await page.locator('#area-origen').selectOption({ label:'Subgerencia de Gestión Ambiental' });
      await page.locator('#area-destino').selectOption({ label:'Subgerencia de Gestión Ambiental' });
      const confirmed = page.waitForResponse(r => r.url().endsWith('/validar-prediccion'));
      await page.getByRole('button', {name:'Corregir con mis datos'}).click();
      check((await confirmed).status()===200, 'CONFIRMACION_EXPLICITA_CONTEXTO');
      await page.locator('#plantilla').selectOption({ label:'Informe Técnico – Piloto NAXJI' });
      await page.getByLabel('Fecha', {exact:false}).waitFor();
      check(await page.locator('[id^="campo-"]').count()===7, 'REACT_SIETE_CAMPOS_DINAMICOS');
      await page.getByRole('button', {name:'Guardar datos',exact:true}).click();
      await page.getByText('Complete el campo obligatorio: Fecha.',{exact:true}).waitFor();
      console.log('REACT_RECHAZA_OBLIGATORIO_VACIO: OK');
      await page.getByLabel('Número o referencia').fill('DEMO-PMV1-SIN-VALOR-OFICIAL');
      await page.getByLabel('Fecha', {exact:false}).fill('2026-09-29');
      for (const label of ['Antecedentes','Objetivo del informe','Análisis técnico','Conclusiones','Recomendaciones']) {
        await page.getByLabel(label,{exact:false}).fill('DEMOSTRACIÓN NAXJI: '+label+'. Datos de prueba sin valor institucional.');
      }
      const written = page.waitForResponse(r => r.url().endsWith('/completa') && r.request().method()==='PUT');
      await page.getByRole('button', {name:'Guardar datos',exact:true}).click();
      const result=await written;
      check(result.status()===200,'REACT_GUARDADO_ATOMICO_SUPABASE');
      saved=await result.json();
      check(saved.valores.length===7,'SIETE_VALORES_PERSISTIDOS');
      await page.reload();
      await page.getByText('Solicitud recuperada de la base de datos.',{exact:true}).waitFor();
      check(await page.locator('#asunto').inputValue()===asunto,'REACT_RECUPERA_ASUNTO_TRAS_RECARGA');
      for (const item of saved.valores) {
        check(await page.locator('#campo-'+item.campo_plantilla_id).inputValue()===item.valor,'REACT_RECUPERA_CAMPO');
      }
      check(new URL(page.url()).searchParams.get('solicitud')===saved.id,'URL_RECUPERA_MISMA_SOLICITUD');
    }
    phase='sql-reinicio-rls';
    const child=spawn(path.join(root,'.venv/Scripts/python.exe'),[path.join(root,'scripts/verificar_catalogos_sesion.py')],
      {cwd:root,windowsHide:true,stdio:['pipe','pipe','pipe']});
    child.stdout.on('data',d=>process.stdout.write(d));
    child.stderr.on('data',()=>{});
    child.stdin.end(JSON.stringify({tokens,solicitud:saved,reuse_servers:process.argv.includes('--existing-servers')}));
    check(await new Promise(resolve=>child.on('close',resolve))===0,'VERIFICACION_SQL_REINICIO_RLS');
    phase='logout';
    for (const page of pages) {
      await page.getByRole('button',{name:'Cerrar sesión'}).click();
      await page.waitForURL(origin+'/');
    }
    console.log('LOGOUT_REACT_A_B: OK');
    console.log('CATALOGOS_PMV1_NAVEGADOR_COMPLETO: OK');
  } catch (error) {
    console.error('CATALOGOS_NAVEGADOR_INCOMPLETO: '+phase+'; '+error.name+'; sin datos privados.');
    process.exitCode=1;
  } finally {
    await browser.close();
  }
})();
