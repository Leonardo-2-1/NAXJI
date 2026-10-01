import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { progresoInforme } from "../../src/adapters/in/web/services/progresoInforme.js";

const completo = {
  form: { asunto: "PRUEBA ficticia", tipoInformeId: "t", areaDestinoId: "a", areaOrigenId: "a",
    plantillaId: "p", valores: { texto: "Sin resultados registrados", numero: 0, booleano: false } },
  prediccion: { id: "prediccion" }, contextoVigente: true, asuntoPredicho: "PRUEBA ficticia",
  plantillas: [{ id: "p", activa: true, tipo_informe_id: "t", area_id: "a" }],
  campos: [
    { id: "texto", tipo_dato: "textarea", activo: true, obligatorio: true },
    { id: "numero", tipo_dato: "number", activo: true, obligatorio: true },
    { id: "booleano", tipo_dato: "boolean", activo: true, obligatorio: true },
  ], idCampos: "p", estadoPlantillas: "listo",
};

test("el indicador retrocede al cambiar asunto o perder la confirmación", () => {
  assert.equal(progresoInforme(completo).pasoDisponible, 3);
  assert.equal(progresoInforme({ ...completo, informe: { numero_version: 1 } }).pasoDisponible, 4);
  assert.equal(progresoInforme({ ...completo, contextoVigente: false }).pasoDisponible, 2);
  assert.equal(progresoInforme({ ...completo, contextoVigente: false, prediccion: null }).pasoDisponible, 1);
  assert.equal(progresoInforme({ ...completo, contextoVigente: false, asuntoPredicho: "Anterior" }).pasoDisponible, 1);
});

test("el borrador exige plantilla compatible, campos cargados, origen y datos obligatorios", () => {
  for (const cambios of [
    { estadoPlantillas: "cargando" }, { estadoPlantillas: "error" }, { idCampos: "otra" },
    { plantillas: [] }, { plantillas: [{ ...completo.plantillas[0], activa: false }] },
    { form: { ...completo.form, plantillaId: "" } }, { form: { ...completo.form, areaOrigenId: "" } },
    { form: { ...completo.form, valores: { ...completo.form.valores, texto: "  " } } },
    { form: { ...completo.form, valores: { ...completo.form.valores, numero: "no numérico" } } },
  ]) {
    const p = progresoInforme({ ...completo, ...cambios });
    assert.equal(p.pasoDisponible, 3, JSON.stringify(cambios));
    assert.equal(p.datosListos, false);
  }
  assert.equal(progresoInforme(completo).datosListos, true, "Cero y false son valores completos");
});

test("recuperación y reintento siguen accesibles aunque la plantilla guardada ya no esté activa", () => {
  for (const estado of ["PROCESANDO", "GENERADA"]) {
    const p = progresoInforme({ ...completo, solicitud: { estado }, plantillas: [], idCampos: "" });
    assert.equal(p.pasoDisponible, 3);
    assert.equal(p.datosListos, false);
  }
});

test("el indicador expone el paso actual y deshabilita los pasos futuros para teclado", async () => {
  const vite = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: Pasos } = await vite.ssrLoadModule("/src/adapters/in/web/components/PasosInforme.jsx");
    const html = renderToStaticMarkup(React.createElement(Pasos, { actual: 2, disponible: 2, onChange() {} }));
    assert.equal((html.match(/aria-current="step"/g) || []).length, 1);
    assert.equal((html.match(/disabled=""/g) || []).length, 2);
    assert.match(html, /aria-label="Pasos para crear el informe"/);
    assert.match(html, /aria-controls="panel-paso-4"/);
    assert.match(html, /Completado · Revisar/);
  } finally { await vite.close(); }
});
