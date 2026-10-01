# Autenticación del despliegue temporal Pages + Railway

El frontend `https://naxji.pages.dev` y el backend
`https://naxji-production.up.railway.app` están en sitios distintos. Para este
despliegue temporal, `naxji_refresh` usa `SameSite=None; Secure; HttpOnly`.
No se publica el refresh token en JSON ni se guarda en el almacenamiento de React.

La cookie pertenece exclusivamente al host del backend (sin `Domain`) y tiene
`Path=/`. Login y renovación la crean con una duración de 30 días. Logout y los
errores 401/403 al renovar la eliminan con los mismos atributos, `Max-Age=0` y
fecha de expiración pasada. `NAXJI_AUTH_COOKIE_SECURE=false` se rechaza al cargar
la configuración: no se permite una cookie `SameSite=None` sin `Secure`.

## Variables del despliegue

En Railway, conservar las credenciales privadas existentes y configurar:

```dotenv
NAXJI_PERSISTENCE_MODE=postgres
NAXJI_AUTH_MODE=supabase
NAXJI_AUTH_COOKIE_SECURE=true
NAXJI_AUTH_ALLOWED_ORIGINS=https://naxji.pages.dev
NAXJI_CORS_ORIGINS=https://naxji.pages.dev
```

En el entorno de compilación de Cloudflare Pages:

```dotenv
VITE_API_URL=https://naxji-production.up.railway.app
```

La URL no lleva `/api`: ese prefijo se usa en el proxy de desarrollo de Vite.
Después de cambiar las variables, desplegar nuevamente los servicios afectados.
Este cambio de código no configura automáticamente las variables de Railway o
Pages y no modifica los archivos privados `.env` locales.

## Controles conservados

- `X-NAXJI-Client: web` es obligatorio en login, refresh y logout.
- `Origin` se valida contra la lista explícita permitida y el propio backend.
  Las solicitudes declaradas cross-site sin `Origin` se rechazan.
- CORS permite credenciales, únicamente los orígenes configurados, los métodos
  `GET`, `POST`, `PUT` y los headers `Authorization`, `Content-Type`,
  `X-NAXJI-Client`. No se permiten comodines en las listas de orígenes.
- React conserva `withCredentials: true`. El access token permanece en memoria.
- La validación de identidad en Supabase y de perfil/roles en PostgreSQL no cambia.

## Verificación

`tests/test_auth.py` simula exactamente los orígenes de Pages y Railway con
Supabase simulado; no necesita ni almacena contraseñas reales. Comprueba login,
renovación, logout, eliminación tras errores, atributos de cookie, preflight
autorizado, rechazo de otros orígenes/headers y rechazo de configuración insegura.

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs -p no:cacheprovider
npm.cmd run test:frontend
npm.cmd run lint
npm.cmd run build
```

Las pruebas opt-in de Supabase, Ollama y PostgreSQL aislado requieren sus servicios
y variables de activación. Un resultado omitido no acredita esa integración.
Los verificadores antiguos que fuerzan `NAXJI_AUTH_COOKIE_SECURE=false` sobre HTTP
no verifican este despliegue; para probar sesiones reales hay que usar HTTPS y
mantener `Secure=true`.

En el navegador, ingresar manualmente desde Pages y verificar en Network que
login y refresh reciben la cookie segura, recargar y comprobar la recuperación
de sesión, y cerrar sesión comprobando que desaparece la cookie. Revisar el
preflight y el origen permitido, sin copiar contraseñas ni tokens a evidencias.
Las pruebas HTTP simuladas no demuestran que un navegador acepte cookies de
terceros: sus políticas pueden bloquearlas aun con estos atributos. Cuando se
unifiquen los sitios mediante un dominio propio, revisar esta decisión temporal
y adoptar una política más restrictiva que sea compatible con el despliegue.

Referencias: [Set-Cookie (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie),
[cookies de terceros (MDN)](https://developer.mozilla.org/en-US/docs/Web/Privacy/Guides/Third-party_cookies),
[CORS en Starlette](https://starlette.dev/middleware/#corsmiddleware).

## Resultados ejecutados el 2026-10-01

| Comprobación | Resultado real |
| --- | --- |
| Suite Python completa, `pytest -q -rs -p no:cacheprovider --basetemp <directorio nuevo en venv>` | `215 passed, 65 skipped, 1 warning in 11.23s` |
| Suite React, `npm.cmd run test:frontend` | `tests 51`, `pass 51`, `fail 0`, `skipped 0` |
| `npm.cmd run lint` | Código de salida 0 |
| `npm.cmd run build` | Código de salida 0; 105 módulos transformados |
| `python -m pip check` en `.venv` | `No broken requirements found.` |
| Sintaxis de los cinco archivos Python modificados | Correcta |
| `git diff --check` | Sin errores |
| Preflight público Railway desde `https://naxji.pages.dev` | HTTP 200, `Access-Control-Allow-Origin: https://naxji.pages.dev`, credenciales permitidas |
| Preflight público Railway desde `https://attacker.invalid` | HTTP 400, sin `Access-Control-Allow-Origin` |

El primer intento de pytest obtuvo 214 aprobadas y un error de preparación por
`PermissionError: [WinError 5]` en el directorio temporal de Windows. Se repitió
toda la suite fuera del entorno restringido, con un directorio temporal nuevo,
obteniendo el resultado sin errores de la tabla. La advertencia restante procede
del uso de httpx en TestClient de Starlette; no es un fallo de prueba.

Las 65 pruebas omitidas son opt-in de Supabase/Auth real, PostgreSQL aislado y
Ollama. No se activaron servicios ni se solicitaron contraseñas para este cambio.
La suite React utiliza respuestas simuladas, aunque algunos nombres históricos
de sus pruebas digan «login real». Los preflight públicos se midieron antes de
publicar este cambio; no acreditan que las nuevas cookies ya estén desplegadas.
Queda por verificar el login y la renovación reales en el navegador tras el
despliegue. No se modificaron datos de Supabase ni credenciales privadas.
