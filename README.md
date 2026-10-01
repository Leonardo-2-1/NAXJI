# NAXJI — Copilot Municipal: backend PMV1

API FastAPI con arquitectura hexagonal, React, PostgreSQL y Supabase Auth.
Permite crear una solicitud, confirmar/corregir contexto, completar una plantilla,
generar un borrador y guardar ediciones como versiones. El predictor ejecuta RF-IA-01
con correspondencias de catálogo; el generador de borradores usa **Ollama local**
con `qwen2.5:7b` y las secciones de la plantilla seleccionada.
La plantilla técnica piloto es demostrativa, no un formato municipal aprobado.

Estado y evidencias: [catálogos PMV1](docs/IMPLEMENTACION_CATALOGOS_PMV1.md) y
[autenticación/persistencia](docs/VERIFICACION_SUPABASE.md).

## Ejecutar en Windows / PowerShell

Requiere Python 3.11 o superior. Desde la raíz del repositorio:

```powershell
# Solo si el entorno todavía no existe:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-export.txt
$env:NAXJI_PERSISTENCE_MODE = 'postgres'
$env:NAXJI_AUTH_MODE = 'supabase'
$env:NAXJI_AUTH_COOKIE_SECURE = 'false' # Solo desarrollo HTTP local
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

- Salud: http://127.0.0.1:8000/health
- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json

Configure las variables privadas según `.env.example` en su `.env` local excluido
de Git. No sobrescriba un `.env` existente. PostgreSQL conserva datos al reiniciar.
En otra terminal: `npm.cmd ci` y `npm.cmd run dev -- --host 127.0.0.1 --port 5173`.
Abra http://127.0.0.1:5173 e inicie sesión con su cuenta Supabase existente.

## Generación con Ollama local

Con Ollama encendido y `qwen2.5:7b` instalado, agregue estas variables al entorno
del backend o a `.env.local` (conserve las demás variables existentes):

```dotenv
NAXJI_OLLAMA_BASE_URL=http://localhost:11434
NAXJI_OLLAMA_MODEL=qwen2.5:7b
NAXJI_OLLAMA_TIMEOUT_SECONDS=300
```

Son los valores por defecto. Reinicie el backend tras modificarlos. No use prefijo
`VITE_`: el frontend solo habla con FastAPI. La URL no admite credenciales ni query;
el tiempo máximo debe estar entre 1 y 1800 segundos e incluye cargar el modelo.
Para comprobar disponibilidad en PowerShell:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
# Solo si falta el modelo:
ollama pull qwen2.5:7b
```

El backend envía `POST /api/generate`, `stream: false`, temperatura 0 y un esquema
JSON de las secciones. También valida la respuesta y guarda el nombre configurado
en `modelo_ia`. Los encabezados los construye el servidor. No hay sustitución
automática por mock cuando falla el servicio.

Los datos ingresados sirven para redactar, no para modificar las reglas del modelo.
Sin resultados de inspección, análisis y conclusiones deben quedar pendientes de
verificación. Las normas aceptadas se transmiten por código y título de catálogo;
no son citas jurídicas verificadas y no se recupera su texto. Aún no hay RAG.
El borrador requiere revisión humana: un esquema válido no demuestra veracidad.

Las migraciones del [paso 3](docs/paso3-estructura-borradores.md) deben estar ya
aplicadas. Para el piloto v2 y la exportación, revise también el SQL pendiente indicado abajo. Detalles de concurrencia,
errores y prueba real: [integración Ollama](docs/INTEGRACION_OLLAMA_LOCAL.md).

Carga inicial, con vista previa y verificación de idempotencia:

```powershell
.\.venv\Scripts\python.exe scripts/cargar_catalogos.py
# Después de revisar las inserciones:
.\.venv\Scripts\python.exe scripts/cargar_catalogos.py --apply
```

La carga ya fue aplicada en este proyecto; repetirla no duplica registros.
Guarde el enlace `/nuevo-informe?solicitud=UUID` para recuperar el formulario.

## Piloto v2 con datos fuente y descarga Word

El flujo visual es asunto → confirmación → elaboración → vista previa y descarga.
En elaboración se elige plantilla, se aportan datos fuente, se genera con Ollama,
se revisan las secciones propuestas y se guarda la edición. El paso 4 solo se
habilita con una versión guardada. Si hay cambios sin guardar, se avisa y la vista
previa/descarga mantiene el contenido guardado. Se pueden consultar y descargar
versiones anteriores sin volver a llamar a Ollama.

La nueva **Informe Técnico – Piloto NAXJI · v2** pide únicamente la selección
«Información disponible». Hechos, referencias, lugar, fecha e información pendiente
son opcionales. «Sin resultados de inspección» permite generar sin redactar antes
antecedentes, objetivo, análisis, conclusiones ni recomendaciones. Esas son las
cinco secciones de salida. Sin hechos aportados, el esquema de Ollama y la validación
del backend exigen marcar las secciones fácticas como `Pendiente de verificación:`.
Esto no comprueba la veracidad de cada oración: la revisión humana sigue siendo necesaria.
Un enlace o referencia no significa que su contenido se haya recuperado o verificado.

**SQL pendiente de revisión; no aplicado automáticamente a Supabase:**

1. [20261001_02_titulo_version.sql](database/migrations/20261001_02_titulo_version.sql)
   añade `versiones_informe.titulo`, nullable. Aplique esta migración antes de usar
   el backend actualizado para generar o editar con PostgreSQL. Los títulos nuevos
   quedan guardados por versión. En versiones antiguas, `NULL` se conserva y se
   muestra un aviso de que el título usado es el actual del informe.
2. [20261001_piloto_v2_datos_fuente.sql](database/seeds/20261001_piloto_v2_datos_fuente.sql)
   inserta la plantilla v2 y sus seis campos. Requiere el piloto v1 y la migración
   de secciones del paso 3. No modifica ni retira v1, sus campos o datos anteriores.
   Una definición v2 conflictiva provoca rollback; se debe revisar, no sobrescribir.

Ambos archivos son transaccionales e idempotentes. No hay migraciones al arrancar
la aplicación. El modo memoria dispone de v1 y v2 como fixtures separados; en
otras bases v2 no aparecerá hasta que se revise y aplique su SQL. En el catálogo
Supabase de esta copia se verificaron v1 y v2 mediante GET autenticados el
2026-10-01; no es necesario volver a sembrarlas para añadir la inspección.

Instale `requirements-export.txt` en el entorno backend. La descarga DOCX usa
`python-docx` en memoria y requiere los permisos de consulta del informe; no
acepta contenido enviado por el cliente y responde `Cache-Control: no-store`.
El formato Word es **piloto, no institucional aprobado**: A4, encabezado guardado,
títulos y secciones en el orden de la versión. No modifica el informe ni consulta
la plantilla actual para reorganizarlo. La vista HTML muestra el contenido y el
orden; la paginación depende de Word.

Pruebas aisladas (clúster exclusivo en loopback, usuario `naxji_step3`):

```powershell
$env:NAXJI_TEST_PG_PORT='55433'
.\.venv\Scripts\python.exe -m pytest -q
npm run test:frontend
npm run lint
npm run build
# Opt-in: generación real, datos ficticios y base temporal aislada; nunca Supabase.
$env:NAXJI_RUN_OLLAMA_TESTS='1'
$env:NAXJI_PILOTO_EVIDENCE_DIR='D:/NAXJI/docs/evidencias/piloto-v2'
.\.venv\Scripts\python.exe -m pytest -q -s tests/test_piloto_v2_ollama.py
```

Las pruebas PostgreSQL crean bases con nombres aleatorios y las eliminan al finalizar;
no aceptan una base existente como destino ni leen credenciales del `.env`.
Sin las variables opt-in se omiten las pruebas externas. Evidencia del caso real:
[piloto-v2-ollama.json](docs/evidencias/piloto-v2/piloto-v2-ollama.json).

## Inspección ambiental piloto para Gestión Ambiental

La ausencia de plantilla al confirmar **Informe de Inspección** no era un fallo
del filtro: las técnicas v1/v2 pertenecen a `INFORME_TECNICO`. El frontend y el
backend requieren el mismo tipo y, si `area_id` no es nulo, el mismo destino.
No se cambia ese criterio ni se reutiliza una plantilla de otro tipo.

Identificación del catálogo real, consultado solo mediante endpoints GET con
Supabase Auth y el backend PostgreSQL local:

| Selección | Código del catálogo | UUID real |
|---|---|---|
| Informe de Inspección | `INFORME_INSPECCION` | `668a217a-8f4f-47d6-99d8-0a7ab8661ea6` |
| Subgerencia de Gestión Ambiental | `MDT_SGGA` | `1973fec4-ba92-42e5-9de5-994dcd0c674b` |

El predictor utiliza la etiqueta de área `AREA_ECOLOGIA`; `ContextPredictorCatalogo`
la resuelve a `MDT_SGGA`. No se modifican las clases, archivos o parámetros sklearn.
La [evidencia del catálogo](docs/evidencias/inspeccion-piloto/catalogo-actual.json)
incluye las dos plantillas técnicas existentes y sus campos, sin credenciales.
`scripts/consultar_compatibilidad_plantillas.py` permite repetir la consulta al
backend local usando una cuenta autorizada; pide la contraseña sin mostrarla,
no guarda tokens y cierra la sesión utilizada. No envía SQL a Supabase.

La nueva **Informe de Inspección – Piloto NAXJI · v1** es una familia independiente.
Su descripción y el Word indican que **no es un formato municipal oficial**.
Está restringida a `INFORME_INSPECCION` + `MDT_SGGA`.

Datos fuente, en orden: información disponible sobre resultados (único obligatorio,
con la opción «Sin resultados de inspección»), lugar, fecha documentada de la visita,
aspectos que se solicita verificar, observaciones/resultados documentados,
actas/documentos/referencias disponibles e información/evidencias pendientes.
No se exige redactar ninguna sección del informe en estos campos.

| Orden | Clave estable de salida | Título | Obligatoria |
|---|---|---|---|
| 1 | `antecedentes` | Antecedentes de la solicitud | Sí |
| 2 | `objetivo` | Objetivo y alcance de la inspección | Sí |
| 3 | `actuaciones` | Actuaciones y fuentes disponibles | Sí |
| 4 | `hallazgos` | Hallazgos y observaciones | Sí |
| 5 | `conclusiones` | Conclusiones | Sí |
| 6 | `recomendaciones` | Recomendaciones y verificaciones pendientes | No |

El JSON exacto de `secciones_salida` está en el SQL. Su lista ordenada se guarda
con cada versión y gobierna editor, vista previa y DOCX; el orden de las claves
de un objeto JSONB no es el orden de presentación. Las secciones opcionales
pueden omitirse en la respuesta del modelo y se presentan vacías, sin inventar texto.

El campo de resultados declara `rol_fuente: "hechos"`. El selector declara
`valores_sin_resultados: ["Sin resultados de inspección"]`: esa elección prevalece
aunque se escriban notas. Sin hechos, Ollama recibe un esquema que exige
`Pendiente de verificación:` en las secciones fácticas y el backend lo valida.
Las instrucciones distinguen datos no aportados de actividades no realizadas;
las conclusiones y recomendaciones las propone Ollama a partir de la evidencia,
no se solicitan previamente al funcionario. Un prefijo no prueba la verdad de
una oración: se mantiene la revisión humana y no hay RAG ni verificación jurídica.

**Estado verificado de esta base y semilla corregida:**

El 2026-10-01 se comparó la definición completa de Supabase en una transacción
`REPEATABLE READ / READ ONLY`: **cero diferencias** con la definición del SQL,
incluidos tipo/área, descripción, campos activos e inactivos, etiquetas, tipos de
dato, orden, obligatoriedad, configuración y secciones. La plantilla guardada es
`c3e99fe3-1907-426a-a690-cd92ce0ada6d`. También están las columnas de título y
estructura por versión. **Está íntegra: no vuelva a insertar ni a aplicar la semilla
en esta base. Ya puede probar el flujo desde Inspección/Gestión Ambiental.**
La [comparación íntegra](docs/evidencias/inspeccion-piloto/comparacion-supabase.json)
contiene los valores esperados, guardados y el hash del SQL comparado.

La semilla anterior usaba tablas temporales `ON COMMIT DROP`; ejecutar por separado
su creación y consumo puede producir `42P01` porque desaparecen al cerrar la
transacción. Se reprodujo ese caso en PostgreSQL aislado, sin atribuir al SQL Editor
un orden de ejecución que no quedó registrado. La semilla corregida es **una sola
sentencia `DO`**, con definición JSON y variables locales, sin tablas temporales ni
objetos entre sesiones. Se probó en autocommit, transacción externa, rollback y
conexiones distintas. No cambia la definición de la plantilla respecto del SQL anterior.

Para revisar el SQL o utilizarlo en **otra base que requiera instalar la plantilla**:

1. Revise [20261001_piloto_inspeccion_ambiental.sql](database/seeds/20261001_piloto_inspeccion_ambiental.sql).
   Es una semilla, no modifica el esquema. Resuelve los UUID por códigos activos;
   requiere las columnas `plantillas.secciones_salida` y `versiones_informe.titulo`
   del código actual. Si falta un prerrequisito, aborta sin insertar registros.
2. En una base que requiera instalarla, ejecute **el bloque DO completo**, después
   de revisarlo. Inserta una plantilla y siete campos de forma atómica si no existe;
   si ya está completa e idéntica, termina sin escribir ni cambiar UUID o timestamps.
   No actualiza ni elimina la técnica v1/v2, solicitudes, informes o versiones.
   Si la definición existente difiere o está incompleta, aborta sin sobrescribir,
   reactivar ni completar registros. No depende de ejecutar previamente otros
   fragmentos. La base actual del usuario no requiere esta ejecución.
3. Ejecute manualmente el [SQL de comprobación, solo lectura](database/checks/20261001_verificar_piloto_inspeccion.sql).
   Debe mostrar las técnicas v1/v2 intactas y la inspección v1 con **7 campos / 6
   secciones**, tipo `INFORME_INSPECCION`, área `MDT_SGGA` y título por versión
   disponible. Para ese destino las compatibilidades esperadas son Técnico: 2,
   Inspección: 1, Legal: 0, Memorando: 0, según el catálogo consultado.
4. Reinicie el backend con estos cambios y su configuración PostgreSQL/Supabase/Ollama
   habitual. Recargue el frontend que apunta a ese backend (no el acceso demo en memoria).
   Abra `/nuevo-informe?solicitud=UUID` o cree una prueba ficticia. Confirme Inspección
   y Gestión Ambiental; en el paso 3 elija la nueva plantilla. Indique que no hay
   resultados, genere, revise y guarde una edición como versión 2. En el paso 4,
   recupere esa versión y descargue Word. La descarga no invoca Ollama ni modifica
   el documento guardado. No hace falta cambiar a Informe Técnico ni reentrenar.

Cobertura pendiente: el modelo cargado tiene **tres tipos** (Técnico, Legal e
Inspección). Legal carece de plantilla; Inspección en otros destinos seguirá sin
una compatible. Memorando tampoco tiene plantilla, pero no es una clase del
modelo actualmente cargado. Hay además una etiqueta de área de riesgo de desastres
sin correspondencia en este catálogo; este cambio no la corrige ni crea áreas.

Pruebas reproducibles, solo sobre el clúster PostgreSQL **aislado**, en loopback
y usuario `naxji_step3` descrito arriba:

```powershell
$env:NAXJI_TEST_PG_PORT='55433'
$env:NAXJI_RUN_DB_TESTS='0' # No habilitar pruebas contra Supabase.
$env:NAXJI_RUN_OLLAMA_TESTS='0'
.\.venv\Scripts\python.exe -m pytest -q tests/test_inspeccion_piloto.py
npm run test:frontend
npm run lint
npm run build
# Optativo, con qwen2.5:7b local encendido:
$env:NAXJI_RUN_OLLAMA_TESTS='1'
$env:NAXJI_INSPECCION_EVIDENCE_DIR='D:/NAXJI/docs/evidencias/inspeccion-piloto'
.\.venv\Scripts\python.exe -m pytest -q -s tests/test_inspeccion_piloto.py -k ollama_real
```

La prueba aplica la semilla en una base nueva desechable, compara **todas** las filas
previas, prueba repetición/conflictos/prerrequisitos y preserva la técnica v1/v2
y el informe anterior. Comprueba el filtro React con el catálogo devuelto por
PostgreSQL; usa sklearn real, confirmación humana simulada, descarte de normas,
generación, error 502 recuperable, edición, recuperación mediante otra instancia,
DOCX guardado y permisos. La prueba DOM utiliza los siete campos y seis secciones
de un fixture contrastado con ese mismo SQL, incluyendo reintentos y respuestas tardías.

Evidencia de Ollama: [ollama-real.json](docs/evidencias/inspeccion-piloto/ollama-real.json).
La clasificación del asunto ficticio fue Legal/Asesoría Jurídica y se corrigió
explícitamente a Inspección/Gestión Ambiental; no se fingió una predicción distinta.
Una primera revisión detectó la afirmación no sustentada «no se han realizado
inspecciones». Se ajustaron las instrucciones y descripciones del esquema y se
repitió el caso; el resultado final distingue ausencia de datos de ausencia de
actividad. Los intentos anteriores se conservan como evidencia de esa limitación.
El DOCX corregido se abrió con Word en modo solo lectura y se inspeccionó visualmente.
Resultados del 2026-10-01: suite Python **189 aprobadas / 15 omitidas** (pruebas
externas optativas); integración real adicional **1 aprobada**, `qwen2.5:7b`,
**4,409 s**, seis secciones. Generación HTTP 201; edición, recuperación y DOCX
HTTP 200. Frontend **41 aprobadas**, `npm run lint` y `npm run build` correctos.
Estas pruebas no ejecutan el flujo de escritura en Supabase ni verifican sus RLS;
Auth real solo se usó para leer el catálogo. La prueba de pantalla usa React/JSDOM,
no un navegador interactivo conectado a Supabase.

La auditoría posterior al error `42P01` usa
`scripts/verificar_inspeccion_guardada.py`, que extrae solo el literal JSON del SQL
y ejecuta únicamente SELECT con la configuración privada del backend. **Nunca
ejecuta la semilla** en la base auditada. Para repetir solo esa lectura:

```powershell
.\.venv\Scripts\python.exe scripts/verificar_inspeccion_guardada.py
```

La corrección y la auditoría tienen **35 pruebas aprobadas / 1 omitida** en
`tests/test_inspeccion_semilla.py` y `tests/test_inspeccion_piloto.py`, con el
PostgreSQL aislado: inserción inicial, repetición en conexiones distintas,
rollback externo, fallo durante inserción y rechazo de 18 definiciones alteradas
o parciales. Se verifican igualdad completa y ausencia de escrituras al auditar.
La prueba omitida es Ollama real, optativa; no se generaron informes ni se modificó
ningún registro de Supabase durante esta auditoría.

## Modo de pruebas en memoria (opcional)

Solo para pruebas: `NAXJI_PERSISTENCE_MODE=memory` y `NAXJI_AUTH_MODE=mock`.
En ese modo los datos sí se pierden al reiniciar y cada proceso tiene su memoria.
La generación también usa Ollama en modo memoria. Las pruebas automáticas inyectan
`GeneradorBorradorMock` explícitamente; el modo de autenticación no elige el generador.

En Swagger pulse **Authorize** e introduzca `demo-funcionario` (sin escribir `Bearer`).
En Postman use `Authorization: Bearer demo-funcionario`.

| Token ficticio | Comportamiento de prueba |
|---|---|
| `demo-funcionario` | Crear, consultar y editar sus propias solicitudes e informes |
| `demo-otro` | Otro propietario; no puede acceder a los recursos del primero |
| `demo-revisor` | Identidad del primer usuario con rol de lectura; no puede elaborar |
| `demo-aprobador` | Identidad del primer usuario con rol de lectura; no puede elaborar |
| `demo-admin` | Elaborar y acceder a todos los recursos de la demo |

Estos valores son selectores de identidades ficticias, **no credenciales ni sesiones reales**.
Estos tokens solo funcionan en modo de pruebas. PostgreSQL usa Supabase Auth,
con sesión real, perfil y roles consultados en el backend. No cree cuentas duplicadas.

Configuración opcional antes de iniciar el servidor:

```powershell
$env:NAXJI_AUTH_MODE = "mock"
$env:NAXJI_CORS_ORIGINS = "http://localhost:5173"
```

`NAXJI_AUTH_MODE=disabled` rechaza todos los tokens en rutas protegidas;
`/health`, `/docs` y `/openapi.json` permanecen públicos. La política de autorización
de la demo está en `autorizar`; debe acordarse con el equipo antes de producción.
CORS queda cerrado salvo los orígenes configurados.

## Flujo de borradores en Swagger / Postman

1. Consulte `GET /tipos-informe` y `GET /areas`. Los cuatro códigos de tipo provienen
   de PostgreSQL en modo real; los fixtures ficticios solo corresponden al modo memoria.
2. Cree `POST /solicitudes` con `{"asunto":"Inspección de un parque"}`.
   Guarde el `id` devuelto. Puede incluir tipo, áreas y plantilla desde este paso.
3. Consulte y edite mediante `GET /solicitudes/{id}` y `PUT /solicitudes/{id}`.
   El PUT actualiza solo los campos enviados; las referencias admiten `null`.
4. Ejecute `POST /solicitudes/{id}/predecir-contexto`, sin cuerpo.
   La respuesta identifica el predictor configurado y sus advertencias. Sus confianzas
   no acreditan precisión institucional validada.
5. Confirme con `POST /solicitudes/{id}/validar-prediccion`:

   ```json
   {"prediccion_id":"UUID_DEVUELTO", "resultado":"ACEPTADA"}
   ```

   Para corregir, envíe `resultado: "CORREGIDA"`, `tipo_informe_id`,
   `area_destino_id` y opcionalmente `normativa_ids` con las normativas predichas
   que conserva. `[]` descarta todas. `RECHAZADA` impide generar.
   Solo se valida la predicción más reciente. La respuesta conserva la propuesta
   original; `GET /solicitudes/{id}` muestra el tipo/área finalmente confirmados.
6. Consulte `GET /plantillas?tipo_informe_id=UUID_CONFIRMADO`.
   Seleccione una con `PUT /solicitudes/{id}` y `{"plantilla_id":"UUID_PLANTILLA"}`.
   Si la confirmación cambia tipo/destino y vuelve incompatible la plantilla,
   la API despeja esa plantilla y sus valores; seleccione nuevamente el formato.
7. Consulte `GET /plantillas/{plantilla_id}/campos` y complete sus datos fuente
   obligatorios. Este ejemplo mínimo corresponde al piloto **v2**; la v1 conserva
   sus campos anteriores y no se convierte automáticamente:

   ```json
   {
     "valores": [
       {"campo_plantilla_id":"UUID_ESTADO_RESULTADOS", "valor":"Sin resultados de inspección"}
     ]
   }
   ```

   Use `PUT /solicitudes/{id}/valores`. **Reemplaza todo el conjunto de valores**;
   incluya también los que desea conservar. Puede guardar formularios incompletos,
   pero no generar con ellos. Los tipos admitidos son text, textarea, date
   (`YYYY-MM-DD`), number, boolean y select. Los campos select de la demo usan
   `configuracion.opciones`; el backend valida que la opción pertenezca a la plantilla.
8. Ejecute `POST /solicitudes/{id}/generar-borrador` con
   `{"instrucciones":"Respetar los datos de la inspección."}` o `{}`.
   Recibirá `informe_id`, `estado: BORRADOR`, `numero_version: 1` y `contenido`.
   Ollama devuelve texto según `secciones_salida`. El piloto es demostrativo y no
   acredita un formato oficial ni la veracidad de hechos no aportados.
9. Recupere `GET /informes/{informe_id}` y edite con `PUT /informes/{informe_id}`:

   ```json
   {
     "numero_version": 1,
     "contenido": {
       "antecedentes": "Solicitud de inspección recibida.",
       "objetivo": "Objetivo revisado por el funcionario.",
       "analisis_tecnico": "Pendiente de contar con resultados verificados.",
       "conclusiones": "Conclusiones editadas."
     }
   }
   ```

   Se agrega la versión 2, con origen `USUARIO`; la versión anterior se conserva.
   Envíe la versión que leyó. Una versión antigua produce 409. Este ejemplo corresponde
   al piloto técnico; otras plantillas usan sus propias secciones. Las versiones
   anteriores conservan la estructura con la que fueron guardadas.
10. Recupere por solicitud con `GET /solicitudes/{id}/informe`. Consulte una versión
    con `GET /informes/{id}/versiones/{numero}` y descargue su DOCX mediante
    `GET /informes/{id}/versiones/{numero}/docx`, con la misma autenticación.

Los IDs ilustrativos `UUID_...` deben reemplazarse por UUID reales devueltos por la API.
El flujo anterior también se verifica automáticamente en `tests/test_api.py`.

## Endpoints

| Método | Ruta | Uso |
|---|---|---|
| GET | `/health` | Estado, sin autenticación |
| GET | `/auth/me` | Identidad y roles verificados según modo configurado |
| POST | `/solicitudes` | Crear; devuelve 201 |
| POST | `/solicitudes/completa` | Crear formulario completo y valores en una transacción |
| PUT | `/solicitudes/{solicitud_id}/completa` | Guardado completo; rollback si faltan obligatorios |
| GET | `/solicitudes/{solicitud_id}/contexto` | Recuperar última predicción; control de propietario |
| GET | `/solicitudes/{solicitud_id}` | Consultar |
| PUT | `/solicitudes/{solicitud_id}` | Modificar campos o cancelar |
| PUT | `/solicitudes/{solicitud_id}/valores` | Guardar valores de plantilla |
| GET | `/tipos-informe` | Catálogo de tipos |
| GET | `/areas` | Catálogo de áreas |
| GET | `/plantillas` | Plantillas activas; filtro opcional por tipo |
| GET | `/plantillas/{plantilla_id}/campos` | Campos activos ordenados |
| POST | `/solicitudes/{solicitud_id}/predecir-contexto` | Sugerencia desde asunto; requiere confirmación |
| POST | `/solicitudes/{solicitud_id}/validar-prediccion` | Confirmar/corregir/rechazar |
| POST | `/solicitudes/{solicitud_id}/generar-borrador` | Generar con Ollama; devuelve 201 |
| GET | `/informes/{informe_id}` | Consultar la última versión |
| GET | `/solicitudes/{solicitud_id}/informe` | Recuperar la última versión desde el UUID de solicitud |
| GET | `/informes/{informe_id}/versiones/{numero_version}` | Consultar una versión guardada |
| GET | `/informes/{informe_id}/versiones/{numero_version}/docx` | Descargar Word piloto sin regenerar |
| PUT | `/informes/{informe_id}` | Guardar una nueva versión |

Se conserva `POST /solicitudes/` como alias. El cuerpo anterior `descripcion`
se sustituye por valores de plantilla, porque no existe esa columna en `solicitudes`.
Los IDs enteros anteriores se sustituyen por UUID.

Estados de solicitud: `BORRADOR → LISTA_PARA_GENERAR → PROCESANDO → GENERADA`.
Los dos primeros admiten cancelación a `CANCELADA`. La API deriva los estados;
solo acepta `CANCELADA` como cambio manual. Modificar asunto/tipo/destino invalida
la confirmación; cambiar plantilla elimina valores de la plantilla anterior.
Cambiar el asunto exige una nueva predicción. Cada solicitud puede generar un único informe.
`PROCESANDO` es una reserva persistida en una transacción corta. La llamada a Ollama
ocurre sin transacciones ni bloqueos PostgreSQL abiertos. Un fallo devuelve la solicitud
a un estado editable. Tras una caída del proceso, el mismo POST permite reintentar
cuando pasan el tiempo máximo configurado + 30 segundos desde la reserva. El frontend
muestra “Reintentar generación” al recuperar una solicitud en `PROCESANDO`.
Una respuesta tardía no puede sobrescribir un intento nuevo. Todos los workers deben
compartir la misma configuración de timeout y tener sus relojes sincronizados.
PMV1 solo edita informes en `BORRADOR`; los demás estados del SQL están definidos,
pero sus flujos de revisión/aprobación quedan fuera de este alcance.

Errores: 400 reglas/datos de negocio, 401 sin autenticación, 403 permiso/propietario,
404 recurso inexistente, 409 estado/versión incompatible, 422 request inválido y
500 fallo interno, 502 salida inválida/fallo de Ollama, 503 conexión o modelo no
disponible y 504 tiempo agotado. Los errores de generación incluyen un `codigo`
estable y un mensaje de una lista controlada, sin prompts ni detalles del proveedor.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m pip check
```

Se cubren casos de uso, validaciones, contratos mock, control por rol/propietario,
concurrencia de generación, rollback, versiones, endpoints, Swagger, CORS e imports.
`httpx` se utiliza en TestClient. Para incluir pruebas reales PostgreSQL:
`$env:NAXJI_RUN_DB_TESTS='1'` antes de pytest. Las pruebas Auth con contraseñas en
archivo son opcionales; la alternativa manual es
`node scripts/verificar_catalogos_navegador.cjs` (requiere Playwright en `venv/ui-check`).
Con las versiones instaladas, Starlette emite un aviso de deprecación de su uso de
httpx en TestClient; las pruebas pasan. No se añadió otro cliente HTTP por ese aviso.

Pruebas de frontend: `node --test tests/frontend/*.test.mjs`, `npm run lint` y
`npm run build`. La suite habitual simula la API de Ollama mediante `httpx.MockTransport`.
Para una prueba completa **optativa** con datos ficticios, predictor sklearn y Ollama reales:

```powershell
$env:NAXJI_PERSISTENCE_MODE='memory'
$env:NAXJI_AUTH_MODE='mock'
$env:NAXJI_RUN_OLLAMA_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q -s tests/test_ollama_integration.py
Remove-Item Env:NAXJI_RUN_OLLAMA_TESTS
```

El escenario PostgreSQL se activa adicionalmente con `NAXJI_TEST_PG_PORT` apuntando
al clúster **aislado de pruebas** descrito en la documentación del paso 3; crea y
elimina solo bases con nombres aleatorios de prueba. No utiliza el Supabase del usuario.

## Integración pendiente y contratos

La correspondencia entre **temas del predictor** y **documentos normativos** es
explícita y admite varias referencias por tema. Véase el
[inventario y verificación de fuentes](docs/CORRESPONDENCIAS_NORMATIVAS.md), que
incluye el contrato JSON, los límites de vigencia y el SQL propuesto para revisión.
La migración y la semilla se probaron solo en PostgreSQL aislado; no se aplicaron
a Supabase. Hasta su aplicación, las nuevas predicciones muestran los temas y
advierten que no hay documentos verificables asociados. El modelo de 200 casos
no cambia, y la confianza temática no acredita aplicabilidad jurídica.

Consulte [docs/CONTRATOS_PMV1.md](docs/CONTRATOS_PMV1.md) y el
[inventario de entrega](docs/ENTREGA_PMV1.md).

- React, repositorios PostgreSQL, unidad de trabajo y Supabase Auth están integrados.
- RF-IA-01: pendientes validación experimental institucional, categorías sin correspondencia
  y curación jurídica de etiquetas normativas. No se reentrenó el modelo.
- LLM: integración local implementada con plantilla, datos, contexto legible e instrucciones;
  pendientes evaluación amplia de fidelidad y recuperación jurídica verificada (RAG).

`Container` configura `OllamaAdapter` al iniciar, sin conectarse hasta generar.
El puerto `LLMPort` recibe prompt de datos, instrucciones de sistema y esquema JSON.
El mock sigue siendo inyectable para pruebas, sin cambiar el comportamiento de producción.

## Interfaz web PMV 1

La interfaz React queda como adaptador de entrada en `src/adapters/in/web/` (páginas, componentes, layouts y servicios). No modifica controladores ni casos de uso del backend.

Con el backend encendido en `http://127.0.0.1:8000`:

```powershell
npm install
npm run dev
```

## Inspección: contenido y Word piloto (revisión local, octubre de 2026)

El caso revisado se trata como **informe interno de inspección, PILOTO**. Una
petición sobre un parque no acredita una supervisión ambiental formal, visita,
hallazgo o infracción. Para ese procedimiento deben confirmarse competencia,
administrado o unidad fiscalizable, obligaciones y actuaciones sustentadas.
El asunto de la prueba menciona el **distrito de Huancayo**: no se puede deducir
competencia territorial de El Tambo a partir del área destinataria seleccionada.

Fuentes primarias revisadas:

- [Kit de supervisión ambiental de OEFA](https://www.gob.pe/institucion/oefa/informes-publicaciones/8442725-supervision-ambiental)
  y su [Formato de Informe de Supervisión DOCX](https://cdn.www.gob.pe/uploads/document/file/10401081/8442725-formato-de-informe-de-supervision.docx?v=1785878687).
  Es un formato para supervisión formal: distingue cabecera administrativa,
  datos de supervisión, antecedentes, sustento, análisis de hechos, conclusiones
  y recomendaciones. Incluye elementos de fiscalización que esta aplicación no
  acredita. No se trasladan códigos de EFA, expediente supuesto, firmas,
  infracciones, medidas administrativas ni competencias del documento de OEFA.
- [Documentos de gestión de El Tambo](https://munieltambo.gob.pe/documentos-gestion03/)
  y [ROF 2020 publicado, páginas 62–63, artículos 121–122](https://cdn.www.gob.pe/uploads/document/file/4258543/MDT_ROF_2020.pdf.pdf?v=1678902895).
  El ROF describe funciones de Gestión Ambiental relativas a ambiente, residuos
  y parques. No prueba la competencia sobre este caso ni la vigencia consolidada
  a la fecha. El índice menciona formatos de comunicación y un reglamento de
  supervisión; no se pudo verificar un DOCX institucional aprobado mediante
  los enlaces expuestos de esa página. No se afirma que no exista.

**Procedencia del diseño.** De OEFA se toma como referencia conceptual separar
datos administrativos del cuerpo y relacionar hechos, fuentes y conclusiones.
Son decisiones locales NAXJI las seis secciones ya guardadas de la plantilla de
inspección, los marcadores `[POR COMPLETAR]`, la revisión por versiones, Arial en
A4, los márgenes, la numeración de páginas y la unión del cierre breve para evitar
recomendaciones aisladas. El resultado no es un formato oficial de El Tambo.
La guía enlazada en el kit declara edición 2019; su publicación en el kit no se
interpreta como certificación de vigencia jurídica de todas sus referencias.

### Contrato y conservación de datos

Los siete campos de inspección existentes siguen siendo **datos fuente**, sin
pedir secciones redactadas. Fecha, lugar preciso, observaciones y evidencia
permiten recomendaciones vinculadas a hechos. Sin resultados, Ollama propone
verificar ubicación y competencia, y programar una visita si corresponde; no
afirma acumulación ni ordena limpieza o sanción. Una referencia o URL no acredita
que se haya leído su contenido. Los controles rechazan ciertas adiciones no
sustentadas (por ejemplo `parque infantil` donde solo se aportó `parque`), fechas,
lugares y referencias normativas detectables. No son una garantía semántica
general: persisten la revisión humana y la validación de fuentes.

El servidor genera el encabezado y el título inicial con el tipo confirmado
(`Informe de Inspección`), sin usar la instrucción «preparar...» como título.
No incluye el UUID como nombre de autor. La identidad auditada permanece en los
registros de versión; no se convierte en firmante. Las unidades seleccionadas
pueden precargar emisor/destinatario; número, fecha, referencia y firmante quedan
vacíos si no se conocen. La fecha del documento no se deduce de la inspección.

`PUT /informes/{id}` admite adicionalmente un objeto **humano** independiente:

```json
{
  "numero_version": 1,
  "contenido": { "...": "Contenido y encabezado recuperados de la versión vigente" },
  "titulo": "Informe de Inspección",
  "encabezado_oficial": {
    "numero": "",
    "emisor": "",
    "destinatario": "",
    "fecha": "",
    "referencia": "",
    "firmante": "",
    "cargo_firmante": ""
  }
}
```

El ejemplo abrevia `contenido`: debe enviarse el contenido real con sus secciones
obligatorias. La fecha usa `AAAA-MM-DD` o vacío; se rechazan claves desconocidas,
UUID y valores excesivos. Las claves omitidas conservan el valor; un vacío lo
deja pendiente. El servidor guarda esos datos en `contenido.encabezado.documento`
de una **nueva versión**. No se permite alterar directamente metadatos protegidos
en `contenido`. Las nuevas generaciones guardan nombre/versión de plantilla en
el encabezado; la API los expone como `plantilla_nombre` y `plantilla_version`.
En históricos sin ese dato se indica «no registrada», sin inferirlo del catálogo.

React diferencia versión de plantilla de versión guardada del borrador. El aviso
de plantilla posterior compara nombre, tipo y área de la misma familia: inspección
v1 no recibe el aviso de técnica v2. El encabezado se edita en el paso 3 y forma
parte del aviso de cambios pendientes. Vista previa y DOCX usan solo la versión
guardada. Los UUID de encabezados históricos se ocultan en estas representaciones
sin modificar su contenido persistido. Los títulos históricos se conservan: para
corregir un título antiguo hay que editarlo y guardar una nueva versión.

**SQL nuevo: ninguno.** Se usan el JSONB y las versiones existentes. No se altera
la definición de técnica v1/v2 ni de inspección v1; no hay SQL que aplicar en
Supabase por esta mejora. No se reentrena sklearn ni se cambia su catálogo.

### Archivos y verificación

- Generación y contenido: `generador_borrador_ollama.py`, `fidelidad_inspeccion.py`,
  `generar_borrador.py`, `actualizar_borrador.py`, `encabezado_documento.py`.
- Contrato y Word: `informe_request.py`, `informe_response.py`, `exportador_docx.py`.
- Interfaz: `NuevoInforme.jsx`, `EditorBorrador.jsx`, `VistaPreviaInforme.jsx`,
  `EncabezadoDocumento.jsx`, `encabezadoDocumento.js`, `informeService.js`,
  `nuevoInforme.css`.
- Pruebas: `test_inspeccion_contenido.py`, `test_inspeccion_contenido_real.py`,
  ayudante de `test_inspeccion_piloto.py`, expectativas de `test_piloto_v2.py`,
  `encabezadoDocumento.test.mjs`, `estructuraBorrador.test.mjs` y
  `nuevoInforme.test.mjs`. Este README y los artefactos de evidencia completan
  la entrega; los otros cambios locales preexistentes se conservan.

La prueba optativa usa Ollama `qwen2.5:7b`, sklearn real y PostgreSQL **aislado**,
con una identidad ficticia inyectada; no comprueba Supabase Auth real ni escribe
en Supabase. Genera, edita encabezado/secciones, guarda versión 2, recupera por
solicitud y desde otro repositorio, comprueba versión 1 intacta y descarga Word.
La descarga debe conservar toda la base y no llamar al generador. La suite cubre
además permisos, respuesta tardía, reintentos y compatibilidad histórica.

```powershell
$env:NAXJI_RUN_DB_TESTS='0'
$env:NAXJI_TEST_PG_PORT='55433' # clúster local exclusivo de pruebas
$env:NAXJI_RUN_OLLAMA_TESTS='1'
$env:NAXJI_CONTENIDO_EVIDENCE_DIR='D:\NAXJI\docs\evidencias\inspeccion-contenido'
.\.venv\Scripts\python.exe -m pytest tests/test_inspeccion_contenido_real.py -q -s
```

Los [artefactos de ambos casos ficticios](docs/evidencias/inspeccion-contenido/)
contienen datos fuente, propuesta, versión corregida, tiempos, HTTP, DOCX y su
renderizado PDF/PNG. Se abrieron en Word en modo solo lectura, sin macros ni
actualización de enlaces; se revisaron todas sus páginas. No se modifica el Word
original del usuario. La suite frontend usa DOM y HTTP simulado, no una sesión
real de Supabase. Los controles de autenticación existentes permanecen vigentes.

Resultado de esta revisión: **228 pruebas Python aprobadas, 17 optativas omitidas**
(la suite no activa servicios externos por defecto), **2 casos Ollama reales
aprobados por separado**, **43 pruebas frontend aprobadas**, `npm run lint`,
`npm run build` y `git diff --check` correctos. Un intento intermedio de frontend
agotó el tiempo de transporte de Vite durante una interrupción del entorno;
la repetición completa pasó sin cambiar los controles de acceso. Persiste el aviso
de deprecación de Starlette/httpx ya existente.

En la última ejecución real, generar tardó **5,175 s sin resultados** y **6,660 s
con resultados ficticios**, con `qwen2.5:7b`. Ambos recorridos devolvieron HTTP
201 al generar y 200 al editar, recuperar y descargar. Cada DOCX final tiene
**una página**, comprobada en Word y en todas sus imágenes renderizadas.
Los tiempos dependen del estado/carga local del modelo y no son un benchmark.
En el caso con resultados, la edición humana ajusta objetivo y atribución de
conclusiones; el JSON conserva también la propuesta de Ollama sin alterar.

- Sin resultados: [DOCX](docs/evidencias/inspeccion-contenido/inspeccion-sin-resultados.docx),
  [PDF renderizado](docs/evidencias/inspeccion-contenido/inspeccion-sin-resultados.pdf).
- Con resultados ficticios: [DOCX](docs/evidencias/inspeccion-contenido/inspeccion-con-resultados.docx),
  [PDF renderizado](docs/evidencias/inspeccion-contenido/inspeccion-con-resultados.pdf).

Se recargó el backend local en 8001 y se verificaron `/health`, `/auth/config`
(`supabase`/`postgres`) y el nuevo campo OpenAPI desde el frontend de 5174,
solo mediante consultas de lectura. Esto no equivale a repetir el recorrido
autenticado en Supabase. La base aislada de pruebas quedó detenida.

### Revisión documental municipal del 01/10/2026

El caso de las bolsas descritas en el DOCX v3 corresponde, con la información
disponible, a **un informe interno que comunica observaciones**. Una solicitud
y una descripción de visita no constituyen un acta firmada ni acreditan un
procedimiento formal de supervisión ambiental. No se equiparan esos documentos.
La ruta «De Alcaldía / A Gestión Ambiental» de la prueba necesita confirmación:
la definición municipal de informe lo dirige al superior inmediato. NAXJI no
puede inferir la identidad ni el cargo de ese superior desde el catálogo.

Se encontró una fuente municipal auténtica: [Directiva General 001-2019-MDT/GM,
Anexo 08, Modelo de Informe](https://www.gob.pe/institucion/munieltambo/informes-publicaciones/4105169-directiva-de-normas-generales-para-la-comunicacion-escrita),
aprobada por la [RGM 021-2019-MDT/GM, 30/01/2019](https://www.gob.pe/institucion/munieltambo/normas-legales/6862621-021-2019-mdt-gm).
El apartado IV abarca todas las unidades orgánicas. El
[ROF aprobado por OM 012-2020, 30/07/2020](https://www.gob.pe/institucion/munieltambo/normas-legales/6695032-012-2020-mdt-cm-so)
identifica Gestión Ambiental (artículos 121–122). Esta es una base general de
comunicación interna; **no se encontró un formato específico de inspección de
Gestión Ambiental con aprobación y vigencia actual verificadas**. No se afirma
vigencia consolidada en 2026 ni aprobación institucional de esta adaptación.

El PDF de 63 páginas incluye proyectos y duplicados. Se usan las reglas de la
directiva aprobada (páginas PDF 5 y 7–10) y su Anexo 08 (página PDF 19, numeración
impresa 15). El Anexo 09 es de informe técnico y tiene otros apartados: no se
intercambió con el Anexo 08 para acomodar las secciones que ya tenía NAXJI.
El [registro de fuentes](docs/evidencias/formato-municipal/fuentes.json) contiene
URLs, emisor, fecha, tipo, alcance, evidencia ambiental y límites de cada fuente.
Incluye el índice municipal, ambas ordenanzas de supervisión de 2019 y el kit
OEFA. El PDF municipal de supervisión descargado contiene el acto de aprobación,
sin sus tres anexos; no se inventaron anexos ni formatos a partir de él.
El DOCX OEFA solo sirvió para contrastar el procedimiento formal: **ningún
identificador, firma, competencia o formato OEFA se presenta como aprobado por
El Tambo**.

Antes de esta revisión el repositorio tenía un exportador programático y DOCX
piloto de prueba, no un DOCX/DOTX institucional. La nueva base es una
**reconstrucción editable desde el PDF**, identificada visiblemente como PILOTO.
No pretende ser el archivo Word original del municipio.

| Elemento | Fuente municipal | Piloto previo | Adaptación revisable nueva |
|---|---|---|---|
| Encabezado | Logo arriba a la izquierda; registro documental/expediente según VI.e | Título y metadatos NAXJI | Posiciones administrativas; logo y registros pendientes |
| Código | Informe con número y siglas, destacado/subrayado | Campo Número | INFORME N° y valor humano o [POR COMPLETAR]; no toma el número del ejemplo |
| Destinatario | Nombre y cargo | Área destinataria | Dos datos humanos separados, inicialmente vacíos |
| Emisor | Código y firma/postfirma | Fila De | Sin fila De; unidad queda como dato de trabajo, firma/cargo se completan manualmente |
| Asunto y referencia | Filas ASUNTO y REF. | Filas de encabezado propias | Filas conservadas; asunto de solicitud, referencia humana; negrita y subrayado según reglas |
| Fecha | Lugar, día, mes, año | Fecha ISO | Lugar humano y fecha en español; fecha de emisión separada de inspección |
| Cuerpo | Texto continuo | Seis secciones | Un cuerpo editable, sin títulos añadidos en Word |
| Cierre | Atentamente; firma y sello; postfirma | Firmante y cargo | Cierre conservado; firma/sello pendientes, sin imágenes copiadas |
| Adjuntos | Iniciales, Cc., Adjunto | Sin esos campos | Datos humanos; no convierte referencias descritas en anexos adjuntos |
| Presentación | A4, Arial 11, sencillo; superior 3,5 cm, otros 3 cm | Superior/inferior 1,8 cm, laterales 2,5 cm | Reglas municipales conservadas |
| Paginación | Folio inferior derecho para documentos de varias hojas | Página X de Y con marca piloto | Folio inferior derecho; también visible en una hoja como decisión de implementación |

Las leyendas «Anexo 08 / Modelo de Informe», líneas de puntos para llenar,
número de ejemplo y foliación del expediente fuente no se transfieren como
contenido del informe emitido. No se copiaron sellos, firmas ni lema político
del membrete histórico. Son diferencias deliberadas: identificación de PILOTO
en la cabecera, marcador de logo vigente y paginación incluso en una hoja. La
[fuente extraída](docs/evidencias/formato-municipal/fuente-municipal-extracto.pdf)
y los dos renderizados permiten revisarlas.

La **inspección v2** conserva siete campos de datos fuente y define una salida:

```json
{
  "formato_documento": "mdt_informe_anexo08_2019_revision1",
  "secciones_salida": [
    {"clave": "cuerpo", "titulo": "Cuerpo del informe interno", "obligatoria": true}
  ]
}
```

`Plantilla.formato_documento` es opcional. PostgreSQL recupera el nuevo campo
mediante el mapeador existente; si la columna aún no está aplicada, conserva
`None` y el piloto anterior funciona. Memory también admite el atributo de la
entidad. Al generar se copia al encabezado protegido de la versión; las ediciones
lo preservan. Exportar usa ese snapshot, no el estado actual del catálogo, y no
llama a Ollama. La v1 conserva seis secciones y su exportador anterior. No se
reestructuran versiones históricas ni se desactiva la plantilla técnica v1/v2.

Los campos administrativos nuevos son `cargo_destinatario`, `lugar_emision`,
`registro_documento`, `registro_expediente`, `iniciales`, `copias` y `anexos`.
Se guardan mediante `encabezado_oficial`, separado del contenido de Ollama;
solo se habilitan para esta estructura. No hay números correlativos inventados,
firmas automáticas ni consulta supuesta de fotografías o documentos.

La contradicción del v3 se verificó leyendo el DOCX local y su solicitud/versiones
en una transacción PostgreSQL **READ ONLY**. La fuente sí describe dos bolsas
cerradas y aclara que no se identificó su contenido/origen/permanencia. El texto
genérico provenía de la generación original y se conservó en las ediciones;
no era una pérdida del exportador. El prompt v7 separa la rama con observaciones
de la rama sin resultados. La validación rechaza la negación genérica de los
hallazgos aportados y la atribución de residuos a bolsas cuyo contenido se declara
desconocido. Son controles conservadores, no prueba universal de veracidad.
Se requiere revisión humana y pueden existir falsos positivos/omisiones fuera
de los patrones cubiertos. No se reescribe silenciosamente la respuesta del modelo.

La v3 en Supabase **no se modificó**. La [corrección propuesta](docs/evidencias/formato-municipal/correccion-v3.txt)
puede incorporarse desde el editor como una nueva versión después de revisarla.
Ninguna nueva versión de ese informe fue creada automáticamente.

SQL exacto pendiente, en este orden y ejecutando cada archivo completo:

1. [20261001_03_formato_documento.sql](database/migrations/20261001_03_formato_documento.sql): columna nullable, sin reclasificar filas anteriores.
2. [20261001_inspeccion_v2_anexo08.sql](database/seeds/20261001_inspeccion_v2_anexo08.sql): nueva versión de inspección, por códigos `INFORME_INSPECCION` y `MDT_SGGA`; rechaza definiciones distintas y no modifica la v1.

**No aplicados a Supabase.** Se probaron en bases aleatorias desechables de un
clúster exclusivo en `127.0.0.1:55433`. Se comprobó primera ejecución, repetición
sin cambios, rechazo de conflictos, persistencia y conservación de filas/fechas
anteriores. La v2 no aparecerá en Supabase hasta que el usuario revise y aplique
estos archivos. No basta aplicar SQL para certificar aprobación institucional.

Archivos de esta revisión (sobre cambios locales conservados):

- Dominio/API: `plantilla.py`, `encabezado_documento.py`, `catalogo_response.py`.
- Generación: `generador_borrador_ollama.py`, `fidelidad_inspeccion.py`.
- Word: `exportador_docx.py`, `exportador_mdt.py`, `templates/mdt_anexo08_revision1.docx`, `scripts/crear_base_informe_mdt.py`.
- Frontend: `EncabezadoDocumento.jsx`, `VistaPreviaInforme.jsx`, `encabezadoDocumento.js`; no altera la navegación de los cuatro pasos.
- SQL: los dos archivos enlazados. Pruebas: `test_formato_mdt.py`, `test_exportacion_mdt.py`, `test_inspeccion_contenido.py`, `frontend/nuevoInforme.test.mjs`, fixture `inspeccion_piloto.json`.
- Este README y `docs/evidencias/formato-municipal/`.

Resultados finales: **236 pruebas Python aprobadas, 19 optativas omitidas**;
**51 pruebas frontend aprobadas**; lint, build y comprobación de diff correctos.
Por separado se ejecutaron **4 casos Ollama reales**: dos con la estructura nueva
y dos de regresión con la inspección v1. En todos, generación HTTP 201,
edición/recuperación/descarga HTTP 200. La prueba de permisos produjo 403 al
descargar un informe ajeno. Se recuperó desde otra instancia de repositorio y se
verificó que cambiar el catálogo no altere la exportación guardada.

La última prueba de la v2 con `qwen2.5:7b` tardó **2,951 s sin resultados** y
**3,951 s con observaciones parciales**. Son tiempos locales, no un benchmark.
Los [JSON de evidencia](docs/evidencias/formato-municipal/) conservan entrada,
propuesta, edición guardada, tiempos y HTTP. Las identidades son ficticias,
inyectadas en FastAPI; no se probó una nueva sesión Supabase Auth ni un flujo
escrito en la nube. El frontend se verificó con React/DOM y HTTP simulado para
v1 y v2, incluyendo recuperación UUID, respuestas tardías, errores y permisos.

Ambos Word se abrieron en modo solo lectura con Word, macros y enlaces
desactivados, y se renderizó **cada página** a PDF/PNG. No hay LibreOffice en este
Windows; se usó Word para la comprobación visual. Ambos tienen una página,
cuerpo continuo, cierre y firma juntos, sin sección breve aislada. Las propuestas
conservan la distinción entre observación de bolsas y contenido desconocido;
su estilo y eventual repetición siguen sujetos a edición humana.

- Sin resultados: [DOCX](docs/evidencias/formato-municipal/anexo08-sin-resultados.docx), [PDF](docs/evidencias/formato-municipal/anexo08-sin-resultados.pdf), [página renderizada](docs/evidencias/formato-municipal/anexo08-sin-resultados-pagina-1.png).
- Con observaciones: [DOCX](docs/evidencias/formato-municipal/anexo08-con-observaciones.docx), [PDF](docs/evidencias/formato-municipal/anexo08-con-observaciones.pdf), [página renderizada](docs/evidencias/formato-municipal/anexo08-con-observaciones-pagina-1.png).

Antes de uso institucional se necesita confirmación de vigencia/aplicación de
la directiva o su reemplazo, DOCX/DOTX y logo vigente o aprobación de esta
reconstrucción, destinatario/firmante/cargos/ruta, siglas y registros oficiales.
Si se pretende supervisión ambiental formal, hacen falta el reglamento vigente
completo con sus anexos y la acreditación del procedimiento y competencia;
el modelo OEFA no los sustituye. No hubo push ni escrituras en Supabase.
