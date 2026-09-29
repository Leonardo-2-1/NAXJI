# Verificación de Supabase — NAXJI

Fecha: 28 de septiembre de 2026. Rama inspeccionada: `main`.

**Resultado: conexión y CRUD comprobados; lectura de FastAPI desde PostgreSQL comprobada con identidad de prueba. Persistencia completa de solicitudes tras reiniciar: pendiente por ausencia de perfiles. Supabase Auth y políticas RLS: pendientes.**

## Causa del error y entorno inspeccionado

La raíz es `C:\Users\DELL INSPIRON\Documents\NAXJI`. La carpeta `scripts` existía, pero solo contenía `__pycache__`. El archivo fuente estaba en la rama `BasedeDatos`, commit `758d558`, no en `main`. No era un error de contraseña ni de PostgreSQL.

Se recuperó y adaptó esa implementación en la ruta solicitada. No se cambió de rama, no se clonó otro repositorio ni se sobrescribió `.env`.

El esquema de referencia es `NAXJI_database_schema_actual.sql`; no se ejecutó ni modificó. Los puertos y casos de uso existentes se conservaron. Antes de la corrección, `Container` creaba exclusivamente repositorios Memory. No existían módulos Python de conexión `NAXJI_DB_*` en `src`.

| Intérprete | Estado inicial | Uso actual |
| --- | --- | --- |
| `.venv/Scripts/python.exe` — Python 3.13.15 | FastAPI, pytest, httpx y sklearn; sin psycopg/dotenv | Backend y pruebas; se agregaron solo psycopg/dotenv y sus dependencias |
| `venv/db-check/Scripts/python.exe` — Python 3.14.4 | psycopg y dotenv ya instalados | Diagnóstico y CRUD directo; no se instalaron dependencias adicionales |

Versiones verificadas: `psycopg` y `psycopg-binary` 3.3.6; `python-dotenv` 1.2.3. La instalación en `.venv` también requirió `tzdata` 2026.4. Ambos `pip check` devolvieron `No broken requirements found.`

El intérprete indicado explícitamente en el comando tiene prioridad sobre el entorno activado en la terminal. Tener `(.venv)` en el prompt no impide ejecutar `venv/db-check/Scripts/python.exe`.

## Archivos creados o modificados

| Ruta completa | Cambio y motivo |
| --- | --- |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\scripts\verificar_supabase.py` | Creado en main recuperando el diagnóstico de BasedeDatos; argparse, SELECT 1, inventario SQL, CRUD de tipos_informe y rollback verificado incluso ante fallo. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\src\infrastructure\configuration\database.py` | Nuevo: configuración privada compartida, .env relativo al proyecto, validación, SSL, errores sanitizados y contraseña excluida del repr. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\out\persistence\postgres.py` | Nuevo: cinco repositorios que implementan los puertos existentes, unidad de trabajo por contexto, JSONB, bloqueos de filas, transacciones y errores controlados. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\out\ai\context_predictor_catalogo.py` | Nuevo: traducción de UUID de la PoC a UUID PostgreSQL por código. Rechaza catálogos faltantes sin insertar datos demo. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\src\infrastructure\configuration\settings.py` | Modificado: NAXJI_PERSISTENCE_MODE=memory|postgres y carga explícita de configuración local. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\src\infrastructure\configuration\container.py` | Modificado: composición del modo solicitado; no cae a memoria ante errores PostgreSQL; predictor inyectable en pruebas. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\src\infrastructure\dependencies.py` | Modificado: las identidades demo quedan limitadas a memoria; no autentican sobre PostgreSQL. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\src\main.py` | Modificado: transmite settings al contenedor, valida coherencia y devuelve 503 sanitizado ante fallos de persistencia; descripción actualizada. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\out\ai\context_predictor_mock.py` | Modificado: corrige el import NORMATIVA inexistente usando NORMATIVAS[0]. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\requirements.txt` | Modificado: agrega psycopg[binary]>=3.2,<4 y python-dotenv>=1,<2. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\tests\conftest.py` | Modificado: pruebas de aplicación en memoria con predictor mock explícito; no dependen del .env ni del modelo real. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\tests\test_api.py` | Modificado: actualiza la expectativa del catálogo de áreas de 2 a 6. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\tests\test_postgres.py` | Nuevo: valida configuración, protección de credenciales, transacciones, errores HTTP, rechazo de tokens demo, traducción de IDs y predictor real. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\tests\test_supabase_integration.py` | Nuevo: seis pruebas opt-in de Supabase; rollback, lecturas HTTP/SQL, rechazo de perfiles inexistentes, flujo completo y reinicio. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\tests\postgres_restart_worker.py` | Nuevo: proceso de prueba para crear/recuperar solicitudes en dos intérpretes independientes usando un perfil existente y autenticación inyectada solo en TestClient. |
| `C:\Users\DELL INSPIRON\Documents\NAXJI\docs\VERIFICACION_SUPABASE.md` | Nuevo: este informe, comandos reproducibles, evidencias y límites de la integración. |

No se cambiaron endpoints, código React, esquema SQL, usuarios, roles, contraseñas ni políticas. La eliminación de `.env.example` visible en la inspección inicial era un cambio previo; no se editó ese archivo como parte de este trabajo.

El parche completo de código, incluidos archivos nuevos, se guarda localmente en `venv/run-logs/supabase-cambios-20260928.patch`. No contiene `.env`. `git diff --check` pasó.

## Ejecución definitiva desde PowerShell

Desde la raíz:

```powershell
.\venv\db-check\Scripts\python.exe .\scripts\verificar_supabase.py --help
.\venv\db-check\Scripts\python.exe .\scripts\verificar_supabase.py
.\venv\db-check\Scripts\python.exe .\scripts\verificar_supabase.py --crud
```

También se ejecutó sin argumentos desde `scripts`:

```powershell
..\venv\db-check\Scripts\python.exe .\verificar_supabase.py
```

Ambas ubicaciones encontraron el mismo `.env` y conectaron correctamente. El código resuelve la raíz con `Path(__file__)`; no contiene rutas absolutas de esta computadora. El entorno del proceso tiene prioridad sobre `.env`, y se evita interpolar contraseñas que contengan `${...}`.

`--help` produjo:

```text
usage: verificar_supabase.py [-h] [--crud]
options:
  -h, --help  show this help message and exit
  --crud      Prueba crear, leer, actualizar y eliminar una fila ficticia con
              rollback.
```

La comprobación de existencia produjo:

```text
FullName                                                             Length
--------                                                             ------
C:\Users\DELL INSPIRON\Documents\NAXJI\scripts\verificar_supabase.py   9406
```

Comprobación de sintaxis ejecutada, sin errores y salida 0:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
```

## Evidencia real de conexión y CRUD

Salida de la ejecución final de `--crud`:

```jsonl
{"status": "ok", "conexion": 1, "ssl": true}
{"status": "ok", "authenticated": true, "ssl": true, "read_only": true, "database": "postgres", "database_role": "postgres", "expected_tables": 14, "visible_tables": 14, "tables": ["areas_municipales", "campos_plantilla", "informes", "normativas", "perfiles", "plantillas", "prediccion_normativas", "predicciones_ia", "roles", "solicitud_valores", "solicitudes", "tipos_informe", "usuario_roles", "versiones_informe"], "missing_or_inaccessible_tables": []}
{"status": "ok", "table": "public.tipos_informe", "count": 4}
{"status": "ok", "rollback": "verified", "remaining_test_rows": 0, "original_records_unchanged": true}
{"status": "ok", "scope": "supabase_postgresql", "table": "public.tipos_informe", "fixture_id": "66762667-cfd4-4e7d-b2a8-4d63b4b9841f", "crud": {"create": "ok", "read": "ok", "update": "ok", "delete": "ok"}, "original_count": 4, "final_count": 4, "original_records_unchanged": true, "rollback": "ok", "remaining_test_rows": 0}
```

La primera consulta de comprobación fue `SELECT 1 AS conexion`. Las 14 tablas del SQL de referencia existen. `SELECT COUNT(*) FROM public.tipos_informe` devolvió **4**; no es una constante del script.

El diagnóstico verifica la estructura básica de `tipos_informe`, usa UUID y código `TEST_CRUD_...` únicos, y parametriza los valores. Solo actualiza y elimina su propia fila por UUID y código. Ejecuta una transacción `force_rollback=True`: tras comprobar DELETE, reinserta su fila temporal dentro de esa misma transacción para demostrar que el rollback también elimina una escritura pendiente.

La comparación de cantidad y huella del contenido completo de `tipos_informe`, antes y después, coincidió. Si hay una modificación concurrente ajena, se informa como discrepancia; no se atribuye automáticamente al script. El bloque `finally` comprueba ausencia del registro y conservación del contenido también si falla una operación. La prueba automatizada inyectó un fallo antes del UPDATE y verificó el rollback.

No se utilizó DROP, TRUNCATE, modificación del esquema ni desactivación de RLS en las comprobaciones.

## Persistencia desde FastAPI

Configuración explícita sin editar `.env`:

```powershell
$env:NAXJI_PERSISTENCE_MODE = 'postgres'
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Este comando selecciona los repositorios PostgreSQL. **No habilita el inicio de sesión Supabase:** mientras el adaptador de autenticación real no exista, los tokens demo reciben 401 en PostgreSQL. Por defecto, el modo PostgreSQL selecciona autenticación `disabled`. No se deben presentar los tests con identidad inyectada como prueba de login real.

Para conservar la demostración actual del frontend:

```powershell
$env:NAXJI_PERSISTENCE_MODE = 'memory'
$env:NAXJI_AUTH_MODE = 'mock'
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

No se modificó el modo persistente de tu `.env` ni se reinició un servidor de uso diario. El modo por defecto sigue siendo `memory`. Las pruebas crearon aplicaciones independientes mediante TestClient.

Los cinco adaptadores PostgreSQL implementan los mismos puertos que los de memoria. La unidad de trabajo comparte una conexión dentro del caso de uso, confirma al terminar y revierte ante excepciones. Los agregados cargados para escritura usan `FOR UPDATE`; las lecturas independientes usan transacciones de solo lectura. Las versiones de informe se insertan sin reescribir el historial. Los errores SQL se traducen a respuestas controladas sin exponer consultas ni parámetros.

El predictor mantiene los modelos existentes y traduce los códigos conocidos a los IDs reales. Si falta un área o normativa, devuelve un error de catálogo; no carga los datos ficticios de la PoC en Supabase.

### Lo realmente demostrado

La prueba construye `Container` en modo PostgreSQL e inyecta una identidad únicamente en `TestClient` para aislar la persistencia de la autenticación pendiente. Compara los resultados del endpoint con SQL directo:

```text
GET /tipos-informe: 200, 4 IDs iguales a PostgreSQL; autenticacion inyectada
POST /solicitudes sin perfil: 400; fila no persistida; FK conservada
```

También se insertaron catálogos temporales dentro de una transacción revertida para comprobar los adaptadores de áreas, normativas, plantillas y campos. Se verificó que esas filas no existieran después. Las consultas vacías de solicitudes, predicciones e informes se ejecutaron contra PostgreSQL.

### Lo que no se pudo demostrar

La base tiene **0 perfiles y 0 asignaciones de roles a usuarios**. `solicitudes.usuario_id` es obligatorio y referencia `perfiles`, que a su vez referencia `auth.users`. No se crearon ni alteraron usuarios para sortear esa restricción.

Por eso se omitieron estas pruebas, con motivo explícito:

- Crear una solicitud por FastAPI en un proceso, comprobarla por SQL y recuperarla en un segundo proceso independiente.
- Ejecutar todos los agregados PostgreSQL desde el flujo HTTP: valores, predicción, validación, generación, historial de versiones y conflicto de edición.

Esas pruebas están implementadas y requieren un perfil activo existente con rol FUNCIONARIO o ADMINISTRADOR. La segunda usa catálogos sintéticos dentro de rollback; la primera limpia exclusivamente su solicitud temporal. Ambas inyectan identidad de prueba: **no validan Supabase Auth ni autorización RLS**. Las escrituras completas de estos agregados aún no están verificadas en esta base.

## Pruebas automatizadas y fallos encontrados

Comando reproducible de la validación conjunta:

```powershell
$env:NAXJI_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q -rs -p no:cacheprovider
Remove-Item Env:\NAXJI_RUN_DB_TESTS
```

Sin `NAXJI_RUN_DB_TESTS=1`, las pruebas que requieren Supabase se omiten intencionalmente.

Resultado real final (salida detallada en `venv/run-logs/supabase-tests-20260928.txt`):

```text
SKIPPED [2] tests\test_supabase_integration.py:146: Persistencia tras reinicio bloqueada: no existe perfil activo con rol de escritura; no se crean usuarios
60 passed, 2 skipped, 1 warning in 25.17s
```

La advertencia es de Starlette sobre el uso de httpx con TestClient, no un fallo de integración.

Fallos iniciales y correcciones:

| Resultado observado | Causa | Corrección |
| --- | --- | --- |
| `can't open file ... verificar_supabase.py` | Script solo en BasedeDatos | Recuperado y adaptado en main |
| `assert 6 == 2` | Expectativa antigua de áreas | Prueba actualizada al catálogo actual |
| `assert False is True`, expectativa `MOCK_` | Tests mock ejecutaban el predictor sklearn real | Inyección explícita del mock en fixtures; predictor real probado por separado |
| `ImportError: cannot import name 'NORMATIVA'` | Símbolo eliminado del catálogo | Uso de NORMATIVAS[0] |
| Suite inicial: `5 failed, 40 passed` | Inconsistencias anteriores | Suite final sin fallos |
| `PermissionError: [WinError 5] Acceso denegado` en temporales de pytest | Restricción del entorno aislado de ejecución | Reejecución autorizada fuera del aislamiento con carpeta temporal única; pasó |
| Docker: `open //./pipe/dockerDesktopLinuxEngine: El sistema no puede encontrar el archivo especificado` | Motor Docker no disponible | No se creó ni utilizó una base local; las pruebas de PostgreSQL ejecutadas usaron Supabase |

## Seguridad, datos conservados y límites

Comprobaciones finales reales:

```text
ENV_INTACTO= True
CREDENCIAL_EN_ARCHIVOS_VERSIONABLES= False
CREDENCIAL_EN_DIST= False
ENV_VERSIONADO= False
ESQUEMA_SQL_MODIFICADO= False
```

`git check-ignore .env` devolvió `.env`; `git ls-files -- .env` no devolvió archivos. La huella SHA-256 de `.env` coincide con la tomada antes de modificar código. No se hizo commit ni push.

Conteos finales:

```text
areas_municipales: 0
campos_plantilla: 0
informes: 0
normativas: 0
perfiles: 0
plantillas: 0
prediccion_normativas: 0
predicciones_ia: 0
roles: 4
solicitud_valores: 0
solicitudes: 0
tipos_informe: 4
usuario_roles: 0
versiones_informe: 0
rol_bypassrls: True
tablas_con_rls: 14
politicas_rls: 0
```

La conexión emplea el rol PostgreSQL configurado localmente, con BYPASSRLS. Estas pruebas **no acreditan aislamiento por usuario mediante RLS**. Ese comportamiento está documentado por [Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security). El rollback controlado sigue la API de transacciones de [psycopg](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

Para completar el uso real desde React quedan: autenticación Supabase en backend/frontend, perfiles y roles autorizados, catálogos institucionales revisados, políticas RLS y la decisión explícita sobre el rol de conexión. No basta con añadir un perfil para que los tokens demo funcionen sobre PostgreSQL: se rechazan deliberadamente en ese modo.

| Componente | Estado anterior | Corrección realizada | Evidencia | Estado final |
| --- | --- | --- | --- | --- |
| Script de verificación | Ausente en main | Recuperación y adaptación al contrato solicitado | --help, ejecución desde dos directorios | Comprobado |
| Conexión PostgreSQL | Verificación separada en otra rama | Configuración compartida y SSL obligatorio | SELECT 1; 14 tablas; conteo real 4 | Comprobada |
| Operaciones CRUD | Script anterior usaba áreas | Prueba sobre tipos_informe, parámetros, finally y rollback | C/R/U/D OK; 4→4; huella idéntica; 0 temporales | Comprobadas |
| Repositorios PostgreSQL | Solo memoria | Cinco adaptadores y unidad de trabajo | Lecturas reales y rollback; escrituras completas bloqueadas por falta de perfil | Implementados, verificación parcial |
| FastAPI–Supabase | Endpoints en memoria | Selección de modo y composición PostgreSQL | GET con IDs reales; POST sin perfil rechazado; reinicio omitido | Lectura comprobada; escritura y reinicio pendientes |
| Seguridad y credenciales | .env privado; Auth mock; RLS sin políticas | Configuración privada y rechazo de demos sobre PostgreSQL | .env intacto/no versionado; BYPASSRLS real; 0 políticas | Secretos conservados; Auth/RLS pendientes |
| Pruebas automatizadas | 40 aprobadas, 5 fallidas | Fixtures corregidos y pruebas de configuración/integración | 60 passed, 2 skipped | Sin fallos ejecutados; 2 bloqueadas |

## Integración de Supabase Auth y persistencia de solicitudes – PMV1

Actualización: **29 de septiembre de 2026**. Esta sección sustituye el estado
pendiente de autenticación, perfiles y persistencia descrito en la revisión anterior.
La revisión anterior se conserva como evidencia histórica.

### Resultado de esta etapa

Se comprobaron **autenticación real, persistencia y aislamiento entre funcionarios**.
El usuario inició sesión manualmente en dos ventanas aisladas de Edge, con las cuentas
ya existentes `funcionario1.naxji@gmail.com` y `funcionario2.naxji@gmail.com`.
No se solicitaron contraseñas por chat ni se guardaron en archivos de prueba.

Las tres cuentas indicadas por el usuario existían y tenían sus perfiles activos:
ADMINISTRADOR para el administrador y FUNCIONARIO para los dos funcionarios.
No se crearon de nuevo ni se cambiaron sus contraseñas, perfiles o asignaciones.

El frontend conserva sus componentes y rutas. El login real usa
`React → FastAPI /auth/login → Supabase Auth /auth/v1/token`.
FastAPI valida cada Bearer token consultando `/auth/v1/user` con HTTPS, y obtiene
el perfil y los roles vigentes de PostgreSQL usando exclusivamente el UUID verificado.
No confía en UUID, roles ni metadata administrativa suministrados por el navegador.

Se añadieron `/auth/config`, `/auth/login`, `/auth/refresh` y `/auth/logout`.
Se mantuvo `/auth/me`; Vite lo expone como `/api/auth/me` mediante el proxy existente.
Su respuesta conserva los campos anteriores y agrega correo, nombres, apellidos,
cargo y nombre del área. Las respuestas de autenticación tienen `Cache-Control: no-store`.

El access token vive en memoria del navegador. El refresh token permanece en una
cookie HttpOnly y SameSite=Strict; Secure se habilita en HTTPS. El modo local HTTP
requiere explícitamente `NAXJI_AUTH_COOKIE_SECURE=false`. Las peticiones de sesión
verifican origen y un encabezado no simple contra CSRF. Las contraseñas no se
persisten ni se reflejan en errores de validación. Los 401 renuevan la sesión una
sola vez; los 403 no conceden permisos ni se convierten en reintentos de escritura.

### Estrategia de autorización y RLS aplicada

La conexión del backend sigue siendo privilegiada y tiene BYPASSRLS. **No se afirma
que RLS controle esas conexiones**: sus escrituras pasan por la validación de
identidad, perfil activo, rol y propiedad en FastAPI y en los casos de uso existentes.
Los roles REVISOR y APROBADOR no reciben acceso global a solicitudes ajenas.
No se implementaron endpoints de administración de usuarios fuera de los casos de
uso existentes; un cliente no puede asignarse roles mediante HTTP.

La migración independiente `migrations/20260928_01_auth_rls.sql` fue explicada,
validada primero con rollback y aplicada después de pasar sus pruebas. Su efecto:

- Mantiene RLS activado en las 14 tablas y añade **14 políticas SELECT**.
- `authenticated` puede leer catálogos autorizados y sus recursos propios;
  ADMINISTRADOR conserva la consulta administrativa prevista por la autorización.
- `anon` no tiene acceso a las tablas PMV1. Las escrituras directas de
  `authenticated` quedan revocadas: las operaciones del flujo se realizan por FastAPI.
- No permite modificar directamente perfiles, roles ni asignaciones, ni siquiera
  alterando metadata del JWT.
- Añade funciones con `SECURITY DEFINER`, `search_path` vacío y permisos explícitos
  en `naxji_private`; no agrega funciones privilegiadas a la API pública.
- Añade un trigger para futuros usuarios de Auth: crea perfiles pendientes,
  inactivos y sin roles, usando el UUID de Auth y valores seguros para campos
  obligatorios. No reescribe perfiles existentes ni asigna ADMINISTRADOR.

El trigger fue probado mediante un usuario exclusivamente transaccional, revertido
al terminar. Se comprobaron metadata maliciosa de rol/estado, nombre vacío,
longitud máxima de apellidos y ausencia de asignación automática de roles.
Un fallo del trigger aborta el alta con un mensaje controlado, sin exponer metadata.
La activación y asignación de roles para futuros usuarios sigue siendo un
procedimiento administrativo autorizado, no un permiso de autoedición del cliente.

Pruebas SQL reales bajo `SET LOCAL ROLE authenticated`:

```text
RLS_contexto_sin_BYPASSRLS: OK
RLS_funcionario_A_lee_su_solicitud: OK
RLS_funcionario_B_no_lee_solicitud_A_ni_eleva_rol_con_metadata: OK
RLS_escritura_directa_y_autoasignacion_roles_denegadas: OK
RLS_anon_sin_acceso: OK
Trigger_perfil_pendiente_datos_validados: OK
Trigger_no_asigna_roles: OK
Cuentas_perfiles_roles_y_contrasenas_existentes_intactos: OK
Migracion: APLICADA
```

Además, se enviaron los **JWT reales** de A y B a la Data API de Supabase:
A pudo leer su solicitud y B recibió una lista vacía para esa misma solicitud.
Esto acredita RLS en un contexto autenticado no privilegiado, separado de las
consultas administrativas del backend.

### Evidencia real de persistencia y sesiones

La transcripción se conserva en [evidencias/auth-manual-20260929.txt](evidencias/auth-manual-20260929.txt).
Se usaron solicitudes con prefijo TEST_AUTH; se compararon asunto y propietario
con SQL directo. A pudo editarlas; B recibió 403 tanto al consultar como al modificar
la solicitud de A, y pudo crear/leer su propia solicitud. Los intentos de enviar
`usuario_id` y `roles` en la petición fueron rechazados con 422; el intento de
modificar roles mediante PUT `/auth/me` recibió 405.

El verificador inició un proceso uvicorn independiente, lo finalizó y creó un
segundo proceso con PID distinto. El segundo recuperó el contenido actualizado
desde PostgreSQL y siguió rechazando el acceso de B. No se simula el reinicio
reutilizando un mismo contenedor en memoria.

```text
LOGIN_REACT_SUPABASE_Y_PERFIL_A: OK
LOGIN_REACT_SUPABASE_Y_PERFIL_B: OK
Persistencia_SQL_datos_y_propietario: OK
B_lectura_ajena_denegada_403: OK
B_modificacion_ajena_denegada_403: OK
RLS_Data_API_JWT_real_A: OK
RLS_Data_API_JWT_real_B: OK
Backend_proceso_anterior_finalizado_y_reiniciado: OK
Persistencia_despues_reinicio: OK
Aislamiento_conservado_despues_reinicio: OK
Renovacion_sesion_cookie_HttpOnly: OK
Access_token_renovado_valido: OK
Cierre_sesion_Supabase: OK
Sesion_cerrada_no_se_renueva: OK
AUTH_PERSISTENCIA_AISLAMIENTO: COMPROBADOS
```

Limitación del verificador: el paso posterior que intentaba cerrar las páginas de
React terminó con `VERIFICACION_MANUAL_NO_COMPLETADA`, después de aprobar todos
los pasos anteriores. El mensaje original no conservó la causa concreta. Se
añadió diagnóstico de fase y se ajustó la espera para tolerar páginas ya devueltas
al login. El cierre de sesión de React pasó en una prueba aislada con respuestas
simuladas; no se repitió toda la secuencia manual tras ese ajuste. La revocación
y el rechazo de renovación sí se comprobaron contra Supabase real.

### Validación automatizada actual

Las dos pruebas PostgreSQL omitidas en la etapa anterior ahora pasaron: reinicio
entre procesos y flujo completo con solicitudes, valores, predicción, informe,
versiones y rechazo de una edición obsoleta. Para ese flujo se usaron catálogos
sintéticos dentro de rollback; no se presentaron como normativa municipal oficial.
No se dejaron áreas, plantillas o normativas ficticias permanentes en la base.

Salida real final de pytest:

```text
SKIPPED [1] tests\test_auth_integration.py:6: Auth real: requiere .env.local y .env.auth-test
75 passed, 1 skipped, 1 warning in 67.09s (0:01:07)
```

La prueba omitida es la variante automatizada que lee passwords de `.env.auth-test`.
El usuario eligió login manual; se ejecutó el mismo verificador con sesiones
obtenidas del navegador por stdin, sin guardarlas en disco. La autenticación real
sí se comprobó fuera de pytest. La advertencia sigue siendo la de Starlette/httpx.

`npm.cmd run lint` y `npm.cmd run build` terminaron correctamente. Se corrigió un
fallo previo de ESLint: recorría entornos virtuales, y `NuevoInforme` referenciaba
la función de carga de catálogos antes de declararla. La carga quedó dentro del
efecto, con control de desmontaje y sin cambiar el contrato de los servicios.
No se añadieron dependencias Python o npm de producción en esta etapa.

### Conservación y configuración local

Comprobaciones finales reales:

```text
REGISTROS_ORIGINALES_14_TABLAS_INTACTOS: True
TRES_CUENTAS_Y_PASSWORDS_INTACTOS: True
POLITICAS_RLS: 14
TRIGGER_PERFILES: 1
SECRETOS_EN_ARCHIVOS_VERSIONABLES: False
SECRETOS_EN_FRONTEND_COMPILADO: False
ENV_NO_VERSIONADO: True
```

El usuario agregó personalmente URL y clave publicable a `.env` durante esta
etapa. El agente no sobrescribió ese archivo ni sus credenciales PostgreSQL;
por eso no se reutiliza la afirmación de la revisión anterior de que su hash
completo permanece idéntico. `.env.local` es opcional y también está soportado.
`.env.auth-test` no fue creado. No se hizo commit ni push.

Los catálogos institucionales de áreas, plantillas y normativas continúan pendientes
de carga. Las pruebas de solicitudes por API no los necesitan; el formulario de
generación existente sí exige área y plantilla para guardar sus datos completos.
No se declara lista la generación institucional de informes sin esos catálogos.

### Comandos de ejecución desde PowerShell

Desde la raíz, backend real:

```powershell
$env:NAXJI_PERSISTENCE_MODE = 'postgres'
$env:NAXJI_AUTH_MODE = 'supabase'
$env:NAXJI_AUTH_COOKIE_SECURE = 'false' # Solo desarrollo local por HTTP
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

En otra terminal, frontend:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Abrir `http://127.0.0.1:5173`. Usar el proxy `/api` mantiene las cookies en el mismo
sitio. En despliegue HTTPS usar cookie Secure=true y orígenes autorizados explícitos.
No iniciar procesos duplicados si esos puertos ya están ocupados por NAXJI.

Pruebas PostgreSQL y unitarias:

```powershell
$env:NAXJI_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q -rs -p no:cacheprovider
Remove-Item Env:\NAXJI_RUN_DB_TESTS
```

Verificación manual asistida, con ambos servidores encendidos y Playwright ya
disponible en el entorno aislado `venv/ui-check`:

```powershell
node .\scripts\verificar_auth_navegador.cjs
```

Verificación de seguridad sin confirmar cambios:

```powershell
.\.venv\Scripts\python.exe .\scripts\aplicar_seguridad_supabase.py
```

La migración ya está aplicada; no es necesario volver a pasar `--apply`.


### Archivos de esta etapa y diff

Rutas completas de los archivos creados o modificados en esta etapa:

- `C:\Users\DELL INSPIRON\Documents\NAXJI\.env.example`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\docs\VERIFICACION_SUPABASE.md`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\docs\evidencias\auth-manual-20260929.txt`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\eslint.config.js`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\migrations\20260928_01_auth_rls.sql`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\scripts\aplicar_seguridad_supabase.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\scripts\verificar_auth_navegador.cjs`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\scripts\verificar_auth_supabase.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\in\controllers\auth_controller.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\in\controllers\usuario_controller.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\in\web\components\Header.jsx`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\in\web\components\ProtectedRoute.jsx`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\in\web\pages\Login.jsx`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\in\web\pages\NuevoInforme.jsx`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\in\web\services\api.js`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\in\web\services\authService.js`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\in\web\services\session.js`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\adapters\out\persistence\perfil_repository_postgres.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\application\ports\output\perfil_repository.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\domain\entities\usuario_actual.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\infrastructure\auth\supabase.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\infrastructure\configuration\container.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\infrastructure\configuration\database.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\infrastructure\configuration\settings.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\infrastructure\dependencies.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\src\main.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\tests\test_auth.py`
- `C:\Users\DELL INSPIRON\Documents\NAXJI\tests\test_auth_integration.py`

El diff respecto del inicio de esta etapa se conserva en `venv/run-logs/auth-cambios-20260929.patch`. Los cambios de la etapa PostgreSQL anterior permanecen conservados.

### Tabla final de esta etapa

| Componente | Estado anterior | Corrección realizada | Evidencia | Estado final |
| --- | --- | --- | --- | --- |
| Supabase Auth | Sin integración | Login/validación/renovación/logout mediante Auth REST | Login manual A y B, tokens inválidos 401 | Comprobado |
| Perfiles | No consultados en login | Consulta por UUID verificado; rechazo de perfil inactivo/ausente | Perfil real de A y B coincide con SQL; trigger probado con rollback | Comprobado |
| Roles | Identidades demo | Roles activos de PostgreSQL en cada petición | FUNCIONARIO real; autoasignación HTTP/SQL denegada | Comprobado |
| Autenticación React–FastAPI | Selector demo | Formulario real, token en memoria, cookie HttpOnly, gestión de sesión | Login manual y perfil reales; cierre UI aislado pasó | Comprobado; limitación final del verificador descrita |
| Autorización y RLS | BYPASSRLS sin políticas | Guardas de backend, 14 políticas y acceso directo limitado a lectura | B recibe 403; Data API con JWT de B devuelve 0 filas; SET ROLE sin bypass | Comprobado |
| Persistencia de solicitudes | Prueba bloqueada por ausencia de perfiles | Uso de perfiles existentes sin alterarlos | POST real, SQL concordante, GET/PUT de propietario | Comprobado |
| Recuperación después del reinicio | Omitida | Dos procesos uvicorn independientes | Segundo proceso recupera contenido y conserva aislamiento | Comprobado |
| Pruebas automatizadas | 60 aprobadas, 2 omitidas | Tests Auth, RLS y pruebas PostgreSQL desbloqueadas | 75 passed, 1 skipped; Auth real por login manual | Comprobado con omisión justificada |
