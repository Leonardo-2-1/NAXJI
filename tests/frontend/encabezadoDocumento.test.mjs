import assert from "node:assert/strict";
import test from "node:test";
import { datosOficiales, plantillaPosterior } from "../../src/adapters/in/web/services/encabezadoDocumento.js";

test("inspección v1 no se confunde con técnica v2; avisa solo de una versión compatible de la misma familia", () => {
  const inspeccion = { id: "i", nombre: "Informe de Inspección – Piloto NAXJI", tipo_informe_id: "i", area_id: "a", version: 1 };
  const tecnica = { ...inspeccion, id: "t", nombre: "Informe Técnico – Piloto NAXJI", tipo_informe_id: "t" };
  const tecnicaV2 = { ...tecnica, id: "t2", version: 2 };
  const catalogo = [inspeccion, tecnica, tecnicaV2];
  assert.equal(plantillaPosterior(catalogo, "i"), undefined);
  assert.equal(plantillaPosterior(catalogo, "t"), tecnicaV2);
  assert.equal(plantillaPosterior([...catalogo, { ...inspeccion, id: "i2", area_id: "otra", version: 2 }], "i"), undefined);
});

test("encabezado histórico conserva denominaciones legibles y nunca expone UUIDs", () => {
  const uuid = "11111111-1111-4111-8111-111111111111";
  const datos = datosOficiales({ autor_id: uuid, area_origen: uuid, area_destino: "Unidad guardada" });
  assert.equal(datos.emisor, "");
  assert.equal(datos.destinatario, "Unidad guardada");
  assert.equal(datos.firmante, "");
  assert.equal(JSON.stringify(datos).includes(uuid), false);
  assert.equal(datosOficiales({ documento: { emisor: "Nombre aportado", fecha: "2026-10-01" } }).emisor, "Nombre aportado");
});
