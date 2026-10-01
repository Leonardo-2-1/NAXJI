-- PROPUESTA PARA REVISIÓN. No ejecutada en Supabase.
-- Aditiva: no modifica normativas ni predicciones/informes existentes.
BEGIN;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(20261001, 1);

CREATE TABLE IF NOT EXISTS public.normativa_correspondencias (
    etiqueta varchar(100) NOT NULL,
    normativa_id uuid NOT NULL REFERENCES public.normativas(id) ON DELETE RESTRICT,
    estado_verificacion varchar(20) NOT NULL DEFAULT 'PENDIENTE',
    fuente_url text,
    fuente_vigencia_url text,
    verificado_en date,
    ambito text,
    vigencia varchar(40) NOT NULL DEFAULT 'PENDIENTE',
    justificacion text,
    activa boolean NOT NULL DEFAULT true,
    PRIMARY KEY (etiqueta, normativa_id),
    CONSTRAINT chk_correspondencia_etiqueta CHECK (etiqueta ~ '^[A-Z][A-Z0-9_]{0,99}$'),
    CONSTRAINT chk_correspondencia_estado CHECK (estado_verificacion IN ('PENDIENTE','VERIFICADA','DESCARTADA')),
    CONSTRAINT chk_correspondencia_vigencia CHECK (vigencia IN ('PENDIENTE','VIGENTE','VIGENTE_CON_MODIFICACIONES','NO_VIGENTE')),
    CONSTRAINT chk_correspondencia_evidencia CHECK (
        estado_verificacion <> 'VERIFICADA' OR (
            fuente_url IS NOT NULL AND fuente_url ~ '^https://'
            AND fuente_vigencia_url IS NOT NULL AND fuente_vigencia_url ~ '^https://'
            AND verificado_en IS NOT NULL
            AND ambito IS NOT NULL AND length(btrim(ambito)) > 0
            AND justificacion IS NOT NULL AND length(btrim(justificacion)) > 0
            AND vigencia IN ('VIGENTE','VIGENTE_CON_MODIFICACIONES')
        )
    )
);
CREATE INDEX IF NOT EXISTS idx_correspondencia_normativa ON public.normativa_correspondencias(normativa_id);
ALTER TABLE public.normativa_correspondencias ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.normativa_correspondencias FROM PUBLIC;
-- Curación mediante SQL revisado, no editable desde clientes anónimos/autenticados.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
        REVOKE ALL ON public.normativa_correspondencias FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
        REVOKE ALL ON public.normativa_correspondencias FROM authenticated;
    END IF;
END $$;
COMMENT ON TABLE public.normativa_correspondencias IS
    'Correspondencias temáticas curadas. VERIFICADA acredita revisión documental fechada, no aplicabilidad al expediente ni contenido jurídico validado por el LLM.';
COMMIT;
