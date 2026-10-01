-- Solo lectura. Para revisión/ejecución manual después de aplicar la semilla.
BEGIN READ ONLY;

SELECT p.id AS plantilla_id, p.nombre, p.version, p.activa,
       t.codigo AS tipo_codigo, t.id AS tipo_id, a.codigo AS area_codigo, a.id AS area_id,
       (SELECT count(*) FROM public.campos_plantilla c WHERE c.plantilla_id=p.id AND c.activo) AS campos_activos,
       jsonb_array_length(p.secciones_salida) AS secciones_salida
FROM public.plantillas p JOIN public.tipos_informe t ON t.id=p.tipo_informe_id
LEFT JOIN public.areas_municipales a ON a.id=p.area_id
WHERE p.nombre IN ('Informe Técnico – Piloto NAXJI','Informe de Inspección – Piloto NAXJI')
ORDER BY p.nombre,p.version;

SELECT c.clave,c.etiqueta,c.tipo_dato,c.obligatorio,c.orden,c.configuracion
FROM public.campos_plantilla c JOIN public.plantillas p ON p.id=c.plantilla_id
WHERE p.nombre='Informe de Inspección – Piloto NAXJI' AND p.version=1
ORDER BY c.orden;

SELECT s.orden,s.seccion->>'clave' AS clave,s.seccion->>'titulo' AS titulo,
       (s.seccion->>'obligatoria')::boolean AS obligatoria
FROM public.plantillas p CROSS JOIN LATERAL jsonb_array_elements(p.secciones_salida)
     WITH ORDINALITY AS s(seccion,orden)
WHERE p.nombre='Informe de Inspección – Piloto NAXJI' AND p.version=1 ORDER BY s.orden;

-- Esta consulta usa exactamente la compatibilidad del frontend.
SELECT t.codigo,t.id AS tipo_id,a.codigo AS area_codigo,a.id AS area_id,
       count(p.id) AS plantillas_compatibles
FROM public.tipos_informe t CROSS JOIN public.areas_municipales a
LEFT JOIN public.plantillas p ON p.tipo_informe_id=t.id AND p.activa
       AND (p.area_id IS NULL OR p.area_id=a.id)
WHERE t.activo AND a.activo AND a.codigo='MDT_SGGA'
GROUP BY t.codigo,t.id,a.codigo,a.id ORDER BY t.codigo;

-- Prerrequisito de la exportación con título por versión; no aplica migraciones.
SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
               AND table_name='versiones_informe' AND column_name='titulo') AS titulo_version_disponible;
COMMIT;
