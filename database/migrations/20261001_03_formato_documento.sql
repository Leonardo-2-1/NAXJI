-- PARA REVISIÓN. Aditiva; no aplica formatos a plantillas o documentos existentes.
-- Ejecutar el bloque completo. No depende de objetos temporales entre sesiones.
DO $formato$
BEGIN
  PERFORM set_config('lock_timeout', '5s', true);
  PERFORM pg_advisory_xact_lock(20261001, 4);
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
      AND table_name='plantillas' AND column_name='formato_documento'
      AND (data_type <> 'text' OR is_nullable <> 'YES' OR column_default IS NOT NULL)) THEN
    RAISE EXCEPTION 'formato_documento existente tiene otra definición; revisar sin sobrescribir';
  END IF;
  ALTER TABLE public.plantillas ADD COLUMN IF NOT EXISTS formato_documento text;
  IF EXISTS (SELECT 1 FROM public.plantillas WHERE formato_documento IS NOT NULL
             AND formato_documento <> 'mdt_informe_anexo08_2019_revision1') THEN
    RAISE EXCEPTION 'Hay formatos desconocidos; revisar sin sobrescribir';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.plantillas'::regclass
                 AND conname='plantillas_formato_documento_check') THEN
    ALTER TABLE public.plantillas ADD CONSTRAINT plantillas_formato_documento_check
      CHECK (formato_documento IS NULL OR formato_documento='mdt_informe_anexo08_2019_revision1');
  END IF;
END
$formato$;
