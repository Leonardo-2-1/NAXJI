import test from "node:test";
import assert from "node:assert/strict";
import {
  armarValores, construirValidacion, crearVigencia, esConfirmada,
  plantillaCompatible, seleccionInicial, valoresDePlantilla,
} from "../../src/adapters/in/web/services/flujoInforme.js";

const propuesta = {
  id: "prediccion", resultado_validacion: "PENDIENTE",
  tipo_informe: { id: "tipo-1" }, area_destino: { id: "area-1" },
  normativas: [{ normativa_id: "n-1", aceptada: null }, { normativa_id: "n-2", aceptada: null }],
};
const seleccion = { tipoInformeId: "tipo-1", areaDestinoId: "area-1", normativaIds: ["n-1", "n-2"] };

test("aceptar envía únicamente ID y ACEPTADA, independientemente del orden de las normas", () => {
  assert.deepEqual(construirValidacion(propuesta, { ...seleccion, normativaIds: ["n-2", "n-1"] }), {
    prediccion_id: "prediccion", resultado: "ACEPTADA",
  });
});

for (const cambios of [{ tipoInformeId: "tipo-2" }, { areaDestinoId: "area-2" }, { normativaIds: ["n-2"] }, { normativaIds: [] }]) {
  test(`corregir envía los tres campos, incluso sin normas: ${JSON.stringify(cambios)}`, () => {
    const s = { ...seleccion, ...cambios };
    assert.deepEqual(construirValidacion(propuesta, s), {
      prediccion_id: "prediccion", resultado: "CORREGIDA",
      tipo_informe_id: s.tipoInformeId, area_destino_id: s.areaDestinoId, normativa_ids: s.normativaIds,
    });
  });
}

test("impide normas externas, repetidas o contexto incompleto", () => {
  for (const normativaIds of [["externa"], ["n-1", "n-1"]]) {
    assert.throws(() => construirValidacion(propuesta, { ...seleccion, normativaIds }));
  }
  assert.throws(() => construirValidacion(propuesta, { ...seleccion, tipoInformeId: "" }));
});

test("rechazar no envía campos de corrección", () => {
  assert.deepEqual(construirValidacion(propuesta, seleccion, true), { prediccion_id: "prediccion", resultado: "RECHAZADA" });
});

test("recuperar CORREGIDA usa los IDs guardados y respeta normas descartadas", () => {
  const corregida = { ...propuesta, resultado_validacion: "CORREGIDA", normativas: [
    { normativa_id: "n-1", aceptada: false }, { normativa_id: "n-2", aceptada: true },
  ] };
  assert.deepEqual(seleccionInicial({ tipo_informe_id: "tipo-2", area_destino_id: "area-2" }, corregida), {
    tipoInformeId: "tipo-2", areaDestinoId: "area-2", normativaIds: ["n-2"],
  });
  assert.equal(esConfirmada(corregida), true);
  assert.equal(esConfirmada(propuesta), false);
});

test("una plantilla debe estar activa y corresponder al tipo y destino confirmados", () => {
  const p = { activa: true, tipo_informe_id: "tipo-1", area_id: "area-1" };
  assert.equal(plantillaCompatible(p, "tipo-1", "area-1"), true);
  assert.equal(plantillaCompatible(p, "tipo-2", "area-1"), false);
  assert.equal(plantillaCompatible(p, "tipo-1", "area-2"), false);
  assert.equal(plantillaCompatible({ ...p, activa: false }, "tipo-1", "area-1"), false);
});

test("recupera valores vigentes sin perder false/cero ni copiar campos ajenos", () => {
  const campos = [{ id: "a", activo: true }, { id: "b", activo: true }, { id: "c", activo: false }];
  assert.deepEqual(valoresDePlantilla(campos, { a: false, b: 0, c: "inactivo", otro: "ajeno" }), { a: false, b: 0 });
  assert.deepEqual(armarValores(campos, { a: false, b: 0 }), [
    { campo_plantilla_id: "a", valor: false }, { campo_plantilla_id: "b", valor: 0 },
  ]);
});

test("una respuesta tardía no puede restaurar la predicción tras editar el asunto", async () => {
  const control = crearVigencia();
  let resolver;
  const respuesta = new Promise(resolve => { resolver = resolve; });
  const vigente = control.capturar();
  let visible = null;
  const pendiente = respuesta.then(p => { if (vigente()) visible = p; });
  control.invalidar();
  resolver(propuesta);
  await pendiente;
  assert.equal(visible, null);
  assert.equal(control.capturar()(), true);
});
