-- Paso 3: cambio aditivo. NULL conserva el contrato de tres secciones anterior.
-- Ejecutar antes de desplegar el backend; no modifica contenido ni registros.
BEGIN;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(20260930, 1);

CREATE OR REPLACE FUNCTION public.naxji_secciones_salida_validas(valor jsonb)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path = pg_catalog AS $$
DECLARE seccion jsonb; claves text[] := ARRAY[]::text[]; clave text;
BEGIN
  IF valor IS NULL THEN RETURN true; END IF;
  IF jsonb_typeof(valor) <> 'array' THEN RETURN false; END IF;
  IF jsonb_array_length(valor) NOT BETWEEN 1 AND 100 THEN RETURN false; END IF;
  FOR seccion IN SELECT * FROM jsonb_array_elements(valor) LOOP
    IF jsonb_typeof(seccion) <> 'object' THEN RETURN false; END IF;
    IF NOT (seccion ?& ARRAY['clave','titulo','obligatoria'])
       OR (seccion - ARRAY['clave','titulo','obligatoria']) <> '{}'::jsonb THEN RETURN false; END IF;
    IF jsonb_typeof(seccion->'clave') <> 'string'
       OR jsonb_typeof(seccion->'titulo') <> 'string'
       OR jsonb_typeof(seccion->'obligatoria') <> 'boolean' THEN RETURN false; END IF;
    clave := seccion->>'clave';
    IF clave !~ '^[a-z][a-z0-9_]{0,79}$'
       OR clave = ANY(ARRAY['encabezado','datos','contexto','plantilla','instrucciones'])
       OR clave = ANY(claves)
       OR length(btrim(seccion->>'titulo')) = 0
       OR length(seccion->>'titulo') > 150 THEN RETURN false; END IF;
    claves := array_append(claves, clave);
  END LOOP;
  RETURN true;
END $$;

ALTER TABLE public.plantillas ADD COLUMN IF NOT EXISTS secciones_salida jsonb;
ALTER TABLE public.versiones_informe ADD COLUMN IF NOT EXISTS secciones_salida jsonb;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.plantillas'::regclass
                 AND conname='chk_plantilla_secciones_salida') THEN
    ALTER TABLE public.plantillas ADD CONSTRAINT chk_plantilla_secciones_salida
      CHECK (public.naxji_secciones_salida_validas(secciones_salida)) NOT VALID;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.versiones_informe'::regclass
                 AND conname='chk_version_secciones_salida') THEN
    ALTER TABLE public.versiones_informe ADD CONSTRAINT chk_version_secciones_salida
      CHECK (public.naxji_secciones_salida_validas(secciones_salida)) NOT VALID;
  END IF;
END $$;
ALTER TABLE public.plantillas VALIDATE CONSTRAINT chk_plantilla_secciones_salida;
ALTER TABLE public.versiones_informe VALIDATE CONSTRAINT chk_version_secciones_salida;
COMMENT ON COLUMN public.plantillas.secciones_salida IS
  'Secciones ordenadas del documento, distintas de campos_plantilla. NULL = contrato anterior.';
COMMENT ON COLUMN public.versiones_informe.secciones_salida IS
  'Copia de la estructura al generar; no depende de cambios posteriores de plantilla. NULL = versión anterior.';
COMMIT;
