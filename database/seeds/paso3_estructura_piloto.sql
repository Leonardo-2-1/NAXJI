-- Solo la plantilla piloto ya existente. No define formatos institucionales.
-- Prerrequisitos: migración 20260930_01 y seed pmv1_catalogos.sql.
BEGIN;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(20260930, 1);
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.plantillas p JOIN public.tipos_informe t ON t.id=p.tipo_informe_id
                 WHERE p.nombre='Informe Técnico – Piloto NAXJI' AND p.version=1 AND t.codigo='INFORME_TECNICO') THEN
    RAISE EXCEPTION 'Falta la plantilla técnica piloto PMV1; no se modificaron registros';
  END IF;
END $$;
UPDATE public.plantillas p
SET secciones_salida = '[
  {"clave":"antecedentes","titulo":"Antecedentes","obligatoria":true},
  {"clave":"objetivo","titulo":"Objetivo del informe","obligatoria":true},
  {"clave":"analisis_tecnico","titulo":"Análisis técnico","obligatoria":true},
  {"clave":"conclusiones","titulo":"Conclusiones","obligatoria":true},
  {"clave":"recomendaciones","titulo":"Recomendaciones","obligatoria":false}
]'::jsonb
FROM public.tipos_informe t
WHERE p.tipo_informe_id=t.id AND t.codigo='INFORME_TECNICO'
  AND p.nombre='Informe Técnico – Piloto NAXJI' AND p.version=1
  AND p.secciones_salida IS NULL;
-- El nombre y la descripción DEMOSTRACIÓN PMV1 del seed original se conservan.
COMMIT;
