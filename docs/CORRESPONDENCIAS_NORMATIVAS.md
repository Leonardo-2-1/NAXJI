# Correspondencias normativas — revisión del 1 de octubre de 2026

Implementación preparada para revisión. **No se aplicó SQL ni se modificaron datos de Supabase.** Su publicación posterior en GitHub fue solicitada por el usuario; los scripts SQL siguen pendientes de aplicación.

## Inventario inicial y tabla de brechas

La consulta inicial a Supabase utilizó `SET TRANSACTION READ ONLY`. Se inspeccionaron `information_schema.columns` y `public.normativas`. El catálogo tiene un único documento activo: `MDT_ROF_2020`, Reglamento de Organización y Funciones de El Tambo. Número y fechas jurídicas están a NULL; su descripción distingue disponibilidad documental de vigencia. El esquema admite código, título, tipo, número, publicación, inicio/fin de vigencia, fuente, descripción y activo. No tenía relaciones explícitas con temas del predictor.

Se leyó `mlb.joblib` sin modificarlo: las once clases coinciden exactamente con los textos de las etiquetas de `datos_demo.py`. Los códigos siguientes son identificadores técnicos de temas; no son números de normas. La columna «existente» se refiere exclusivamente al catálogo inicial de Supabase, no a documentos encontrados posteriormente.

| Etiqueta del modelo / tema literal | Norma existente que podría corresponder | Fuente consultada | Estado de verificación | Brecha y decisión |
| --- | --- | --- | --- | --- |
| `NORM_RESIDUOS` — Normativa municipal sobre gestión de residuos sólidos | Ninguna; el ROF no acredita esa correspondencia | Catálogo inicial; [DL 1278 en SINIA](https://sinia.minam.gob.pe/normas/ley-gestion-integral-residuos-solidos); [reglamento en SINIA](https://sinia.minam.gob.pe/normas/aprueban-reglamento-decreto-legislativo-ndeg-1278-decreto-legislativo) | Dos referencias nacionales verificadas documentalmente, aún fuera de Supabase | Propuesta de dos documentos y dos relaciones, nunca ordenanzas locales inventadas |
| `NORM_RUIDO` — Normativa municipal sobre prevención y control de contaminación sonora | Ninguna acreditada | Catálogo inicial y [ROF](https://cdn.www.gob.pe/uploads/document/file/4258543/MDT_ROF_2020.pdf.pdf) | Pendiente | No se verificó documento específico ni relación; sin semilla |
| `NORM_COMERCIO_AMBULATORIO` — Normativa municipal sobre comercio ambulatorio y uso de espacios públicos | Ninguna acreditada | Catálogo inicial / ROF | Pendiente | Falta documento concreto, alcance y revisión de vigencia |
| `NORM_DESARROLLO_URBANO` — Normativa municipal sobre desarrollo urbano y edificaciones | Ninguna acreditada | Catálogo inicial / ROF | Pendiente | No equiparar funciones organizativas con regulación sectorial |
| `NORM_LICENCIAS` — Normativa municipal sobre licencias de funcionamiento | Ninguna acreditada | Catálogo inicial / ROF | Pendiente | Falta documento concreto y revisión normativa |
| `NORM_ITSE` — Normativa aplicable a inspecciones técnicas de seguridad en edificaciones | Ninguna acreditada | Catálogo inicial / ROF | Pendiente | Falta documento concreto y revisión normativa |
| `NORM_SERVICIOS_PUBLICOS` — Normativa municipal sobre gestión de servicios públicos | ROF solo como antecedente organizativo; no se acredita equivalencia normativa | Catálogo inicial / ROF | Pendiente, no asignado | El tema es amplio: no se traduce automáticamente al ROF ni a toda norma de residuos |
| `LPAG` — Ley del Procedimiento Administrativo General | Ninguna en el catálogo | [Control de cambios SUNAT](https://www.sunat.gob.pe/legislacion/procedim/normasadua/gja-01/ctrlCambios/index.htm); [TUO oficial](https://diariooficial.elperuano.pe/Normas/obtenerDocumento?idNorma=12) | Se identificó el nuevo TUO DS 006-2026-JUS; correspondencia pendiente | No cargar DS 004-2019-JUS como TUO vigente. Revisar íntegramente nuevo texto y fe de erratas antes de proponer carga |
| `NORM_FISCALIZACION_SANCIONES` — Normativa municipal sobre fiscalización y sanciones administrativas | Ninguna acreditada | Catálogo inicial / ROF | Pendiente | Un ROF no sustituye el régimen sancionador ni acredita infracciones |
| `NORM_CONTRATACION_PUBLICA` — Normativa de contratación pública aplicable | Ninguna acreditada | Catálogo inicial / ROF | Pendiente | Falta identificar régimen temporal, documentos y ámbito del caso |
| `NORM_TRANSPARENCIA` — Normativa de transparencia y acceso a la información pública | Ninguna acreditada | Catálogo inicial / ROF | Pendiente | Falta documento concreto y revisión de vigencia |

La [ficha municipal de la Ordenanza 012-2020-MDT/CM/SO](https://www.gob.pe/institucion/munieltambo/normas-legales/6695032-012-2020-mdt-cm-so) identifica aprobación del ROF el 30/07/2020. Esto no acredita por sí solo su vigencia actual, texto consolidado ni equivalencia con las etiquetas sectoriales. No se actualizó su registro ni se añadió una relación a él. No se afirma haber agotado todos los documentos municipales existentes.

## Documentos propuestos y límites de verificación

1. **Decreto Legislativo 1278**, Ley de Gestión Integral de Residuos Sólidos, publicación 23/12/2016. SINIA identifica el documento, alcance nacional y estado vigente, e informa modificaciones por DL 1501 y Ley 32212. Su ámbito incluye gestión y manejo de residuos municipales. Se propone `PE_DL_1278`, tipo del esquema `DECRETO`, relacionado temáticamente con `NORM_RESIDUOS`. [Fuente oficial SINIA](https://sinia.minam.gob.pe/normas/ley-gestion-integral-residuos-solidos).
2. **Decreto Supremo 014-2017-MINAM**, Reglamento del DL 1278, publicación **21/12/2017**, comprobada en la cabecera de El Peruano; su objeto comprende gestión de residuos y limpieza pública. SINIA lo clasifica vigente. Existe modificación por DS 001-2022-MINAM, identificada también en la publicación oficial del 09/01/2022. Se propone `PE_DS_014_2017_MINAM`, también asociado a `NORM_RESIDUOS`. [Publicación original, páginas 18–19](https://www.minam.gob.pe/wp-content/uploads/2018/06/ds_014-2017-minam_-RRSS.pdf), [estado SINIA](https://sinia.minam.gob.pe/normas/aprueban-reglamento-decreto-legislativo-ndeg-1278-decreto-legislativo), [publicación de modificación](https://www.leyes.congreso.gob.pe/Documentos/2021_2026/Boletin_de_Normas_Legales/2022/NL20220109.pdf).

**Discrepancia registrada:** la ficha SINIA del DS muestra 31/12/2017; la edición original de El Peruano muestra 21/12/2017. La propuesta utiliza la publicación original. No se confunde publicación con inicio de vigencia: no se rellenaron fechas jurídicas de inicio/fin no verificadas.

«VERIFICADA» significa que un curador documentó identificación, fuente oficial, ámbito y estado de vigencia según la fuente consultada en una fecha determinada. No significa revisión jurídica exhaustiva de todas las modificaciones, aplicabilidad automática al expediente ni artículos verificados. El catálogo registra `VIGENTE_CON_MODIFICACIONES`, y la interfaz muestra esa condición y la fecha de consulta. Los textos originales no se presentan como consolidaciones vigentes de todos sus artículos. La asociación a residuos es una decisión temática explícita basada en el objeto de los documentos; no declara que sean ordenanzas de El Tambo.

Para LPAG, SUNAT identifica DS 006-2026-JUS como vigente y DS 004-2019-JUS como derogado; El Peruano publica además una [fe de erratas](https://busquedas.elperuano.pe/dispositivo/EX/2515226-1). No se incluyó LPAG en la semilla por quedar pendiente la revisión íntegra para esta incorporación.

## Implementación y compatibilidad

- `normativa_correspondencias` tiene clave `(etiqueta, normativa_id)`: relaciones 0..N, con revisión por cada asociación. Documentos y temas siguen siendo conceptos separados.
- Solo se proponen relaciones activas, `VERIFICADA`, con fuentes oficiales HTTPS, identidad documental y metadatos completos, estado vigente documentado y fechas compatibles. El dominio oficial es un filtro técnico; la verificación del contenido sigue siendo una tarea de curación humana.
- No se busca una norma por igualdad entre su código y una etiqueta, ni por similitud del título. El ROF existente no se convierte en un comodín. Los temas sin relación quedan visibles con advertencia, sin inventar una FK normativa.
- Dos temas pueden apuntar al mismo documento: aparece una sola casilla, con ambas procedencias. El antiguo campo `confianza` conserva compatibilidad y representa el máximo de las confianzas temáticas, no una probabilidad jurídica.
- Se guarda una instantánea de tema, documento y evidencia en `predicciones_ia.parametros`, que ya es JSONB. No se cambia el esquema de predicciones ni de informes.
- `ACEPTADA` confirma toda la propuesta. Para descartar una referencia se usa `CORREGIDA` con tipo, área y `normativa_ids`; no se admiten normas externas. La selección persiste en `prediccion_normativas.aceptada`.
- Antes de confirmar y de generar se comprueba la correspondencia vigente del catálogo contra la evidencia guardada; se repite al finalizar la inferencia. Si se retira o cambia, se exige analizar y confirmar de nuevo; también se permite descartar la referencia retirada. Un fallo libera la reserva del borrador.
- Se conservan lectura y edición de versiones/predicciones anteriores. En la UI las propuestas antiguas sin evidencia muestran revisión pendiente; no se fabrica una verificación retrospectiva. El contrato anterior del generador sigue tratando las referencias aceptadas como contenido jurídico no verificado.
- Sin la nueva tabla, el repositorio devuelve cero correspondencias y se muestran temas pendientes. No se ejecuta SQL de creación desde el backend ni se cambia a datos ficticios. Errores de conexión/permisos siguen siendo errores controlados de persistencia.
- El modelo sklearn, su umbral, etiquetas y artefactos no cambian. El flujo asunto → confirmación → plantilla → borrador, control de roles y campos obligatorios permanece igual.
- Ollama recibe solo referencias aceptadas y sus nombres. Sus reglas existentes prohíben inventar artículos, obligaciones, vigencia, aplicabilidad o hallazgos. No se incorporó RAG ni se enviaron textos legales como citas verificadas.

## Contrato HTTP aditivo

`POST /solicitudes/{id}/predecir-contexto`, `GET /solicitudes/{id}/contexto` y la validación conservan sus campos anteriores. Añaden:

```json
{
  "temas_normativos": [
    {
      "codigo": "NORM_RESIDUOS",
      "etiqueta": "Normativa municipal sobre gestión de residuos sólidos",
      "confianza": 0.78,
      "normativa_ids": ["<UUID del documento propuesto>"]
    }
  ],
  "normativas": [
    {
      "normativa_id": "<UUID del documento propuesto>",
      "codigo": "PE_DL_1278",
      "titulo": "Decreto Legislativo N.º 1278 — Ley de Gestión Integral de Residuos Sólidos",
      "confianza": 0.78,
      "aceptada": null,
      "orden": 1,
      "correspondencias": [
        {
          "etiqueta": "NORM_RESIDUOS",
          "estado_verificacion": "VERIFICADA",
          "documento_codigo": "PE_DL_1278",
          "documento_titulo": "Decreto Legislativo N.º 1278 — Ley de Gestión Integral de Residuos Sólidos",
          "documento_numero": "1278",
          "documento_url": "https://sinia.minam.gob.pe/normas/ley-gestion-integral-residuos-solidos",
          "documento_publicacion": "2016-12-23",
          "fuente_url": "https://sinia.minam.gob.pe/normas/ley-gestion-integral-residuos-solidos",
          "fuente_vigencia_url": "https://sinia.minam.gob.pe/normas/ley-gestion-integral-residuos-solidos",
          "verificado_en": "2026-10-01",
          "ambito": "Perú; gestión de residuos, incluidos municipales",
          "vigencia": "VIGENTE_CON_MODIFICACIONES",
          "justificacion": "Relación temática; revisar modificaciones y aplicación al caso",
          "confianza_tema": 0.78
        }
      ]
    }
  ]
}
```

El ejemplo abrevia textos, usa un UUID marcador y confianza ilustrativa; no es una nueva predicción. Para un tema sin relación, `normativa_ids` es `[]` y se añade una advertencia. Las predicciones antiguas tienen listas nuevas vacías.

## SQL exacto que debe revisarse antes de Supabase

1. [Migración aditiva completa](../database/migrations/20261001_01_correspondencias_normativas.sql). Crea solo la tabla de correspondencias e índice; FK restrictiva, restricciones de metadatos, RLS, sin acceso directo para PUBLIC/anon/authenticated. El rol privado del backend necesita SELECT; el propietario conserva su acceso normal. No cambia tablas o registros existentes.
2. [Semilla opcional completa](../database/seeds/20261001_referencias_residuos_verificadas.sql). Inserta únicamente los dos documentos nacionales descritos y sus dos relaciones a residuos. No rellena las otras diez etiquetas. Usa una transacción y bloqueo advisory; ante un código existente con identidad diferente aborta y revierte todo. No sobrescribe documentos, no reactiva relaciones retiradas y no altera curación existente.

Los archivos enlazados son el SQL ejecutable exacto propuesto, sin comandos adicionales ni marcadores por rellenar. Revisar primero las fuentes y el contenido; después, si se decide aplicarlo, ejecutar la migración y luego la semilla. **No ejecutado en Supabase por esta tarea.** No ejecutar fixtures ni scripts de pruebas sobre Supabase.

Para retirar una asociación en una revisión futura, se marca `activa=false` o su estado pendiente/no vigente mediante SQL revisado; no se borran normas que estén referidas por predicciones. Para añadir otra norma hay que registrar su identidad y evidencia, y una relación revisada. Publicación o un catálogo `activo=true` por sí solos no bastan.

## Pruebas y archivos

Resultado final: **164 pruebas Python aprobadas, 13 optativas omitidas**; **15 pruebas frontend aprobadas**; `npm run lint` y `npm run build` correctos. La prueba optativa con Ollama real se ejecutó aparte y pasó. La suite Python conserva una advertencia de deprecación de Starlette/TestClient sobre httpx.

Una lectura final de Supabase confirmó que continúa únicamente `MDT_ROF_2020` y que `normativa_correspondencias` aún no existe allí. El nuevo repositorio devolvió cero correspondencias correctamente en ese estado previo a migración, sin escribir datos.

Las pruebas de PostgreSQL utilizan el clúster aislado loopback, puerto 55433, y bases efímeras `naxji_step3_test_<uuid>` que la fixture crea y elimina. Nunca toman el destino de `.env`. Se probaron migración y semilla repetidas, conservación de filas anteriores y versiones legacy, ausencia de permisos públicos, metadatos incompletos, conflicto con código existente con rollback y no reactivación de curación retirada.

Se verificaron tema sin correspondencia, una norma, varias normas, deduplicación de documento, aceptación completa, descarte individual, selección recuperada en otra instancia PostgreSQL, fuente guardada, referencia retirada o identidad cambiada y retiro durante inferencia. En frontend se comprobaron advertencias, fuentes, selección conservada, contrato CORREGIDA y compatibilidad de propuestas anteriores.

La prueba optativa real usó sklearn de 200 casos, la semilla propuesta, la plantilla piloto y Ollama `qwen2.5:7b` en PostgreSQL efímero. El modelo detectó residuos y se ofrecieron ambos documentos. Se aceptó DL 1278 y descartó DS 014-2017-MINAM. El borrador tardó **44,101 s**, mantuvo las cinco secciones, la falta de resultados y las conclusiones pendientes; no inventó artículos ni citó el documento descartado. [Evidencia de esa respuesta concreta](evidencias/normas-ollama-local-20261001.json). No es una garantía general de exactitud jurídica ni una prueba de Supabase Auth o navegador en esta tarea.

Comandos de comprobación:

```powershell
$env:NAXJI_TEST_PG_PORT='55433' # Solo el clúster aislado de pruebas
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/frontend/*.test.mjs
npm run lint
npm run build
# Optativa: Ollama local ya ejecutándose; no instalar ni configurar otro servicio.
$env:NAXJI_RUN_OLLAMA_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q -s tests/test_correspondencias_postgres.py::test_sklearn_y_ollama_reales_con_semilla_verificada_sin_citas
```

Archivos de implementación modificados/añadidos:

- Dominio: `src/domain/entities/catalogo.py`, `correspondencia_normativa.py`.
- Puerto/repositorios: `src/application/ports/output/catalogo_repository.py`, `src/adapters/out/persistence/catalogo_repository_memory.py`, `postgres.py`.
- Predicción y validación: `src/adapters/out/ai/context_predictor_catalogo.py`, `src/application/use_cases/verificar_referencias_normativas.py`, `validar_prediccion.py`, `generar_borrador.py`.
- API/UI: `src/adapters/in/schemas/prediccion_response.py`, `src/adapters/in/web/components/NormativasSugeridas.jsx`, `src/adapters/in/web/pages/NuevoInforme.jsx`.
- SQL: los dos archivos enlazados arriba.
- Pruebas: `tests/fixtures/normativa_demo.py` (ficticio, solo tests), `tests/test_correspondencias_normativas.py`, `tests/test_correspondencias_postgres.py`, `tests/frontend/normativasSugeridas.test.mjs`, adaptaciones de `tests/test_postgres.py` y `tests/test_catalogos_pmv1.py` al nuevo contrato explícito.
- Documentación: `README.md`, este informe y la evidencia JSON del ensayo local.

Se conservaron sin tocar la eliminación previa de `requirements.txt`, `.postman/`, `postman/` y las evidencias del 30/09. Ningún archivo del predictor entrenado ni de las plantillas fue modificado.
