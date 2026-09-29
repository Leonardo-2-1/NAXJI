# NAXJI — Copilot Municipal: backend PMV1

API FastAPI con arquitectura hexagonal, React, PostgreSQL y Supabase Auth.
Permite crear una solicitud, confirmar/corregir contexto, completar una plantilla,
generar un borrador y guardar ediciones como versiones. El predictor ejecuta RF-IA-01
con correspondencias de catálogo; el generador de borradores sigue siendo **mock**.
La plantilla técnica piloto es demostrativa, no un formato municipal aprobado.

Estado y evidencias: [catálogos PMV1](docs/IMPLEMENTACION_CATALOGOS_PMV1.md) y
[autenticación/persistencia](docs/VERIFICACION_SUPABASE.md).

## Ejecutar en Windows / PowerShell

Requiere Python 3.11 o superior. Desde la raíz del repositorio:

```powershell
# Solo si el entorno todavía no existe:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
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

Carga inicial, con vista previa y verificación de idempotencia:

```powershell
.\.venv\Scripts\python.exe scripts/cargar_catalogos.py
# Después de revisar las inserciones:
.\.venv\Scripts\python.exe scripts/cargar_catalogos.py --apply
```

La carga ya fue aplicada en este proyecto; repetirla no duplica registros.
Guarde el enlace `/nuevo-informe?solicitud=UUID` para recuperar el formulario.

## Modo de pruebas en memoria (opcional)

Solo para pruebas: `NAXJI_PERSISTENCE_MODE=memory` y `NAXJI_AUTH_MODE=mock`.
En ese modo los datos sí se pierden al reiniciar y cada proceso tiene su memoria.

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
7. Consulte `GET /plantillas/{plantilla_id}/campos` y copie los IDs de los campos
   `antecedentes` y `detalle`. Guarde:

   ```json
   {
     "valores": [
       {"campo_plantilla_id":"UUID_ANTECEDENTES", "valor":"Solicitud de inspección recibida."},
       {"campo_plantilla_id":"UUID_DETALLE", "valor":"Se registraron observaciones en el parque."}
     ]
   }
   ```

   Use `PUT /solicitudes/{id}/valores`. **Reemplaza todo el conjunto de valores**;
   incluya también los que desea conservar. Puede guardar formularios incompletos,
   pero no generar con ellos. Los tipos admitidos son text, textarea, date
   (`YYYY-MM-DD`), number, boolean y select. Los campos select de la demo usan
   `configuracion.opciones`; es una convención del mock, no una restricción nueva del SQL.
8. Ejecute `POST /solicitudes/{id}/generar-borrador` con
   `{"instrucciones":"Respetar los datos de la inspección."}` o `{}`.
   Recibirá `informe_id`, `estado: BORRADOR`, `numero_version: 1` y `contenido`.
   El mock devuelve texto de demostración, sin realizar inferencia ni llamadas externas.
9. Recupere `GET /informes/{informe_id}` y edite con `PUT /informes/{informe_id}`:

   ```json
   {
     "numero_version": 1,
     "contenido": {
       "antecedentes": "Solicitud de inspección recibida.",
       "desarrollo": "Contenido revisado por el funcionario.",
       "conclusiones": "Conclusiones editadas."
     }
   }
   ```

   Se agrega la versión 2, con origen `USUARIO`; la versión anterior se conserva.
   Envíe la versión que leyó. Una versión antigua produce 409.

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
| POST | `/solicitudes/{solicitud_id}/generar-borrador` | Generar mock; devuelve 201 |
| GET | `/informes/{informe_id}` | Consultar la última versión |
| PUT | `/informes/{informe_id}` | Guardar una nueva versión |

Se conserva `POST /solicitudes/` como alias. El cuerpo anterior `descripcion`
se sustituye por valores de plantilla, porque no existe esa columna en `solicitudes`.
Los IDs enteros anteriores se sustituyen por UUID.

Estados de solicitud: `BORRADOR → LISTA_PARA_GENERAR → PROCESANDO → GENERADA`.
Los dos primeros admiten cancelación a `CANCELADA`. La API deriva los estados;
solo acepta `CANCELADA` como cambio manual. Modificar asunto/tipo/destino invalida
la confirmación; cambiar plantilla elimina valores de la plantilla anterior.
Cambiar el asunto exige una nueva predicción. Cada solicitud puede generar un único informe.
PMV1 solo edita informes en `BORRADOR`; los demás estados del SQL están definidos,
pero sus flujos de revisión/aprobación quedan fuera de este alcance.

Errores: 400 reglas/datos de negocio, 401 sin autenticación, 403 permiso/propietario,
404 recurso inexistente, 409 estado/versión incompatible, 422 request inválido y
500 fallo interno o de generación. Los errores 500 no exponen detalles del proveedor.

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

## Integración pendiente y contratos

Consulte [docs/CONTRATOS_PMV1.md](docs/CONTRATOS_PMV1.md) y el
[inventario de entrega](docs/ENTREGA_PMV1.md).

- React, repositorios PostgreSQL, unidad de trabajo y Supabase Auth están integrados.
- RF-IA-01: pendientes validación experimental institucional, categorías sin correspondencia
  y curación jurídica de etiquetas normativas. No se reentrenó el modelo.
- LLM: implementar `GeneradorBorrador` con plantilla, datos, contexto e instrucciones.

El `OllamaAdapter` y `LLMPort` que ya existían en el commit remoto se conservan sin
modificaciones. No se importan ni instancian al iniciar la aplicación PMV1. Su contrato
antiguo de texto/prompt requerirá adaptación por el responsable de la integración;
el controller PMV1 utiliza exclusivamente el puerto estructurado y su mock.

## Interfaz web PMV 1

La interfaz React queda como adaptador de entrada en `src/adapters/in/web/` (páginas, componentes, layouts y servicios). No modifica controladores ni casos de uso del backend.

Con el backend encendido en `http://127.0.0.1:8000`:

```powershell
npm install
npm run dev
```
