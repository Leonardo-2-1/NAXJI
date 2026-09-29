-- NAXJI PMV1. Solo inserciones; no modifica registros existentes.
-- Fuente: ROF 2020 publicado actualmente por MDT, art. 6 (pp. 7-8), organigrama p. 67.
-- https://cdn.www.gob.pe/uploads/document/file/4258543/MDT_ROF_2020.pdf.pdf
-- Índice vigente consultado 2026-09-29:
-- https://transparencia.gob.pe/enlaces/pte_transparencia_enlaces.aspx?id_entidad=11090&id_tema=5&ver=
-- Los códigos MDT_* son identificadores de NAXJI, no códigos oficiales del ROF.
-- BEGIN/COMMIT pertenecen al archivo para ejecución SQL independiente.
BEGIN;
SELECT pg_advisory_xact_lock(20260929, 1);
DO $$ BEGIN
  IF (SELECT count(*) FROM public.tipos_informe WHERE activo AND codigo IN
      ('INFORME_TECNICO','INFORME_LEGAL','INFORME_INSPECCION','MEMORANDO')) <> 4 THEN
    RAISE EXCEPTION 'Se requieren los cuatro tipos PMV1 activos; no se alteraron registros';
  END IF;
END $$;

INSERT INTO public.areas_municipales(codigo,nombre,descripcion)
VALUES ('MDT_CONCEJO','Concejo Municipal','ROF 2020, art. 6 y p. 67. Fuente oficial: https://cdn.www.gob.pe/uploads/document/file/4258543/MDT_ROF_2020.pdf.pdf ; consulta 2026-09-29. Catálogo parcial.')
ON CONFLICT(codigo) DO NOTHING;
INSERT INTO public.areas_municipales(codigo,nombre,area_padre_id,descripcion)
SELECT 'MDT_ALCALDIA','Alcaldía',id,'ROF 2020, pp. 7 y 67; fuente y fecha de consulta en database/seeds/pmv1_catalogos.sql.'
FROM public.areas_municipales WHERE codigo='MDT_CONCEJO'
ON CONFLICT(codigo) DO NOTHING;
INSERT INTO public.areas_municipales(codigo,nombre,area_padre_id,descripcion)
SELECT 'MDT_GM','Gerencia Municipal',id,'ROF 2020, pp. 7 y 67; fuente y fecha de consulta en database/seeds/pmv1_catalogos.sql.'
FROM public.areas_municipales WHERE codigo='MDT_ALCALDIA'
ON CONFLICT(codigo) DO NOTHING;
INSERT INTO public.areas_municipales(codigo,nombre,area_padre_id,descripcion)
SELECT v.codigo,v.nombre,p.id,'ROF 2020, pp. 7-8 y 67; fuente y fecha de consulta en database/seeds/pmv1_catalogos.sql.'
FROM (VALUES
 ('MDT_GSP','Gerencia de Servicios Públicos'),
 ('MDT_GDT','Gerencia de Desarrollo Territorial'),
 ('MDT_GDE','Gerencia de Desarrollo Económico'),
 ('MDT_GAJ','Gerencia de Asesoría Jurídica')
) AS v(codigo,nombre)
JOIN public.areas_municipales p ON p.codigo='MDT_GM'
ON CONFLICT(codigo) DO NOTHING;
INSERT INTO public.areas_municipales(codigo,nombre,area_padre_id,descripcion)
SELECT v.codigo,v.nombre,p.id,'ROF 2020, pp. 8 y 67; fuente y fecha de consulta en database/seeds/pmv1_catalogos.sql.'
FROM (VALUES
 ('MDT_SGGA','Subgerencia de Gestión Ambiental','MDT_GSP'),
 ('MDT_SGDUR','Subgerencia de Desarrollo Urbano y Rural','MDT_GDT')
) AS v(codigo,nombre,padre)
JOIN public.areas_municipales p ON p.codigo=v.padre
ON CONFLICT(codigo) DO NOTHING;

INSERT INTO public.normativas(codigo,titulo,tipo,numero,fecha_publicacion,
 fecha_inicio_vigencia,fecha_fin_vigencia,url_fuente,descripcion,activo)
VALUES ('MDT_ROF_2020','Reglamento de Organización y Funciones de la Municipalidad Distrital de El Tambo – ROF 2020',
 'REGLAMENTO',NULL,NULL,NULL,NULL,
 'https://cdn.www.gob.pe/uploads/document/file/4258543/MDT_ROF_2020.pdf.pdf',
 'Documento oficial publicado y enlazado por MDT y Transparencia al 2026-09-29. Fechas jurídicas no verificadas: NULL no acredita vigencia. Activo significa disponible en el catálogo documental. No se equipara a etiquetas normativas del modelo IA.',true)
ON CONFLICT(codigo) WHERE codigo IS NOT NULL DO NOTHING;

INSERT INTO public.plantillas(nombre,tipo_informe_id,version,descripcion)
SELECT 'Informe Técnico – Piloto NAXJI',id,1,
 'DEMOSTRACIÓN PMV1. No constituye formato oficial aprobado por MDT. Asunto y áreas se obtienen de la solicitud; autor del perfil autenticado. Revisión humana obligatoria.'
FROM public.tipos_informe WHERE codigo='INFORME_TECNICO' AND activo
ON CONFLICT(nombre,version) DO NOTHING;

INSERT INTO public.campos_plantilla(plantilla_id,clave,etiqueta,tipo_dato,obligatorio,orden,configuracion)
SELECT p.id,v.clave,v.etiqueta,v.tipo,v.obligatorio,v.orden,'{}'::jsonb
FROM (VALUES
 ('referencia_documento','Número o referencia del documento','text',false,1),
 ('fecha','Fecha','date',true,2),
 ('antecedentes','Antecedentes','textarea',true,3),
 ('objetivo','Objetivo del informe','textarea',true,4),
 ('detalle','Análisis técnico','textarea',true,5),
 ('conclusiones','Conclusiones','textarea',true,6),
 ('recomendaciones','Recomendaciones','textarea',true,7)
) AS v(clave,etiqueta,tipo,obligatorio,orden)
JOIN public.plantillas p ON p.nombre='Informe Técnico – Piloto NAXJI' AND p.version=1
ON CONFLICT(plantilla_id,clave) DO NOTHING;
COMMIT;
