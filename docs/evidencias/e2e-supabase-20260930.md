# Verificación de integración NAXJI — 2026-09-30

**Pasó el flujo autenticado por HTTP con Supabase en la nube y Ollama real. La comprobación visual sigue pendiente.** La herramienta no tiene navegadores disponibles; no pudo abrir Chrome ni el navegador integrado. Se usó la API a través del proxy de React, sin operar la interfaz renderizada.

Las credenciales proporcionadas por el usuario permitieron usar una cuenta existente autorizada. Se recibieron por stdin y permanecieron en memoria; los archivos de evidencia no contienen correos, contraseñas, tokens, conexiones ni IDs de usuarios. No se crearon usuarios ni se usaron overrides de autenticación.

## Código y archivos

- Main local y remoto: `b639d5d417956b7b81413d85ec6f22b06bb5a98a`.
- Se conservaron la eliminación previa de `requirements.txt` y los directorios no seguidos `.postman/` y `postman/`.
- Sin cambios al código de aplicación, predictor, plantillas, migraciones ni configuración privada. Sin commit ni push.
- Archivos añadidos: este informe y [evidencia JSON](e2e-supabase-20260930.json). Auxiliares locales sin credenciales en `.venv/e2e-current/`, ignorado por Git.

## Acceso real y selector demo

El backend previo en 8000 responde `mock`/`memory`; por eso React en 5173 muestra usuarios demo. `src/adapters/in/web/pages/Login.jsx:34` selecciona ese formulario según `/auth/config`. No se modificó el formulario.

Se dejó activa una instancia independiente de FastAPI en 8001 con `supabase`/`postgres` y React en **http://localhost:5174**, con proxy hacia ella. Esta dirección admite correo y contraseña reales. La configuración se aplicó al proceso, sin cambiar `.env`. Al cerrar estas instancias temporales, iniciar con la configuración original conserva el modo original.

## Comprobaciones iniciales

Consultas READ ONLY confirmaron las columnas JSONB `secciones_salida` en `plantillas` y `versiones_informe`, y la plantilla técnica piloto activa, versión 1, con cinco secciones: antecedentes, objetivo, análisis técnico, conclusiones y recomendaciones. Las cuatro primeras son obligatorias. No se ejecutaron migraciones ni semillas.

HTTP 200: `/health`, `/auth/config` directo y por proxy, React, Supabase Auth `/auth/v1/health` y Ollama `/api/tags`. Ollama tiene `qwen2.5:7b`. Catálogos sin sesión y refresh sin cookie devolvieron 401.

## Resultados de los escenarios

| Paso | Resultado |
| --- | --- |
| 1. Login y catálogos | Pasó por HTTP real: login, perfil autorizado, tipos, áreas, plantillas y campos: 200. Interfaz visual pendiente. |
| 2. Solo asunto y predicción | Creación 201 sin tipo, destino ni plantilla. Predicción 200: `SKLEARN_RF_IA_01`, `RF-IA-01-200CASOS-v1`, `es_mock=false`. |
| 3. Confirmar y descartar normas | Parcial: `CORREGIDA`, tipo técnico, área y `normativa_ids: []`: 200; selección vacía recuperada y verificada en SQL. No hubo normas propuestas seleccionables que descartar. |
| 4. Plantilla y campos | Guardado 200 con todos los obligatorios y ausencia explícita de resultados. Estado `LISTA_PARA_GENERAR`. Datos compatibles recuperados por UUID y SQL. |
| 5. Generación | 201, `qwen2.5:7b`, cinco secciones y encabezado del backend. Se contrastaron asunto, nombres de áreas y autor con la sesión sin registrar su identidad. Modelo, estructura y contenido confirmados en SQL. |
| 6. Edición y recuperación | Actualización 200 a versión 2; recuperación 200 después de renovación y nueva sesión. SQL confirma ambas versiones y encabezado conservado. Recarga visual pendiente. |
| 7. Fallo y reintento | URL aislada: 503/`OLLAMA_NO_DISPONIBLE`. Recuperación 200 en `LISTA_PARA_GENERAR` con datos conservados. Reintento sobre la misma solicitud: 201. SQL confirma un informe único. |

La generación principal tardó **21,926 s** y el reintento **17,457 s**, incluyendo el recorrido HTTP, autenticación y persistencia. La prueba auxiliar directa del generador con plantilla leída de Supabase tardó 15,927 s. No son mediciones exclusivas de inferencia.

La lista `secciones_salida` de cada versión conserva el orden: `antecedentes`, `objetivo`, `analisis_tecnico`, `conclusiones`, `recomendaciones`. El orden interno de claves JSONB no gobierna la presentación.

## Revisión del contenido ficticio

Asuntos identificados como `PRUEBA NAXJI E2E 2026-09-30 PRINCIPAL` y `REINTENTO`, sobre inspección de un parque ficticio sin resultados. Campos del fixture `tests/fixtures/inspeccion_parque_sin_resultados.json`.

Ambas respuestas indican que la inspección no está registrada, no existen resultados, mediciones, fotografías ni hallazgos y se desconoce el estado del césped, limpieza e infraestructura. Mantienen conclusiones pendientes y no recomiendan mantenimiento basado en defectos inventados. El JSON conserva los textos ficticios, excluyendo el encabezado con identidad del autor. Se verifican estas respuestas concretas, no una garantía general contra invenciones.

La versión 2 cambia conclusiones a una revisión humana ficticia que mantiene la falta de resultados. Su origen es `USUARIO` y `modelo_ia` nulo; la versión 1 conserva `qwen2.5:7b` y origen `IA`.

## Limitación normativa

SQL de solo lectura encontró **una norma activa y cero coincidencias con los once códigos normativos del predictor**. `src/adapters/out/ai/context_predictor_catalogo.py:42` busca los códigos; líneas 43–45 omiten los inexistentes/inactivos y generan advertencias. Las predicciones devolvieron cero normas seleccionables.

Pasó la persistencia de selección vacía. **El descarte individual de una norma predicha no pudo verificarse con estos catálogos.** No se inventaron correspondencias, normas ni citas, ni se modificó predictor o catálogo para fabricar el resultado. Las pruebas unitarias no sustituyen esa comprobación pendiente en la nube.

## Aislamiento y restauración

El backend temporal en 8002 usó Supabase real y una URL Ollama hacia un puerto efímero de loopback reservado sin escucha. El error expuso solo `detail` y `codigo`. El reintento usó el backend funcional en 8001. Se detuvieron únicamente los procesos del backend de fallo; Ollama y la aplicación funcional siguen activos. No hubo cambios en `.env` que restaurar. El último auxiliar cerró su sesión con 204.

## Registros ficticios conservados

SQL READ ONLY limitado a estos IDs confirmó estado `GENERADA`, valores idénticos al fixture, validación `CORREGIDA`, cero normas aceptadas, un informe por solicitud, estructura y versiones. No se borraron registros.

| Caso | Solicitud | Informe | Versiones |
| --- | --- | --- | --- |
| Principal | `3f97b19b-9f03-479e-934b-f7d59287fd9d` | `6283b8b3-8213-4c83-ad39-5a16b7119fe6` | 1 y 2 |
| Reintento | `61fc6f36-da7a-44fb-b43d-85b84d5c4b0a` | `e4a9181d-8c04-4b52-af5f-f799921ec7bd` | 1 |

El JSON incluye además IDs de predicciones y versiones ficticias.

- [Abrir borrador principal](http://localhost:5174/nuevo-informe?solicitud=3f97b19b-9f03-479e-934b-f7d59287fd9d&informe=6283b8b3-8213-4c83-ad39-5a16b7119fe6)
- [Abrir borrador del reintento](http://localhost:5174/nuevo-informe?solicitud=61fc6f36-da7a-44fb-b43d-85b84d5c4b0a&informe=e4a9181d-8c04-4b52-af5f-f799921ec7bd)

## Comprobaciones automáticas y límites

- Python: **141 aprobadas, 15 omitidas**, 2,47 s. Optativas omitidas no cuentan como aprobadas. Una advertencia de deprecación Starlette/TestClient sobre httpx.
- Frontend: **14 aprobadas**.
- `npm run lint` y `npm run build`: correctos.

El auxiliar inicial comparaba valores incluyendo timestamps que los triggers actualizan al guardar estado. Se corrigió la comprobación para comparar contenido por campo y se revalidó la misma solicitud. No fue un defecto de conservación de datos de la aplicación.

No se reprodujo otro defecto de código en los escenarios ejecutados. Quedan pendientes interacción y recarga visual de React, descarte de una norma seleccionable y comportamiento de cookies en navegador. Para el refresh HTTP, httpx envió explícitamente su propia cookie; no implementa la excepción de navegador para cookies `Secure` en localhost. No se afirma una verificación completa con interfaz.
