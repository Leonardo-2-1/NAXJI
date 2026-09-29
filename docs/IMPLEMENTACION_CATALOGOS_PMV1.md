# Catálogos institucionales y plantilla piloto PMV1

Fecha de consulta documental y ejecución: 2026-09-29. Proyecto local:
`C:\Users\DELL INSPIRON\Documents\NAXJI`. Rama `main`.

## Objetivo y diagnóstico

Permitir que un funcionario autenticado consulte catálogos PostgreSQL, complete
una plantilla técnica piloto, guarde una solicitud con sus valores y la recupere.
Se conservan FastAPI, React, puertos/casos de uso, unidad de trabajo, repositorios
PostgreSQL, autenticación Supabase y controles de propietario de la etapa anterior.
Los cambios anteriores estaban sin commit y se conservaron; no se hizo push.

Inspección previa: `docs/VERIFICACION_SUPABASE.md`, esquema
`NAXJI_database_schema_actual.sql`, repositorios en `src/adapters/out/persistence`,
contenedor, servicios/casos de uso, controladores, esquemas y `NuevoInforme.jsx`.
La consulta real encontró 0 áreas, 4 tipos activos, 0 plantillas, 0 campos y 0 normas;
14 políticas RLS SELECT para authenticated. No se recrearon tablas ni cuentas.

El formulario ya consultaba FastAPI, pero no tenía catálogos utilizables, obligaba
a completar todo antes de predecir y perdía su estado al recargar. El guardado en
dos peticiones podía dejar cabecera actualizada con valores sin guardar.

## Datos cargados y fuentes

La vista previa real ejecutó las inserciones dentro de una transacción y terminó
con rollback. Se presentó el contenido antes de aplicar `--apply`. La carga
confirmada conserva los UUID de los cuatro tipos existentes y añade UUID generados
por PostgreSQL, nunca UUID inventados para representar catálogos reales.

Fuentes oficiales consultadas:

- [Portal municipal de El Tambo](https://munieltambo.gob.pe/), enlace ROF.
- [Ficha oficial ROF](https://www.gob.pe/institucion/munieltambo/informes-publicaciones/3945274-reglamento-de-organizacion-y-funciones-rof).
- [ROF 2020 PDF](https://cdn.www.gob.pe/uploads/document/file/4258543/MDT_ROF_2020.pdf.pdf), artículo 6, páginas 7-8, y organigrama página 67.
- [Portal de Transparencia, Planeamiento y organización](https://transparencia.gob.pe/enlaces/pte_transparencia_enlaces.aspx?id_entidad=11090&id_tema=5&ver=), que mantiene ROF y organigrama 2020 como los más recientes listados al consultar.

El navegador de búsqueda devolvió 418/403 para ciertos enlaces. La descarga
directa del PDF oficial mediante HTTPS funcionó (200, 67 páginas escaneadas).
Se revisaron visualmente las páginas indicadas; el índice de Transparencia y el
sitio municipal se contrastaron. Es la estructura publicada que se pudo verificar,
no una certificación de ausencia de modificaciones institucionales no publicadas.

Catálogo **parcial** de órganos verificados, con capitalización normalizada:

| Código funcional NAXJI | Nombre | Padre cargado |
| --- | --- | --- |
| MDT_CONCEJO | Concejo Municipal | — |
| MDT_ALCALDIA | Alcaldía | MDT_CONCEJO |
| MDT_GM | Gerencia Municipal | MDT_ALCALDIA |
| MDT_GSP | Gerencia de Servicios Públicos | MDT_GM |
| MDT_GDT | Gerencia de Desarrollo Territorial | MDT_GM |
| MDT_GDE | Gerencia de Desarrollo Económico | MDT_GM |
| MDT_GAJ | Gerencia de Asesoría Jurídica | MDT_GM |
| MDT_SGGA | Subgerencia de Gestión Ambiental | MDT_GSP |
| MDT_SGDUR | Subgerencia de Desarrollo Urbano y Rural | MDT_GDT |

Los códigos MDT_* pertenecen al software; no se presentan como numeración oficial.
La misma fuente y fecha se documentan en el SQL y descripciones de los registros.
La administración futura debe incorporar nuevas áreas con su fuente y revisión.
Esta etapa gestiona la carga idempotente y consulta; no agrega un panel CRUD
administrativo para editar catálogos institucionales.

Se conservan los tipos `INFORME_TECNICO`, `INFORME_LEGAL`, `INFORME_INSPECCION`,
`MEMORANDO` sin actualizaciones. Total posterior: **9 áreas, 4 tipos, 1 plantilla,
7 campos y 1 referencia normativa documental**. Los registros exactos y sus UUID
confirmados están en [evidencia de carga](evidencias/catalogos-carga-20260929.txt).
Los UUID de la vista previa corresponden a su transacción revertida y no se reutilizan.

### Normativas

Se agregó únicamente `MDT_ROF_2020`, tipo `REGLAMENTO`, con título, URL oficial y
descripción del alcance de verificación. Número, publicación, inicio y fin de
vigencia permanecen NULL porque no se comprobaron esas fechas jurídicas. El año
del título no se convirtió en una fecha inventada. `activo=true` significa
disponible como documento de catálogo, **no dictamen de vigencia jurídica**.
No se cargaron las etiquetas normativas ficticias de la PoC.

Para ampliar se necesitan textos oficiales identificados, publicación, modificaciones,
derogaciones y revisión jurídica de su pertinencia. La falta de fecha final nunca
se interpreta como confirmación de vigencia.

## Plantilla piloto

Nombre `Informe Técnico – Piloto NAXJI`, versión 1, tipo `INFORME_TECNICO`, sin
restricción a una sola área. Su descripción identifica expresamente la demostración
y la ausencia de aprobación como formato oficial municipal.

| Orden | Clave | Etiqueta | Tipo | Obligatorio |
| --- | --- | --- | --- | --- |
| 1 | referencia_documento | Número o referencia del documento | text | No |
| 2 | fecha | Fecha | date | Sí |
| 3 | antecedentes | Antecedentes | textarea | Sí |
| 4 | objetivo | Objetivo del informe | textarea | Sí |
| 5 | detalle | Análisis técnico | textarea | Sí |
| 6 | conclusiones | Conclusiones | textarea | Sí |
| 7 | recomendaciones | Recomendaciones | textarea | Sí |

Todos activos, configuración JSON `{}`: no necesitan opciones de selección. La
referencia es opcional porque el PMV1 no implementa numeración oficial. Se conserva
`detalle` por compatibilidad con el generador actual. Fecha exige formato ISO válido.

Asunto y áreas origen/destino existen en `solicitudes`, por lo que no se duplican
en `campos_plantilla`. El origen se precarga del perfil si existe; si no, el usuario
lo elige para esta solicitud sin modificar su perfil. El autor se obtiene de la
sesión validada, nunca de un ID enviado por React. Al generar, el caso de uso agrega
`contenido.encabezado` con asunto, nombres de áreas y UUID del autor propietario;
los siete campos se conservan en `contenido.datos`. Objetivo, conclusiones y
recomendaciones proporcionados por el usuario se preservan. El generador sigue
identificado como MOCK: no se integró un LLM ni se produjo un informe oficial.

## Integración y contratos

Sin cambios de ruta para las operaciones existentes:

- `GET /areas`, `/tipos-informe`, `/plantillas?tipo_informe_id=UUID`, `/plantillas/{id}/campos` usan repositorios PostgreSQL cuando el modo es postgres.
- `POST /solicitudes`, `PUT /solicitudes/{id}` y `PUT /solicitudes/{id}/valores` conservan el guardado incompleto como BORRADOR. Es necesario para solicitar predicción desde el asunto.
- Nuevos `POST /solicitudes/completa` y `PUT /solicitudes/{id}/completa` reciben cabecera y `valores` juntos. Requieren tipo, plantilla, origen/destino y todos los campos obligatorios. El caso de uso reutiliza los existentes dentro de una sola unidad de trabajo: cualquier error revierte cabecera y valores.
- Nuevo `GET /solicitudes/{id}/contexto` permite recuperar la última predicción después de recargar; aplica el mismo control de propietario.
- Respuestas de área incluyen padre y descripción; plantilla incluye su descripción; predicción añade `advertencias`. Son extensiones aditivas.

React mantiene un solo formulario, consulta UUID reales, filtra plantillas por tipo,
renderiza los campos y usa el guardado completo. Conserva únicamente el identificador
en `?solicitud=UUID`; al recargar consulta de nuevo datos y contexto al backend.
No guarda datos del formulario ni credenciales de PostgreSQL en el navegador.
La sesión continúa con token de acceso en memoria y renovación por cookie HttpOnly.
Un fallo de recuperación bloquea el guardado para evitar crear accidentalmente otra
solicitud. Un estado no editable se presenta sin permitir nuevas modificaciones.

Se rechazaron con 400/404 referencias inexistentes, inactivas, tipo incompatible,
campos de otra plantilla y formularios completos sin obligatorios. Los modelos
HTTP rechazan duplicados/UUID malformados con 422. Las rutas previas de borrador
siguen admitiendo incompletos; estos no se presentan como formularios completos.

### RF-IA-01

El botón de predicción solo requiere asunto. El backend existente ya lo permitía;
no se cambió ese contrato ni se reentrenó el modelo. Se guardan propuestas pendientes
y se exige aceptar/corregir explícitamente antes de generar.

Correspondencias de encaminamiento propuestas: AREA_SERVICIOS_PUBLICOS→MDT_GSP,
AREA_DESARROLLO_ECONOMICO→MDT_GDE, AREA_ASESORIA_JURIDICA→MDT_GAJ,
AREA_ECOLOGIA→MDT_SGGA, AREA_DESARROLLO_URBANO→MDT_SGDUR. Son decisiones de
integración sujetas a revisión humana, no equivalencias institucionales certificadas
ni resultados experimentales de precisión. Se resuelven por código hacia UUID reales.
AREA_RIESGO_DESASTRES no tiene correspondencia verificada en esta carga y produce
un error controlado; no se inventa una subgerencia.

Las etiquetas normativas sin documento correspondiente se omiten de las FK y se
reportan como advertencias visibles. Se conserva la sugerencia de tipo/área sin
afirmar que el contexto normativo esté resuelto. Una categoría principal ausente
o inactiva sigue rechazándose. La confirmación humana que cambia el contexto y
vuelve incompatible la plantilla despeja esta y sus valores de manera transaccional;
el formulario pide seleccionar nuevamente. Este cambio de comportamiento es explícito.

## Evidencias ejecutadas

- [Vista previa](evidencias/catalogos-preview-20260929.txt): inserciones previstas, segunda ejecución sin cambios, rollback.
- [Carga confirmada](evidencias/catalogos-carga-20260929.txt): COMMIT; cero actualizaciones.
- [Suite anterior](evidencias/catalogos-pytest-inicial-20260929.txt): 75 passed, 1 skipped.
- [Pruebas nuevas iniciales](evidencias/catalogos-pruebas-nuevas-20260929.txt): 10 passed, 1 failed. Descubrieron que el timestamp HTTP no coincidía con el fijado por el trigger PostgreSQL.
- Corrección: el repositorio vuelve a leer la solicitud y sus valores dentro de la misma transacción antes de responder; no modifica triggers.
- [Suite completa posterior](evidencias/catalogos-pytest-final-20260929.txt): **86 passed, 1 skipped, 1 warning**, 107.56 s. Incluye piloto recuperado con todos sus valores y timestamps desde otro proceso.
- La prueba Auth que solicita archivo privado de contraseñas se omite deliberadamente: el usuario eligió login manual. La advertencia de Starlette sobre httpx es deprecación, no fallo.
- Compilación Vite inicial falló por restricción del entorno (`spawn EPERM`); al ejecutar con permiso de creación de procesos terminó correctamente. [Build](evidencias/catalogos-build-20260929.txt).
- [Lint](evidencias/catalogos-lint-20260929.txt) pasó; compileall terminó con código 0 y pip check respondió `No broken requirements found.`
- [React aislado](evidencias/catalogos-react-aislado-20260929.txt): asunto sin selecciones, corrección explícita, obligatorios, guardado único y recarga pasaron. Usa HTTP interceptado y no se presenta como integración Supabase.
- [Inferencia con modelo existente](evidencias/catalogos-predictor-real-20260929.txt): SKLEARN_RF_IA_01 resolvió tipo y área a UUID reales; 0 normas verificadas, 2 advertencias. Es una comprobación funcional de correspondencias, no una evaluación de precisión.
- Verificación real del navegador: **aprobada**. [Recorrido React](evidencias/catalogos-navegador-reanudado-20260929.txt) y [cierre SQL/autorización/RLS](evidencias/catalogos-navegador-cierre-20260929.txt). Ambos logins fueron ingresados manualmente por el usuario.

Las pruebas HTTP automatizadas de PostgreSQL inyectan la identidad únicamente en
TestClient; no equivalen a probar Supabase Auth. RLS se comprobó además con
`SET LOCAL ROLE authenticated`, UUID de perfil existente y una fila temporal
inactiva invisible. La transacción se revirtió. La prueba entre procesos crea una
solicitud propia con prefijo TEST_PILOTO y elimina solo esa solicitud al finalizar.

## Comandos PowerShell

Desde la raíz NAXJI; no crear de nuevo los entornos existentes:

```powershell
# Vista previa reversible y carga ya aplicada (repetible)
.\.venv\Scripts\python.exe .\scripts\cargar_catalogos.py
.\.venv\Scripts\python.exe .\scripts\cargar_catalogos.py --apply

# Diagnóstico PostgreSQL independiente, entorno ligero existente
.\venv\db-check\Scripts\python.exe .\scripts\verificar_supabase.py --crud

# Backend: usar el entorno con FastAPI/modelos
$env:NAXJI_PERSISTENCE_MODE = 'postgres'
$env:NAXJI_AUTH_MODE = 'supabase'
$env:NAXJI_AUTH_COOKIE_SECURE = 'false'
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000

# En otra terminal
npm.cmd run dev -- --host 127.0.0.1 --port 5173

# Pruebas
$env:NAXJI_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q -rs -p no:cacheprovider
npm.cmd run lint
npm.cmd run build
node .\scripts\verificar_catalogos_navegador.cjs
# Solo el recorrido funcional, reutilizando React/FastAPI encendidos:
node .\scripts\verificar_catalogos_navegador.cjs --existing-servers
# Recuperar la misma demostración, sin insertar otra solicitud:
node .\scripts\verificar_catalogos_navegador.cjs --existing-servers --solicitud=7fdecf2a-4931-4a5e-9502-73ea42f15395
```

El verificador de navegador requiere Playwright ya instalado de forma aislada
en `venv/ui-check` y Edge. Pide login manual A y B, nunca passwords por chat ni
archivos. Conserva una solicitud claramente marcada DEMO_PMV1 como evidencia;
no altera solicitudes preexistentes. Tokens del test viajan solo en memoria/stdin.
No se agregaron dependencias de ejecución. PyMuPDF se instaló exclusivamente en
`venv/document-tools` para inspeccionar el PDF, sin tocar requirements.txt.

## Pendientes y límites

La comprobación manual React–FastAPI–Supabase quedó completada. Ampliar el
catálogo parcial si se requieren otros órganos; validar institucionalmente las
correspondencias del predictor y obtener revisión jurídica de normas. No hay
formato oficial aprobado, numeración oficial, LLM/RAG, ni evidencia de rendimiento
del modelo en esta institución. Los repositorios PostgreSQL usan el rol servidor
configurado: la API controla propietario/roles y la Data API usa RLS; son capas
diferentes y ambas deben probarse.

## Archivos y resumen de cambios

El [listado completo de rutas absolutas](evidencias/catalogos-archivos-20260929.md)
identifica los archivos de código, SQL, pruebas y README de esta etapa.
El [diff de la etapa](evidencias/catalogos-cambios-20260929.patch) compara contra
la copia previa a catálogos, incluyendo archivos que aún no estaban versionados.
Así no atribuye a esta etapa los cambios de Auth/PostgreSQL anteriores que también
aparecen en `git diff`. El listado incluye el recuento de líneas por archivo.

| Archivos (rutas relativas a la raíz indicada arriba) | Motivo |
| --- | --- |
| database/seeds/pmv1_catalogos.sql | Carga independiente, transaccional y solo inserciones |
| scripts/cargar_catalogos.py | Vista previa con rollback, validación de relaciones y repetición idempotente |
| scripts/verificar_catalogos_navegador.cjs | Recorrido real React con login manual A/B; reanudación por UUID y reutilización de servidores |
| scripts/verificar_catalogos_sesion.py | Contrastar SQL y RLS con sesiones solo en memoria; entrada UTF-8 explícita; reinicio opcional |
| scripts/test_catalogos_frontend.cjs | Prueba aislada de interacciones React sin credenciales ni PostgreSQL |
| src/application/use_cases/guardar_solicitud_completa.py | Guardar cabecera y valores completos con rollback conjunto |
| src/application/use_cases/obtener_contexto.py | Recuperación autorizada de la última predicción |
| src/application/use_cases/validar_prediccion.py | Desvincular plantilla incompatible al confirmar otro contexto |
| src/application/use_cases/generar_borrador.py | Incorporar encabezado de solicitud sin campos duplicados |
| src/infrastructure/configuration/container.py | Componer los dos casos de uso nuevos con los puertos existentes |
| src/adapters/in/controllers/solicitud_controller.py | Rutas aditivas de guardado completo |
| src/adapters/in/controllers/ia_controller.py | Recuperación de contexto y documentación del predictor real |
| src/adapters/in/controllers/catalogo_controller.py | Describir catálogos según modo e incluir jerarquía |
| src/adapters/in/schemas/solicitud_request.py | Contrato explícito del formulario completo y validación de duplicados |
| src/adapters/in/schemas/catalogo_response.py | Descripción piloto y jerarquía de áreas |
| src/adapters/in/schemas/prediccion_response.py | Advertencias visibles sobre correspondencias incompletas |
| src/domain/entities/catalogo.py; src/domain/entities/plantilla.py | Conservar metadatos que ya existen en SQL |
| src/adapters/out/persistence/postgres.py | Responder con timestamps fijados realmente por PostgreSQL |
| src/adapters/out/ai/context_predictor_catalogo.py | Resolver códigos MDT y omitir FK normativas no verificadas con aviso |
| src/adapters/out/ai/generador_borrador_mock.py | Preservar objetivo, conclusiones y recomendaciones ingresados |
| src/adapters/in/web/pages/NuevoInforme.jsx | Recuperación, origen, guardado completo, predicción desde asunto y etiquetas accesibles |
| src/adapters/in/web/services/solicitudService.js; src/adapters/in/web/services/iaService.js | Consumir las rutas aditivas |
| tests/test_catalogos_pmv1.py; tests/test_catalogos_supabase.py | Validaciones, atomicidad, PostgreSQL, RLS e idempotencia |
| README.md | Comandos actuales y distinción entre modo real y fixtures de memoria |

Documentación nueva: `C:\Users\DELL INSPIRON\Documents\NAXJI\docs\IMPLEMENTACION_CATALOGOS_PMV1.md`.
Evidencias nuevas: archivos `catalogos-*` en
`C:\Users\DELL INSPIRON\Documents\NAXJI\docs\evidencias\`.
No se modificaron `.env`, cuentas, perfiles, roles, políticas RLS ni el esquema base.
La [comparación de integridad](evidencias/catalogos-integridad-20260929.txt) confirma
conservación de filas originales de las 14 tablas, cuentas y hashes de contraseñas;
`.env` intacto y no versionado; secretos ausentes de archivos versionables y dist.
El [diagnóstico CRUD](evidencias/catalogos-crud-20260929.txt) pasó SELECT 1, SSL,
14 tablas, conteo real de 4 tipos y CRUD con rollback, cero filas temporales restantes.

## Cierre funcional con sesiones reales — 2026-09-29

Se reanudó únicamente la prueba funcional solicitada. Al comenzar, React en 5173,
FastAPI `/health` en 8000 y `/api/auth/config` devolvieron HTTP 200; configuración
real `supabase`/`postgres`. Se reutilizaron los servidores existentes: no se arrancaron
servidores duplicados ni se reinició el backend en esta reanudación. La prueba de
persistencia entre procesos ya estaba acreditada por la suite anterior y no se repitió.

Primer recorrido, con contraseñas introducidas directamente en Edge:

```text
LOGIN_REAL_A: OK
REACT_NUEVE_AREAS: OK
REACT_CUATRO_TIPOS: OK
RF_IA_DESDE_ASUNTO_SIN_SELECCIONES: OK
CONFIRMACION_EXPLICITA_CONTEXTO: OK
REACT_SIETE_CAMPOS_DINAMICOS: OK
REACT_RECHAZA_OBLIGATORIO_VACIO: OK
REACT_GUARDADO_ATOMICO_SUPABASE: OK
SIETE_VALORES_PERSISTIDOS: OK
REACT_RECUPERA_ASUNTO_TRAS_RECARGA: OK
URL_RECUPERA_MISMA_SOLICITUD: OK
LOGIN_REAL_B: OK
```

El log también contiene siete verificaciones `REACT_RECUPERA_CAMPO: OK`. La
comprobación SQL siguiente inicialmente falló: `React_solicitud_confirmada_SQL:
FALLÓ`. Se identificó `sys.stdin.encoding=cp1252` en Windows, mientras Node enviaba
JSON UTF-8. Esto alteraba tildes del asunto en el comparador, aunque React y SQL
conservaban correctamente el texto. Se corrigió solo el verificador con
`sys.stdin.reconfigure(encoding='utf-8')`, sin modificar datos ni aplicación.

Se recuperó la misma solicitud por UUID y se repitieron manualmente los logins
porque el verificador había cerrado sus ventanas al fallar. No se creó otra solicitud.
Resultados reales del cierre:

```text
REANUDACION_SIN_CREAR_SOLICITUD: OK
LOGIN_REAL_B: OK
React_solicitud_confirmada_SQL: OK
Siete_valores_React_iguales_SQL: OK
Servidor_existente_recupera_piloto: OK
Persistencia_y_recuperacion_servidor_existente: OK
Funcionario_B_lectura_ajena_403: OK
Funcionario_B_contexto_ajeno_403: OK
Funcionario_B_escritura_ajena_403: OK
Endpoint_areas_UUID_reales_PostgreSQL: OK
RLS_Data_API_A: OK
RLS_Data_API_B: OK
LOGOUT_REACT_A_B: OK
CATALOGOS_PMV1_NAVEGADOR_COMPLETO: OK
```

La verificación RLS usó los JWT reales contra la Data API de Supabase: A recibió
una fila y B cero filas para la misma solicitud. Los intentos HTTP de B devolvieron
403 sin alterar el asunto. No se simularon identidades en esta prueba funcional.
El resumen heredado del script `VERIFICACION_SQL_REINICIO_RLS: OK` incluye la palabra
reinicio, pero **no hubo reinicio en este recorrido con `--existing-servers`**; los
resultados detallados anteriores son los que delimitan la evidencia actual.

Solicitud de demostración conservada: `7fdecf2a-4931-4a5e-9502-73ea42f15395`.
Asunto identificado con `DEMO_PMV1_e0e63274-9c56-462d-96f0-1d0ee7f7862a`, sin valor
institucional. Para consultarla, iniciar sesión con funcionario1 y abrir:
`http://127.0.0.1:5173/nuevo-informe?solicitud=7fdecf2a-4931-4a5e-9502-73ea42f15395`.
Quedaron guardados los siete valores de la plantilla piloto existente.

En esta reanudación solo se ajustaron los dos verificadores y la documentación/
evidencias. No se recrearon usuarios, tablas, plantillas ni catálogos. No se solicitaron
contraseñas por chat ni se almacenaron contraseñas/tokens en archivos. Las sesiones
del test se transmitieron por stdin y ambos usuarios cerraron sesión correctamente.
No se repitieron pytest, lint ni build: sus resultados previos siguen documentados
como pruebas de la implementación, y las modificaciones del verificador pasaron
`py_compile` y `node --check` (código 0).

## Estado por componente

| Componente | Estado anterior | Implementación realizada | Evidencia | Estado final |
| --- | --- | --- | --- | --- |
| Áreas municipales | Vacío | 9 órganos con jerarquía del ROF publicado | PDF pp. 7-8/67, carga SQL, RLS | Comprobado; catálogo parcial |
| Tipos de informe | 4 registros | Conservados, UUID reales | HTTP/SQL y hashes | Comprobado |
| Plantillas | Vacío | Piloto técnico versión 1, identificado como demostración | SQL y GET /plantillas | Comprobado |
| Campos de plantilla | Vacío | 7 configurables; asunto/áreas en solicitud | SQL, GET campos, 7 valores recuperados | Comprobado |
| Normativas | Vacío | 1 ROF documental con fuente y límites explícitos | PDF y carga SQL | Documento verificado; curación jurídica pendiente |
| Catálogos FastAPI | PostgreSQL integrado, catálogos vacíos | Consultas activas, metadatos y validaciones | Pruebas HTTP con repositorios reales | Comprobado |
| Formulario React | Sin recuperación; guardado en dos pasos | Guardado completo, recuperación por URL y campos dinámicos | Recorrido real con login manual, SQL y siete valores tras recarga | Comprobado React–FastAPI–Supabase |
| Integración RF-IA-01 | Selecciones previas obligatorias en UI | Asunto primero, mapeo real, avisos y confirmación | Tests de sugerencia/mapeo; sin reentrenamiento | Parcial: categorías y normas pendientes |
| Pruebas automatizadas | 75 aprobadas, 1 omitida | 11 nuevas; regresión completa y cierre funcional | 86 passed, 1 skipped; logins reales A/B, HTTP 403 y RLS | Comprobado; omisión de prueba con archivo de contraseñas suplida por login manual |
