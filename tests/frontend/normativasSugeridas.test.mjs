import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { construirValidacion, seleccionInicial } from "../../src/adapters/in/web/services/flujoInforme.js";

test("presenta temas separados, fuentes y selección recuperada por documento", async () => {
  const vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: Normativas } = await vite.ssrLoadModule("/src/adapters/in/web/components/NormativasSugeridas.jsx");
    const p = { id: "p", tipo_informe: { id: "t" }, area_destino: { id: "a" }, resultado_validacion: "CORREGIDA",
      temas_normativos: [{ codigo: "NORM_RESIDUOS", etiqueta: "Tema residuos", confianza: 0.82, normativa_ids: ["n1", "n2"] },
        { codigo: "NORM_RUIDO", etiqueta: "Tema ruido", confianza: 0.7, normativa_ids: [] }],
      normativas: ["n1", "n2"].map((id, i) => ({ normativa_id: id, codigo: id, titulo: `DOCUMENTO FICTICIO ${id}`,
        confianza: 0.82, aceptada: i === 1, correspondencias: [{ etiqueta: "NORM_RESIDUOS", verificado_en: "2000-01-02",
          vigencia: "VIGENTE", ambito: "Ámbito de prueba", justificacion: "Fixture",
          fuente_url: "https://www.gob.pe/", fuente_vigencia_url: "https://www.gob.pe/" }] })) };
    const seleccion = seleccionInicial({ tipo_informe_id: "t", area_destino_id: "a" }, p);
    assert.deepEqual(seleccion.normativaIds, ["n2"]);
    const validacion = construirValidacion(p, seleccion);
    assert.equal(validacion.resultado, "CORREGIDA");
    assert.deepEqual(validacion.normativa_ids, ["n2"]);
    const html = renderToStaticMarkup(React.createElement(Normativas, { prediccion: p, seleccionadas: seleccion.normativaIds, onChange() {} }));
    assert.match(html, /Confianza temática/);
    assert.match(html, /no acredita vigencia ni aplicabilidad jurídica/);
    assert.match(html, /Solo se identificó el tema/);
    assert.match(html, /Documento oficial/);
    assert.equal((html.match(/type="checkbox"/g) || []).length, 2);
    assert.equal((html.match(/checked=""/g) || []).length, 1);
    p.normativas[0].correspondencias[0].fuente_url = "javascript:alert(1)";
    const safe = renderToStaticMarkup(React.createElement(Normativas, { prediccion: p, seleccionadas: [], onChange() {} }));
    assert.doesNotMatch(safe, /javascript:/);
    const legacy = renderToStaticMarkup(React.createElement(Normativas, { prediccion: { normativas: [{ normativa_id: "old", titulo: "Anterior" }] }, seleccionadas: [], onChange() {} }));
    assert.match(legacy, /sin evidencia de correspondencia documental/);
  } finally { await vite.close(); }
});
