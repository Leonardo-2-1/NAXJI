# Paso 3: estructura del borrador por plantilla

Implementado el 30/09/2026 sobre los cambios locales del paso 2. Se conserva el flujo asunto → predicción confirmada → plantilla y datos → borrador, sus comprobaciones de vigencia y las restricciones de roles.

## Contrato y compatibilidad

`CampoPlantilla` define **entradas del funcionario** (tipo de dato, etiqueta, orden y obligatoriedad del formulario). `Plantilla.secciones_salida` define **salidas del documento**. Son contratos independientes; por ejemplo, la entrada `detalle` alimenta la sección `analisis_tecnico` en el generador mock. No se cambiaron los campos existentes ni sus reglas.

La definición es una lista JSON ordenada. Ejemplo de la **demostración técnica NAXJI, sin carácter de formato municipal oficial**:

```json
{
  "secciones_salida": [
    {"clave": "antecedentes", "titulo": "Antecedentes", "obligatoria": true},
    {"clave": "objetivo", "titulo": "Objetivo del informe", "obligatoria": true},
    {"clave": "analisis_tecnico", "titulo": "Análisis técnico", "obligatoria": true},
    {"clave": "conclusiones", "titulo": "Conclusiones", "obligatoria": true},
    {"clave": "recomendaciones", "titulo": "Recomendaciones", "obligatoria": false}
  ],
  "estructura_legacy": false
}
```

- El orden de la lista es el orden del documento; no depende del orden de propiedades de `contenido` JSONB.
- Entre 1 y 100 secciones. `clave` es única, estable y cumple `[a-z][a-z0-9_]{0,79}`; el título no puede estar vacío y admite hasta 150 caracteres; `obligatoria` es booleano.
- Se reservan `encabezado`, `datos`, `contexto`, `plantilla` e `instrucciones` para datos técnicos. No son secciones editables.
- Cada sección presente contiene texto. Las obligatorias exigen texto no vacío; las opcionales pueden omitirse o contener una cadena vacía. `null` no sustituye texto.
- En almacenamiento, **SQL NULL** significa contrato anterior: antecedentes, desarrollo y conclusiones obligatorios. Una lista vacía y JSON `null` son definiciones inválidas.

`GET /plantillas` añade `secciones_salida` efectivas y `estructura_legacy`. `/plantillas/{id}/campos` sigue devolviendo exclusivamente las entradas del formulario. No se creó un endpoint de administración de plantillas; su definición se configura en el repositorio/SQL existente.

`POST /solicitudes/{id}/generar-borrador` conserva su petición `{ "instrucciones": "..." }`. El servidor obtiene la estructura de la plantilla seleccionada, la entrega mediante `Plantilla` al puerto del generador y valida su respuesta. El generador devuelve `{ "clave_de_seccion": "texto" }`, sin encabezado ni claves ajenas. El caso de uso añade el encabezado derivado de la solicitud y del usuario autenticado.

La respuesta de generación, `GET /informes/{id}` y `PUT /informes/{id}` incluyen la estructura **de la versión** y `estructura_legacy`, además de los campos anteriores. `contenido` conserva su formato de objeto. El guardado sigue recibiendo `contenido`, `numero_version` y `titulo`; no permite que el cliente sustituya la estructura.

Cada versión nueva guarda una copia de las secciones utilizadas. La edición usa esa copia, aunque cambie la plantilla después. En versiones anteriores (`secciones_salida IS NULL`), se mantiene la validación histórica y la edición de textos adicionales ya existentes, como `objetivo` y `recomendaciones`. Se conservan los objetos técnicos; si se omiten al guardar, el servidor los recupera de la versión anterior, y rechaza su alteración. No se reescriben versiones antiguas ni se les asigna retroactivamente la estructura actual de la plantilla.

Los errores de contenido obligatorio devuelven HTTP **400**, conforme al manejador de dominio existente; peticiones HTTP mal formadas, 422; conflictos de número de versión, 409.

## Migración y despliegue

Archivos:

1. `database/migrations/20260930_01_secciones_salida.sql`: añade columnas JSONB **nullable** a `plantillas` y `versiones_informe`, función de comprobación y restricciones de estructura.
2. `database/seeds/paso3_estructura_piloto.sql`: configura únicamente `Informe Técnico – Piloto NAXJI`, versión 1, del tipo `INFORME_TECNICO`, y solo si su estructura es NULL. Conserva su nombre, descripción demostrativa y campos. No sobrescribe una estructura previamente configurada.

Ejecutar **antes de iniciar el backend actualizado** contra la base de destino, con la conexión PostgreSQL ya configurada y permisos de migración:

```powershell
psql --set=ON_ERROR_STOP=1 --file=database/migrations/20260930_01_secciones_salida.sql
psql --set=ON_ERROR_STOP=1 --file=database/seeds/paso3_estructura_piloto.sql
```

La base debe tener el esquema existente; el segundo archivo requiere el piloto creado por `database/seeds/pmv1_catalogos.sql`. Si falta, informa el error y revierte su transacción. No ejecutar el archivo histórico de creación del esquema sobre la base existente para aplicar este paso.

Ambos archivos son transaccionales e idempotentes, con bloqueo asesor y `lock_timeout` de 5 segundos. La migración no borra ni recrea tablas o registros, ni modifica el contenido de informes. Si no consigue el bloqueo o encuentra una definición incompatible, falla y revierte; no fuerza cambios destructivos. No se incluye una migración inversa que elimine las columnas: contienen la estructura necesaria para interpretar los nuevos documentos. Para revertir un despliegue, conservarlas y usar código que entienda esas estructuras.

**No se aplicó a Supabase ni a la base de trabajo del usuario.** Se ejecutó en PostgreSQL 18.4 local aislado, con registros de prueba creados antes de migrar. La prueba compara todas las filas y sus timestamps antes/después, repite la migración y el seed, y comprueba persistencia y recuperación mediante los repositorios PostgreSQL reales. La tabla `auth.users` del entorno aislado es una fixture mínima; no verifica Supabase Auth/RLS.

## Generadores y frontend

El mock produce únicamente las secciones solicitadas y marca sus textos como `DEMOSTRACIÓN MOCK`; no inventa hechos ni resultados del predictor. El adaptador Ollama incluye claves, títulos, orden y obligatoriedad en el prompt, valida el JSON recibido y rechaza claves ajenas o secciones obligatorias ausentes. Se probó con un cliente LLM inyectado; no se instaló, configuró ni ejecutó Ollama.

La composición normal conserva el generador Ollama que ya existía. `Container(..., generador=GeneradorBorradorMock())` permite ejecutar pruebas independientes del servicio. No hay una caída silenciosa a datos mock cuando falla Ollama.

El frontend muestra una vista previa de secciones al elegir plantilla. El editor utiliza las secciones de la versión devuelta por la API, en su orden y con sus títulos; no las deduce de los campos de entrada ni de la plantilla actual. El encabezado muestra etiquetas y valores legibles; los otros metadatos se conservan como información de solo lectura. Los documentos anteriores mantienen sus campos de texto adicionales. Antes de guardar se comprueban las secciones obligatorias; el backend repite la validación.

No se añadieron nuevas transiciones al formulario del paso 2. Se conserva la misma solicitud, contexto confirmado, plantilla, valores, control de respuestas tardías y número de versión. Los objetos técnicos permanecen en `contenido` sin pasar por edición/parsing de JSON en un textarea.

La segunda estructura (`resumen_prueba`, `hallazgos_prueba`, `notas_prueba`) existe solo en `tests/fixtures/estructuras_demostrativas.json`. No se instala como formato de otro tipo de documento. Las demás plantillas existentes siguen usando el contrato anterior cuando no tienen definición explícita.

## Archivos de este paso

| Grupo | Archivos añadidos o modificados |
| --- | --- |
| Base de datos | `database/migrations/20260930_01_secciones_salida.sql`, `database/seeds/paso3_estructura_piloto.sql` |
| Dominio | `src/domain/entities/plantilla.py`, `informe.py`; `src/domain/value_objects/seccion_salida.py`, `estructura_piloto.py`; `src/domain/services/informe_service.py` |
| Aplicación | `src/application/ports/output/generador_borrador.py`; `src/application/use_cases/generar_borrador.py`, `actualizar_borrador.py` |
| Persistencia y composición | `src/adapters/out/persistence/postgres.py`, `datos_demo.py`; `src/infrastructure/configuration/container.py` |
| Generadores | `src/adapters/out/ai/generador_borrador_mock.py`, `generador_borrador_ollama.py` |
| API | `src/adapters/in/controllers/catalogo_controller.py`; `src/adapters/in/schemas/catalogo_response.py`, `informe_response.py`, `seccion_response.py` |
| Frontend | `src/adapters/in/web/pages/NuevoInforme.jsx`; `components/EditorBorrador.jsx`; `services/estructuraBorrador.js` |
| Pruebas | `tests/conftest.py`, `test_api.py`, `test_casos_uso.py`, `test_estructura_borrador.py`, `test_estructura_postgres.py`; `tests/fixtures/estructuras_demostrativas.json`; `tests/frontend/estructuraBorrador.test.mjs` |
| Documentación | `docs/paso3-estructura-borradores.md` |

Los repositorios memory ya hacen copias profundas al guardar y recuperar; conservan la nueva estructura sin cambiar su mecanismo. Sus pruebas verifican que no se pueda modificar el estado almacenado mutando una copia recuperada. Los archivos locales del paso 2 (`flujoInforme.js`, sus pruebas y cambios en los servicios) se conservaron. La eliminación previa de `requirements.txt` y los archivos ajenos a este paso no se modificaron.

## Comprobaciones ejecutadas

```powershell
$env:NAXJI_PERSISTENCE_MODE='memory'
$env:NAXJI_AUTH_MODE='mock'
$env:NAXJI_RUN_DB_TESTS='0'
# Solo para un clúster local aislado de pruebas, usuario naxji_step3:
$env:NAXJI_TEST_PG_PORT='55433'
.venv\Scripts\python.exe -m pytest -q
node --test tests/frontend/*.test.mjs
npm run lint
npm run build
git diff --check
```

Resultados: **97 pruebas Python aprobadas, 10 omitidas**, **14 pruebas frontend aprobadas**, lint y build correctos, sin errores de whitespace. Las omitidas son pruebas existentes opt-in de Supabase/servicios externos; no se habilitaron. Una advertencia existente de Starlette indica deprecación de su integración con `httpx`; no impide las pruebas.

Sin `NAXJI_TEST_PG_PORT`, las dos pruebas PostgreSQL de este paso también se omiten. Para reproducirlas se necesita un clúster local aislado accesible en loopback con usuario `naxji_step3` y permiso `CREATEDB`. Cada prueba crea una base con nombre UUID, ejecuta fixtures y la elimina al terminar; no acepta como destino una base existente de la aplicación ni lee las credenciales del `.env`.

Además se ejecutaron dos comprobaciones funcionales con React DOM/jsdom:

- Regresión del paso 2 con API simulada: asunto solo, aceptación/corrección de normas, recuperación, incompatibilidad de plantilla, ausencia de plantilla, invalidación por cambio de asunto y descarte de respuesta tardía, generación/edición y recuperación por ID.
- React contra **HTTP FastAPI real** en memoria, con predictor y generador mock explícitos: asunto → corrección al tipo técnico → selección de piloto → datos guardados y recuperados → generación de cinco secciones ordenadas → encabezado de solo lectura → bloqueo de sección obligatoria vacía → edición y recuperación de versión 2, conservando encabezado y estructura.

Estas comprobaciones no verifican diseño visual en un navegador real, Supabase Auth/RLS ni calidad de generación de un modelo Ollama real. Las pruebas unitarias del adaptador verifican el prompt y el rechazo de respuestas inválidas sin necesitar ese servicio.
