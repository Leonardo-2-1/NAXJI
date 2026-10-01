-- PROPUESTA PARA REVISIÓN. No ejecutada en Supabase.
-- Requiere 20261001_01_correspondencias_normativas.sql. Curación al 2026-10-01.
-- Referencias NACIONALES relacionadas con residuos; NO ordenanzas de El Tambo.
-- Identidad/publicación: MINAM y reproducción de El Peruano; estado: SINIA.
-- La asociación es temática y revisable, NO aplicación jurídica automática.
-- SINIA muestra 31/12/2017 para el DS; el PDF original dice 21/12/2017 y prevalece.
-- No se importan artículos ni textos jurídicos al generador (sin RAG).
BEGIN;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(20261001, 1);

DO $$
DECLARE doc record; existente public.normativas%ROWTYPE;
BEGIN
    FOR doc IN SELECT * FROM (VALUES
      ('PE_DL_1278', 'Decreto Legislativo N.º 1278 — Ley de Gestión Integral de Residuos Sólidos',
       '1278', DATE '2016-12-23',
       'https://sinia.minam.gob.pe/normas/ley-gestion-integral-residuos-solidos',
       'https://sinia.minam.gob.pe/normas/ley-gestion-integral-residuos-solidos',
       'Perú. Gestión y manejo de residuos, incluidos residuos municipales; no es una ordenanza local.',
       'Referencia nacional para el tema residuos. SINIA la clasifica vigente e identifica modificaciones por DL 1501 y Ley 32212. Revisar texto actualizado y aplicabilidad al caso; no se valida contenido jurídico.'),
      ('PE_DS_014_2017_MINAM', 'Decreto Supremo N.º 014-2017-MINAM — Reglamento del Decreto Legislativo N.º 1278',
       '014-2017-MINAM', DATE '2017-12-21',
       'https://www.minam.gob.pe/wp-content/uploads/2018/06/ds_014-2017-minam_-RRSS.pdf',
       'https://sinia.minam.gob.pe/normas/aprueban-reglamento-decreto-legislativo-ndeg-1278-decreto-legislativo',
       'Perú. Reglamento nacional de gestión y manejo de residuos y servicios de limpieza pública; no es una ordenanza local.',
       'Referencia reglamentaria para el tema residuos. SINIA la clasifica vigente; existe modificación por DS 001-2022-MINAM. La publicación original es de 21/12/2017, distinta de la fecha de ficha SINIA. Revisar modificaciones y aplicabilidad; no se valida contenido jurídico.')
    ) AS docs(codigo,titulo,numero,publicacion,fuente,fuente_vigencia,ambito,justificacion)
    LOOP
        INSERT INTO public.normativas(codigo,titulo,tipo,numero,fecha_publicacion,url_fuente,descripcion)
        VALUES (doc.codigo,doc.titulo,'DECRETO',doc.numero,doc.publicacion,doc.fuente,doc.justificacion)
        ON CONFLICT (codigo) WHERE codigo IS NOT NULL DO NOTHING;
        SELECT * INTO STRICT existente FROM public.normativas WHERE codigo=doc.codigo;
        -- No sobrescribir identidades, bajas ni curación previa: detener ante conflicto.
        IF ROW(existente.titulo,existente.tipo,existente.numero,existente.fecha_publicacion,
               existente.url_fuente,existente.activo,existente.fecha_inicio_vigencia,existente.fecha_fin_vigencia)
           IS DISTINCT FROM ROW(doc.titulo,'DECRETO'::varchar,doc.numero,doc.publicacion,
                                doc.fuente,true,NULL::date,NULL::date) THEN
            RAISE EXCEPTION 'Conflicto de catálogo en %. Revisar manualmente; no se sobrescribió.', doc.codigo;
        END IF;
        INSERT INTO public.normativa_correspondencias(etiqueta,normativa_id,estado_verificacion,
            fuente_url,fuente_vigencia_url,verificado_en,ambito,vigencia,justificacion)
        VALUES ('NORM_RESIDUOS',existente.id,'VERIFICADA',doc.fuente,doc.fuente_vigencia,
                DATE '2026-10-01',doc.ambito,'VIGENTE_CON_MODIFICACIONES',doc.justificacion)
        ON CONFLICT (etiqueta,normativa_id) DO NOTHING;
        -- No reactivar ni reemplazar una relación que un curador haya cambiado.
    END LOOP;
END $$;
COMMIT;
