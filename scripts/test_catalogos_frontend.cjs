// Prueba AISLADA de React: HTTP interceptado, sin Supabase ni credenciales reales.
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require(path.resolve(__dirname,'../venv/ui-check/node_modules/playwright'));
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage();
    const area={id:id(1),codigo:'TEST_AREA',nombre:'Área prueba aislada',activo:true};
    const tipo={id:id(2),codigo:'INFORME_TECNICO',nombre:'Informe Técnico',activo:true};
    const plantilla={id:id(3),tipo_informe_id:tipo.id,nombre:'Plantilla prueba aislada',descripcion:'DEMOSTRACIÓN',activa:true};
    const campos=[{id:id(4),clave:'fecha',etiqueta:'Fecha',tipo_dato:'date',obligatorio:true},
      {id:id(5),clave:'detalle',etiqueta:'Análisis técnico',tipo_dato:'textarea',obligatorio:true}];
    let solicitud=null, prediccion=null, completos=0;
    await page.route('**/api/**',async route => {
      const req=route.request(), url=new URL(req.url());
      const p=url.pathname.slice(4), method=req.method();
      let data, status=200;
      if(p==='/auth/config') data={mode:'supabase',persistence:'postgres'};
      else if(p==='/auth/refresh') data={access_token:'TOKEN_FICTICIO_SOLO_PRUEBA',expires_in:3600};
      else if(p==='/auth/me') data={id:id(6),roles:['FUNCIONARIO'],nombres:'Prueba',activo:true};
      else if(p==='/areas') data=[area];
      else if(p==='/tipos-informe') data=[tipo];
      else if(p==='/plantillas') data=[plantilla];
      else if(p===`/plantillas/${plantilla.id}/campos`) data=campos;
      else if(p==='/solicitudes' && method==='POST') {
        const body=req.postDataJSON();
        assert.equal(body.tipo_informe_id,null); assert.equal(body.plantilla_id,null);
        solicitud={...body,id:id(7),estado:'BORRADOR',valores:[]}; data=solicitud; status=201;
      } else if(p.endsWith('/predecir-contexto')) {
        prediccion={id:id(8),solicitud_id:solicitud.id,tipo_informe:tipo,area_destino:area,
          modelo:'TEST_AISLADO',resultado_validacion:'PENDIENTE',normativas:[],advertencias:['Prueba aislada']}; data=prediccion;
      } else if(p.endsWith('/validar-prediccion')) {
        prediccion.resultado_validacion='CORREGIDA';
        solicitud.tipo_informe_id=tipo.id; solicitud.area_destino_id=area.id; data=prediccion;
      } else if(p.endsWith('/contexto')) data=prediccion;
      else if(p.endsWith('/completa')) { solicitud={...solicitud,...req.postDataJSON()}; completos++; data=solicitud; }
      else if(p===`/solicitudes/${id(7)}` && method==='GET') data=solicitud;
      else { data={detail:'Ruta de fixture no definida'}; status=404; }
      await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
    });
    await page.goto('http://127.0.0.1:5173/nuevo-informe');
    await page.getByLabel('Asunto',{exact:false}).fill('Solo asunto para predecir');
    await page.getByRole('button',{name:'Predecir estructura y contexto'}).click();
    await page.getByText('Contexto sugerido',{exact:true}).waitFor();
    assert.equal(solicitud.plantilla_id,null);
    await page.locator('#tipo-informe').selectOption(tipo.id);
    await page.locator('#area-origen').selectOption(area.id);
    await page.locator('#area-destino').selectOption(area.id);
    await page.getByRole('button',{name:'Corregir con mis datos'}).click();
    await page.getByText('Contexto confirmado. La plantilla anterior no coincide con el tipo propuesto; seleccione una nueva.',{exact:true}).waitFor();
    await page.locator('#plantilla').selectOption(plantilla.id);
    await page.getByLabel('Fecha',{exact:false}).waitFor();
    await page.getByRole('button',{name:'Guardar datos',exact:true}).click();
    await page.getByText('Complete el campo obligatorio: Fecha.',{exact:true}).waitFor();
    assert.equal(completos,0);
    await page.getByLabel('Fecha',{exact:false}).fill('2026-09-29');
    await page.getByLabel('Análisis técnico',{exact:false}).fill('Solo datos de fixture');
    await page.getByRole('button',{name:'Guardar datos',exact:true}).click();
    await page.getByText('Datos del informe guardados correctamente.',{exact:true}).waitFor();
    assert.equal(completos,1);
    await page.reload();
    await page.getByText('Solicitud recuperada de la base de datos.',{exact:true}).waitFor();
    assert.equal(await page.getByLabel('Fecha',{exact:false}).inputValue(),'2026-09-29');
    assert.equal(await page.getByLabel('Análisis técnico',{exact:false}).inputValue(),'Solo datos de fixture');
    assert.equal(await page.locator('#area-origen').inputValue(),area.id);
    assert.equal(completos,1);
    console.log('REACT_AISLADO: asunto solo, correccion, obligatorios, guardado unico y recarga: OK');
    console.log('HTTP_INTERCEPTADO: esta prueba NO verifica Supabase Auth ni PostgreSQL.');
  } finally { await browser.close(); }
})().catch(e=>{console.error('PRUEBA_REACT_AISLADA_FALLO:',e.message);process.exitCode=1;});
