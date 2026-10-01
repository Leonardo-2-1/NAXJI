-- PENDIENTE DE REVISIÓN. Ejecutar manualmente, nunca al arrancar la aplicación.
-- Versión nueva: no modifica v1, sus campos, solicitudes, informes ni versiones.
-- Requiere pmv1_catalogos.sql y la migración 20260930_01_secciones_salida.sql.
BEGIN;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(20261001, 2);
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.plantillas p JOIN public.tipos_informe t
    ON t.id=p.tipo_informe_id WHERE p.nombre='Informe Técnico – Piloto NAXJI'
    AND p.version=1 AND t.codigo='INFORME_TECNICO' AND t.activo) THEN
    RAISE EXCEPTION 'Falta la plantilla piloto v1 o su tipo activo; no se insertaron registros';
  END IF;
END $$;

INSERT INTO public.plantillas(nombre,tipo_informe_id,version,descripcion,secciones_salida)
SELECT 'Informe Técnico – Piloto NAXJI', id, 2,
  'DEMOSTRACIÓN v2 con datos fuente. No constituye un formato oficial municipal. No requiere redactar las secciones de salida. Los hechos faltantes quedan pendientes de verificación. Revisión humana obligatoria.',
  '[{"clave":"antecedentes","titulo":"Antecedentes","obligatoria":true},
    {"clave":"objetivo","titulo":"Objetivo del informe","obligatoria":true},
    {"clave":"analisis_tecnico","titulo":"Análisis técnico","obligatoria":true},
    {"clave":"conclusiones","titulo":"Conclusiones","obligatoria":true},
    {"clave":"recomendaciones","titulo":"Recomendaciones","obligatoria":false}]'::jsonb
FROM public.tipos_informe WHERE codigo='INFORME_TECNICO' AND activo
ON CONFLICT(nombre,version) DO NOTHING;

-- Si alguien ya usa el número de versión con otra definición, detenerse sin pisarla.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.plantillas p JOIN public.tipos_informe t ON t.id=p.tipo_informe_id
    WHERE p.nombre='Informe Técnico – Piloto NAXJI' AND p.version=2 AND t.codigo='INFORME_TECNICO'
    AND p.descripcion LIKE 'DEMOSTRACIÓN v2 con datos fuente.%'
    AND p.area_id IS NULL AND p.secciones_salida =
    '[{"clave":"antecedentes","titulo":"Antecedentes","obligatoria":true},
      {"clave":"objetivo","titulo":"Objetivo del informe","obligatoria":true},
      {"clave":"analisis_tecnico","titulo":"Análisis técnico","obligatoria":true},
      {"clave":"conclusiones","titulo":"Conclusiones","obligatoria":true},
      {"clave":"recomendaciones","titulo":"Recomendaciones","obligatoria":false}]'::jsonb) THEN
    RAISE EXCEPTION 'La versión 2 existente tiene otra definición; revisar manualmente';
  END IF;
END $$;

-- Tabla temporal solo para comparar la definición esperada; no altera el esquema público.
CREATE TEMP TABLE naxji_fuentes_v2 ON COMMIT DROP AS
SELECT * FROM (VALUES
  ('estado_resultados','Información disponible','select',true,1,
   '{"opciones":["Sin resultados de inspección","Información parcial por verificar","Resultados documentados disponibles"],"ayuda":"Indique si existen resultados. Elegir una opción no acredita hechos ni sustituye sus fuentes."}'::jsonb),
  ('lugar_referencia','Lugar de referencia conocido','text',false,2,
   '{"ayuda":"Opcional. Identifique el lugar solo si lo conoce; no implica que haya sido inspeccionado."}'::jsonb),
  ('fecha_referencia','Fecha de referencia conocida','date',false,3,
   '{"ayuda":"Opcional. Fecha del hecho o documento aportado; no supone una inspección realizada."}'::jsonb),
  ('hechos_conocidos','Hechos y resultados conocidos','textarea',false,4,
   '{"rol_fuente":"hechos","ayuda":"Opcional. Describa solo hechos aportados, su origen y qué falta comprobar. Si no hay resultados, déjelo vacío o indíquelo expresamente."}'::jsonb),
  ('referencias_conocidas','Documentos y referencias conocidos','textarea',false,5,
   '{"rol_fuente":"referencias","ayuda":"Opcional. Identifique documentos, enlaces o extractos disponibles. Un número o enlace no acredita su contenido, vigencia ni aplicabilidad."}'::jsonb),
  ('informacion_pendiente','Información pendiente de obtener o verificar','textarea',false,6,
   '{"ayuda":"Opcional. Señale datos faltantes. No necesita redactar antecedentes, análisis ni conclusiones."}'::jsonb)
) AS v(clave,etiqueta,tipo_dato,obligatorio,orden,configuracion);

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM public.campos_plantilla c
    JOIN public.plantillas p ON p.id=c.plantilla_id
    LEFT JOIN naxji_fuentes_v2 v ON v.clave=c.clave
    WHERE p.nombre='Informe Técnico – Piloto NAXJI' AND p.version=2
    AND (v.clave IS NULL OR (c.etiqueta,c.tipo_dato,c.obligatorio,c.orden,c.configuracion,c.activo)
      IS DISTINCT FROM (v.etiqueta,v.tipo_dato,v.obligatorio,v.orden,v.configuracion,true))) THEN
    RAISE EXCEPTION 'Los campos de v2 existentes difieren; no se alteraron registros';
  END IF;
END $$;

INSERT INTO public.campos_plantilla(plantilla_id,clave,etiqueta,tipo_dato,obligatorio,orden,configuracion)
SELECT p.id,v.clave,v.etiqueta,v.tipo_dato,v.obligatorio,v.orden,v.configuracion
FROM naxji_fuentes_v2 v CROSS JOIN public.plantillas p
WHERE p.nombre='Informe Técnico – Piloto NAXJI' AND p.version=2
ON CONFLICT(plantilla_id,clave) DO NOTHING;
COMMIT;
