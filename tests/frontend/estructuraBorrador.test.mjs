import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { seccionesDelBorrador, validarSeccionesBorrador } from "../../src/adapters/in/web/services/estructuraBorrador.js";

const fixtures = JSON.parse(await readFile(new URL("../fixtures/estructuras_demostrativas.json", import.meta.url), "utf8"));

test("las dos estructuras conservan orden, títulos y obligatoriedad", () => {
  for (const fixture of fixtures) {
    const informe = { ...fixture, estructura_legacy: false, contenido: {} };
    assert.deepEqual(seccionesDelBorrador(informe), fixture.secciones_salida);
    const contenido = Object.fromEntries(fixture.secciones_salida.filter(s => s.obligatoria).map(s => [s.clave, "Revisión"]));
    assert.doesNotThrow(() => validarSeccionesBorrador(informe, contenido));
    contenido[fixture.secciones_salida[0].clave] = " ";
    assert.throws(() => validarSeccionesBorrador(informe, contenido), /Complete la sección/);
  }
});

test("versiones antiguas conservan secciones de texto adicionales sin convertir metadatos en campos", () => {
  const informe = { contenido: { antecedentes: "A", desarrollo: "D", conclusiones: "C", objetivo: "O",
    encabezado: { asunto: "Asunto guardado" }, datos: { fecha: "2020-01-01" }, instrucciones: "Instrucciones antiguas" } };
  assert.deepEqual(seccionesDelBorrador(informe).map(s => s.clave), ["antecedentes", "desarrollo", "conclusiones", "objetivo"]);
  assert.doesNotThrow(() => validarSeccionesBorrador(informe, informe.contenido));
});

test("editor React presenta encabezado legible y solo edita secciones ordenadas de la versión", async () => {
  const vite = await createServer({ server: { middlewareMode: true }, appType: "custom" });
  try {
    const { default: Editor } = await vite.ssrLoadModule("/src/adapters/in/web/components/EditorBorrador.jsx");
    for (const fixture of fixtures) {
      const contenido = { encabezado: { asunto: "Asunto guardado", area_origen: "Origen guardado", autor_id: "id-autor" },
        datos: { fecha: "2020-01-01" }, ...Object.fromEntries(fixture.secciones_salida.map(s => [s.clave, "Texto"])) };
      const html = renderToStaticMarkup(React.createElement(Editor, { informe: { ...fixture, estructura_legacy: false, contenido }, contenido, onChange: () => {} }));
      assert.match(html, /Asunto guardado/);
      assert.match(html, /Emisor \/ unidad remitente/);
      assert.doesNotMatch(html, /textarea[^>]*id="contenido-(encabezado|datos)"/);
      const ids = [...html.matchAll(/<textarea[^>]*id="contenido-([^"]+)"/g)].map(m => m[1]);
      assert.deepEqual(ids, fixture.secciones_salida.map(s => s.clave));
      for (const seccion of fixture.secciones_salida) assert.ok(html.includes(seccion.titulo));
    }
  } finally { await vite.close(); }
});
