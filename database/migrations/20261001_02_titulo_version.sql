-- PENDIENTE DE REVISIÓN. Aditiva e idempotente; no reconstruye títulos históricos.
-- NULL identifica versiones cuyo título no estaba versionado. No modifica filas.
BEGIN;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(20261001, 2);
ALTER TABLE public.versiones_informe ADD COLUMN IF NOT EXISTS titulo text;
COMMENT ON COLUMN public.versiones_informe.titulo IS
  'Título guardado con la versión. NULL = dato histórico no versionado; usar el título actual del informe con aviso.';
COMMIT;
