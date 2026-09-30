# Integración de Ollama local — 30/09/2026

Generación real implementada conservando el flujo de los pasos 2 y 3, el predictor
sklearn y los SQL existentes. No hay una migración nueva para esta integración.

## Configuración y contrato

Variables **del backend**, leídas por `Settings` desde `.env`, `.env.local` y el
entorno del proceso (este último tiene prioridad):

| Variable | Valor predeterminado | Validación |
| --- | --- | --- |
| `NAXJI_OLLAMA_BASE_URL` | `http://localhost:11434` | HTTP(S), sin usuario, contraseña, query ni fragmento |
| `NAXJI_OLLAMA_MODEL` | `qwen2.5:7b` | Nombre no vacío, sin espacios, hasta 150 caracteres |
| `NAXJI_OLLAMA_TIMEOUT_SECONDS` | `300` | Número finito entre 1 y 1800 |

No se publican en variables `VITE_`, Swagger ni endpoints de configuración. El
modelo utilizado sí se registra en `modelo_ia`, como parte de la trazabilidad de
cada versión. El adaptador comprueba que el modelo de la respuesta coincida con
el solicitado. `Container(..., generador=...)` conserva la inyección de mocks;
los fallos del servicio real nunca activan un mock automáticamente.

`LLMPort.generar(prompt, sistema=..., esquema=...)` recibe por separado las reglas
del sistema, los datos JSON y el esquema de salida. El cuerpo de `/api/generate`
incluye `model`, `system`, `prompt`, `format`, `stream: false` y opciones:
temperatura 0, contexto de 8192 tokens y límite de salida de 2048 tokens.

El esquema se construye a partir de las secciones de la plantilla: un objeto con
propiedades de tipo texto y títulos, `required` según obligatoriedad y
`additionalProperties: false`. El backend vuelve a comprobar claves, tipos,
textos obligatorios no vacíos y claves duplicadas; no intenta reparar una salida
inválida. Ordena el contenido según la lista de secciones. La lista guardada en
cada versión sigue siendo la autoridad de presentación al recuperar desde JSONB.

El contexto incluye nombres de tipo y área confirmados, y solo las normas
aceptadas, resueltas a códigos y títulos de catálogo. No se envían textos jurídicos
supuestos ni se declara verificada su vigencia o aplicabilidad. El encabezado,
incluido el autor, se añade en el servidor y no se solicita al LLM.

Las instrucciones separan datos de reglas: la solicitud y las instrucciones
adicionales no pueden cambiar el contrato. El asunto no prueba que una inspección
haya ocurrido. Sin resultados, el análisis y las conclusiones deben quedar
pendientes; las recomendaciones no pueden presuponer defectos del parque.

Referencias técnicas: [API de generación](https://docs.ollama.com/api/generate) y
[salidas estructuradas](https://docs.ollama.com/capabilities/structured-outputs).

## Transacciones, concurrencia y recuperación

La inferencia ya no ocurre dentro de `UnidadTrabajo.transaccion()`:

1. Una transacción breve bloquea la solicitud, valida asunto/contexto/campos,
   toma copias de plantilla y contexto, y guarda `PROCESANDO`. La reserva usa
   `updated_at` devuelto por el repositorio, incluido el valor del trigger PostgreSQL.
2. Se cierra la transacción y su conexión. Ollama recibe las copias y hace la inferencia.
3. Otra transacción breve verifica estado y timestamp de reserva, vigencia, ausencia
   de informe previo, y que solicitud, plantilla y predicción no hayan cambiado.
   Entonces guarda informe/versión y `GENERADA` de manera atómica.

Mientras la reserva está vigente, otro intento recibe 409 sin llamar a Ollama.
Las operaciones de edición/predicción mantienen su restricción sobre `PROCESANDO`.
Una lectura u otra solicitud no quedan esperando la inferencia. Se probó con dos
instancias PostgreSQL y `FOR UPDATE NOWAIT` durante la llamada al generador.

Ante un error, una transacción de compensación devuelve **solo la reserva propia**
a `LISTA_PARA_GENERAR` o `BORRADOR`, según sus datos actuales. Si falla también la
base de datos o cae el proceso, la reserva vence tras timeout + 30 segundos. Un
nuevo POST recupera la reserva vencida, valida de nuevo y permite reintentar. No
hay un temporizador de limpieza ni una dependencia de memoria del worker.

El timestamp actúa como control de versión: una respuesta o error de un intento
vencido no puede guardar ni liberar una reserva más reciente. Todos los workers
deben usar el mismo timeout y relojes sincronizados; los timestamps se comparan
como fechas con zona horaria, no como cadenas de texto.

La única incorporación visual es “Reintentar generación” para una solicitud
recuperada en `PROCESANDO`. Usa los datos ya guardados, sin intentar reescribir el
formulario bloqueado. Tras un error se consulta el estado real. No cambia el orden
asunto → contexto confirmado → plantilla/datos → borrador ni las restricciones de roles.

## Errores controlados

| Código | HTTP | Situación |
| --- | --- | --- |
| `OLLAMA_NO_DISPONIBLE` | 503 | Conexión rechazada/no disponible |
| `OLLAMA_MODELO_NO_INSTALADO` | 503 | Ollama responde 404 al modelo solicitado |
| `OLLAMA_TIMEOUT` | 504 | Límite total o timeout de red |
| `OLLAMA_RESPUESTA_INVALIDA` | 502 | JSON/esquema inválido, respuesta incompleta o truncada |
| `OLLAMA_ERROR` | 502 | Otro fallo HTTP/de transporte del servicio |
| `GENERACION_FALLIDA` | 500 | Fallo inesperado del generador inyectado |

La respuesta mantiene `detail` y añade `codigo`. Los mensajes provienen de una
lista controlada: no reflejan cuerpos del proveedor, prompts, direcciones privadas,
credenciales ni datos de la solicitud. Las excepciones inesperadas de un generador
tampoco se propagan al logger global con el prompt incluido.

Se usa un límite total con cancelación asíncrona además de los timeouts de HTTPX.
No se usan proxies ni credenciales del entorno HTTP de forma implícita y no se
siguen redirecciones. Cancelar la petición cierra la conexión del cliente; no se
afirma que detenga inmediatamente todo cómputo interno de Ollama. Un resultado
tardío carece de autorización para sobrescribir la reserva nueva.

## Pruebas y evidencia real

Suite habitual, con mocks para Ollama y PostgreSQL aislado habilitado:

```powershell
$env:NAXJI_PERSISTENCE_MODE='memory'
$env:NAXJI_AUTH_MODE='mock'
$env:NAXJI_RUN_DB_TESTS='0'
$env:NAXJI_RUN_OLLAMA_TESTS='0'
$env:NAXJI_TEST_PG_PORT='55433' # solo clúster aislado, usuario naxji_step3
.venv\Scripts\python.exe -m pytest -q
node --test tests/frontend/*.test.mjs
npm run lint
npm run build
```

Prueba real optativa:

```powershell
$env:NAXJI_RUN_OLLAMA_TESTS='1'
$env:NAXJI_OLLAMA_MODEL='qwen2.5:7b'
.venv\Scripts\python.exe -m pytest -q -s tests/test_ollama_integration.py
```

Sin `NAXJI_TEST_PG_PORT` solo se ejecuta el escenario de memoria. El escenario
PostgreSQL crea una base aislada, usa el SQL y el piloto del paso 3 sin modificarlos,
y elimina exclusivamente esa base de prueba. Las identidades se inyectan solo en
TestClient: no prueba Supabase Auth/RLS ni toca la base de Supabase del usuario.

Resultado final: **144 pruebas Python aprobadas y 12 omitidas** en la suite sin
Ollama real (10 existentes de Supabase/Auth y las 2 optativas de Ollama); **2 pruebas
con Ollama real aprobadas** por separado; **14 pruebas frontend aprobadas**; lint
y build correctos. Persiste la advertencia existente de Starlette/httpx.

También se verificó React DOM con jsdom: regresión de todo el flujo del paso 2,
edición del paso 3, recuperación de `PROCESANDO` y reintento sin reenviar `/completa`.
Esta comprobación del DOM usó respuestas de API simuladas; las comprobaciones
reales de Ollama se hicieron mediante la API FastAPI con TestClient.

Prueba real: solicitud ficticia de inspección de parque sin resultados. Predictor
sklearn real, corrección explícita al tipo técnico, normas descartadas para este
caso, datos guardados, generación, lectura y edición de versión 2:

| Escenario | Modelo | Tiempo de generación completa | Secciones |
| --- | --- | --- | --- |
| API + memoria, piloto DEMO | `qwen2.5:7b` | 3,482 s | Las cinco del piloto |
| API + PostgreSQL aislado, piloto SQL | `qwen2.5:7b` | 3,289 s | Las cinco del piloto |

La primera ejecución en memoria tardó 6,766 s. Son medidas observadas en este
Windows, no un compromiso de rendimiento ni una comparación de bases de datos;
la carga y caché del modelo influyen.

Secciones obtenidas: `antecedentes`, `objetivo`, `analisis_tecnico`, `conclusiones`,
`recomendaciones`. En el piloto SQL, el análisis indicó ausencia de resultados,
mediciones, fotografías y hallazgos; las conclusiones quedaron pendientes de
verificación y no propuso mantenimiento basado en defectos inventados. Se verificó
que el encabezado no cambiase al editar.

La salida sintética y tiempos están en
[`evidencias/ollama-local-20260930.json`](evidencias/ollama-local-20260930.json).
No incluye datos personales reales ni el encabezado con IDs de la fixture.

Límites observados: con los dos campos de la fixture de memoria, el modelo redactó
un objetivo derivado del asunto; con los siete campos del piloto SQL conservó el
objetivo explícito ingresado. La salida fue conservadora y cercana a los datos,
no una evaluación técnica nueva. El esquema valida estructura, no verdad factual;
la prueba semántica solo cubre este caso y requiere revisión humana para otros.
No hay RAG, verificación jurídica ni evaluación de entradas largas o adversariales
exhaustiva. Las salidas truncadas por el límite de tokens se rechazan.

## Archivos principales

- Configuración: `settings.py`, `container.py`, `.env.example` y `README.md`.
- Puertos: `generador_borrador.py` (contexto legible), `llm_port.py` (sistema/esquema).
- Adaptadores: `ollama_adapter.py`, `generador_borrador_ollama.py`.
- Caso de uso: `generar_borrador.py` (reserva, inferencia, finalización y compensación).
- Errores/API: `errores.py`, `main.py`, `error_response.py`, `ia_controller.py`.
- Frontend: `NuevoInforme.jsx`, solo recuperación/reintento de generación.
- Pruebas: `test_ollama.py`, `test_generacion_concurrencia.py`,
  `test_generacion_postgres.py`, `test_ollama_integration.py`, actualización de
  `test_estructura_borrador.py` y fixture `inspeccion_parque_sin_resultados.json`.

Los archivos SQL, el predictor de 200 casos y los cambios previos del formulario
se conservaron. La eliminación local previa de `requirements.txt` no forma parte
de esta implementación.
