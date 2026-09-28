# Comprobaciones de Supabase

Ejecutar desde la raiz del proyecto, con la conexion configurada en `.env`.
El entorno local `venv/db-check` utiliza `requirements-db.txt` y no necesita
FastAPI ni los modelos de IA. `.env` y `venv/` estan excluidos de Git.

## Conexion y lectura del esquema

```powershell
.\venv\db-check\Scripts\python.exe scripts\verificar_supabase.py
```

Comprueba autenticacion, SSL y visibilidad de las tablas esperadas mediante
una transaccion de solo lectura. No consulta datos personales.

## CRUD directo en PostgreSQL

```powershell
.\venv\db-check\Scripts\python.exe scripts\verificar_supabase.py --crud
```

Primero realiza la comprobacion anterior. Despues crea una fila ficticia con
UUID y codigo unicos en `public.areas_municipales`, la consulta, la actualiza,
la elimina y comprueba cada resultado. Todas las escrituras se ejecutan dentro
de una transaccion con rollback obligatorio, incluso si ocurre un error.

Para verificar el rollback, repone la misma fila ficticia antes de revertir
la transaccion y confirma que no queda guardada. El resultado debe incluir:

```json
{
  "status": "ok",
  "crud": {"create": "ok", "read": "ok", "update": "ok", "delete": "ok"},
  "rollback": "ok",
  "remaining_test_rows": 0
}
```

No modifica filas preexistentes. Se detiene si detecta triggers activos o
reglas personalizadas en la tabla que requieran revisar posibles efectos externos.
La fila de prueba no permanece visible en el panel de Supabase.

Esta prueba valida operaciones SQL desde Python con el usuario de `.env`.
Con el usuario `postgres` no demuestra los permisos RLS de un funcionario.
Tampoco verifica los endpoints de FastAPI: actualmente sus repositorios siguen
usando memoria y no existe un endpoint HTTP DELETE. La cancelacion de una
solicitud es un cambio de estado, no una eliminacion.
