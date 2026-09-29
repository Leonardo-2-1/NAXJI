-- PMV1: ejecutar dentro de una transacción. No modifica registros existentes.
-- Las escrituras del flujo se realizan exclusivamente a través de FastAPI.
-- authenticated tiene SELECT sujeto a RLS; anon no tiene acceso a estas tablas.
-- PostgreSQL del backend conserva su autorización propia (rol BYPASSRLS).

CREATE SCHEMA IF NOT EXISTS naxji_private;
REVOKE ALL ON SCHEMA naxji_private FROM PUBLIC, anon;
GRANT USAGE ON SCHEMA naxji_private TO authenticated;

CREATE OR REPLACE FUNCTION naxji_private.has_role(allowed_codes text[])
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.perfiles p
        JOIN public.usuario_roles ur ON ur.usuario_id = p.id
        JOIN public.roles r ON r.id = ur.rol_id
        WHERE p.id = (SELECT auth.uid()) AND p.activo AND r.activo
          AND r.codigo = ANY(allowed_codes)
    );
$$;
REVOKE ALL ON FUNCTION naxji_private.has_role(text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION naxji_private.has_role(text[]) TO authenticated;

CREATE OR REPLACE FUNCTION naxji_private.can_read()
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT naxji_private.has_role(ARRAY['ADMINISTRADOR','FUNCIONARIO','REVISOR','APROBADOR']);
$$;
REVOKE ALL ON FUNCTION naxji_private.can_read() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION naxji_private.can_read() TO authenticated;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'areas_municipales','tipos_informe','normativas','roles','perfiles','usuario_roles',
        'plantillas','campos_plantilla','solicitudes','solicitud_valores','predicciones_ia',
        'prediccion_normativas','informes','versiones_informe'
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM pg_policies p WHERE p.schemaname='public' AND p.tablename=table_name
            AND p.policyname NOT LIKE 'naxji_%'
        ) THEN
            RAISE EXCEPTION 'Hay políticas ajenas a esta migración; revisar antes de continuar';
        END IF;
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated', table_name);
        EXECUTE format('GRANT SELECT ON TABLE public.%I TO authenticated', table_name);
    END LOOP;
END $$;

-- Solo se sustituyen políticas propiedad de esta migración.
DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['areas_municipales','tipos_informe','normativas','roles','campos_plantilla'] LOOP
        EXECUTE format('DROP POLICY IF EXISTS naxji_catalog_read ON public.%I', table_name);
        EXECUTE format('CREATE POLICY naxji_catalog_read ON public.%I FOR SELECT TO authenticated '
                       'USING (activo AND (SELECT naxji_private.can_read()))', table_name);
    END LOOP;
END $$;
DROP POLICY IF EXISTS naxji_catalog_read ON public.plantillas;
CREATE POLICY naxji_catalog_read ON public.plantillas FOR SELECT TO authenticated
USING (activa AND (SELECT naxji_private.can_read()));

DROP POLICY IF EXISTS naxji_profile_read ON public.perfiles;
CREATE POLICY naxji_profile_read ON public.perfiles FOR SELECT TO authenticated
USING ((SELECT naxji_private.can_read()) AND
       (id = (SELECT auth.uid()) OR (SELECT naxji_private.has_role(ARRAY['ADMINISTRADOR']))));

DROP POLICY IF EXISTS naxji_roles_read ON public.usuario_roles;
CREATE POLICY naxji_roles_read ON public.usuario_roles FOR SELECT TO authenticated
USING ((SELECT naxji_private.can_read()) AND
       (usuario_id = (SELECT auth.uid()) OR (SELECT naxji_private.has_role(ARRAY['ADMINISTRADOR']))));

DROP POLICY IF EXISTS naxji_request_read ON public.solicitudes;
CREATE POLICY naxji_request_read ON public.solicitudes FOR SELECT TO authenticated
USING ((SELECT naxji_private.can_read()) AND
       (usuario_id = (SELECT auth.uid()) OR (SELECT naxji_private.has_role(ARRAY['ADMINISTRADOR']))));

DROP POLICY IF EXISTS naxji_values_read ON public.solicitud_valores;
CREATE POLICY naxji_values_read ON public.solicitud_valores FOR SELECT TO authenticated
USING (EXISTS (SELECT 1 FROM public.solicitudes s WHERE s.id=solicitud_id));

DROP POLICY IF EXISTS naxji_prediction_read ON public.predicciones_ia;
CREATE POLICY naxji_prediction_read ON public.predicciones_ia FOR SELECT TO authenticated
USING (EXISTS (SELECT 1 FROM public.solicitudes s WHERE s.id=solicitud_id));

DROP POLICY IF EXISTS naxji_norms_read ON public.prediccion_normativas;
CREATE POLICY naxji_norms_read ON public.prediccion_normativas FOR SELECT TO authenticated
USING (EXISTS (SELECT 1 FROM public.predicciones_ia p WHERE p.id=prediccion_id));

DROP POLICY IF EXISTS naxji_report_read ON public.informes;
CREATE POLICY naxji_report_read ON public.informes FOR SELECT TO authenticated
USING (EXISTS (SELECT 1 FROM public.solicitudes s WHERE s.id=solicitud_id));

DROP POLICY IF EXISTS naxji_versions_read ON public.versiones_informe;
CREATE POLICY naxji_versions_read ON public.versiones_informe FOR SELECT TO authenticated
USING (EXISTS (SELECT 1 FROM public.informes i WHERE i.id=informe_id));

-- Perfiles futuros: pendientes e inactivos, sin roles automáticos.
-- Nunca confiar en roles/activo enviados en raw_user_meta_data.
CREATE OR REPLACE FUNCTION naxji_private.create_pending_profile()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
    INSERT INTO public.perfiles (id,nombres,apellidos,activo)
    VALUES (NEW.id,
            left(coalesce(nullif(btrim(NEW.raw_user_meta_data->>'nombres'),''),'Pendiente'),100),
            left(coalesce(nullif(btrim(NEW.raw_user_meta_data->>'apellidos'),''),'Pendiente'),150),
            false)
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    -- Falla cerrada: no deja un alta Auth parcialmente inicializada ni expone metadata.
    RAISE EXCEPTION USING ERRCODE='P0001', MESSAGE='No se pudo inicializar el perfil NAXJI';
END;
$$;
REVOKE ALL ON FUNCTION naxji_private.create_pending_profile() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS naxji_pending_profile ON auth.users;
CREATE TRIGGER naxji_pending_profile AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION naxji_private.create_pending_profile();

-- Sin INSERT/UPDATE/DELETE para authenticated: tampoco puede autoasignarse roles.
-- La activación y asignación de roles requiere un administrador autorizado;
-- no se añade un endpoint de gestión que aún no tenga caso de uso.
