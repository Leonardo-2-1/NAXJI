-- Para revisión. No se ejecuta al arrancar NAXJI ni debe reaplicarse si la auditoría coincide.
-- PILOTO, no formato municipal oficial. No actualiza ni elimina registros.
-- Una sola sentencia DO: ejecutar el bloque COMPLETO, también en el SQL Editor.
-- Cada ejecución es atómica, en autocommit o dentro de una transacción externa.
-- No usa tablas temporales, variables de sesión ni objetos entre ejecuciones.
-- Catálogo real: INFORME_INSPECCION = 668a217a-8f4f-47d6-99d8-0a7ab8661ea6;
-- MDT_SGGA = 1973fec4-ba92-42e5-9de5-994dcd0c674b. Se resuelven por código.
DO $naxji_inspeccion$
DECLARE
  v_definicion constant jsonb := $definicion_inspeccion$
{
  "nombre": "Informe de Inspección – Piloto NAXJI",
  "version": 1,
  "activa": true,
  "descripcion": "DEMOSTRACIÓN de inspección ambiental. No constituye un formato municipal oficial. El funcionario aporta datos fuente; Ollama propone el borrador. Sin resultados, actuaciones, hallazgos y conclusiones quedan pendientes de verificación. Revisión humana obligatoria.",
  "secciones_salida": [
    {
      "clave": "antecedentes",
      "titulo": "Antecedentes de la solicitud",
      "obligatoria": true
    },
    {
      "clave": "objetivo",
      "titulo": "Objetivo y alcance de la inspección",
      "obligatoria": true
    },
    {
      "clave": "actuaciones",
      "titulo": "Actuaciones y fuentes disponibles",
      "obligatoria": true
    },
    {
      "clave": "hallazgos",
      "titulo": "Hallazgos y observaciones",
      "obligatoria": true
    },
    {
      "clave": "conclusiones",
      "titulo": "Conclusiones",
      "obligatoria": true
    },
    {
      "clave": "recomendaciones",
      "titulo": "Recomendaciones y verificaciones pendientes",
      "obligatoria": false
    }
  ],
  "tipo_codigo": "INFORME_INSPECCION",
  "area_codigo": "MDT_SGGA",
  "campos": [
    {
      "clave": "estado_resultados",
      "etiqueta": "Información disponible sobre la inspección",
      "tipo_dato": "select",
      "obligatorio": true,
      "orden": 1,
      "configuracion": {
        "ayuda": "Indique si dispone de resultados. Sin resultados no significa que se haya inspeccionado ni que no existan incidencias.",
        "opciones": [
          "Sin resultados de inspección",
          "Información parcial por verificar",
          "Resultados documentados disponibles"
        ],
        "valores_sin_resultados": [
          "Sin resultados de inspección"
        ]
      },
      "activo": true
    },
    {
      "clave": "lugar_inspeccion",
      "etiqueta": "Lugar o elemento a inspeccionar",
      "tipo_dato": "text",
      "obligatorio": false,
      "orden": 2,
      "configuracion": {
        "ayuda": "Opcional. Identifique el lugar solo si lo conoce. Su identificación no acredita una visita ni su estado."
      },
      "activo": true
    },
    {
      "clave": "fecha_inspeccion",
      "etiqueta": "Fecha de la inspección realizada, si se conoce",
      "tipo_dato": "date",
      "obligatorio": false,
      "orden": 3,
      "configuracion": {
        "ayuda": "Opcional. Registre la fecha solo si la inspección ocurrió y está documentada. No ingrese una fecha supuesta."
      },
      "activo": true
    },
    {
      "clave": "alcance_solicitado",
      "etiqueta": "Aspectos que se solicita verificar",
      "tipo_dato": "textarea",
      "obligatorio": false,
      "orden": 4,
      "configuracion": {
        "ayuda": "Opcional. Indique qué se necesita inspeccionar. Una petición de comprobación no es un hallazgo."
      },
      "activo": true
    },
    {
      "clave": "resultados_observados",
      "etiqueta": "Observaciones y resultados documentados",
      "tipo_dato": "textarea",
      "obligatorio": false,
      "orden": 5,
      "configuracion": {
        "ayuda": "Opcional. Aporte hechos observados, quién o qué documento los respalda y sus límites. Si no dispone de resultados, deje este campo vacío; no redacte hallazgos ni conclusiones anticipados.",
        "rol_fuente": "hechos"
      },
      "activo": true
    },
    {
      "clave": "referencias_conocidas",
      "etiqueta": "Actas, documentos y referencias disponibles",
      "tipo_dato": "textarea",
      "obligatorio": false,
      "orden": 6,
      "configuracion": {
        "ayuda": "Opcional. Identifique documentos, enlaces o extractos que conoce. Un enlace o número no acredita su contenido ni su vigencia; NAXJI no consulta automáticamente esas fuentes.",
        "rol_fuente": "referencias"
      },
      "activo": true
    },
    {
      "clave": "informacion_pendiente",
      "etiqueta": "Información y evidencias pendientes",
      "tipo_dato": "textarea",
      "obligatorio": false,
      "orden": 7,
      "configuracion": {
        "ayuda": "Opcional. Señale observaciones, mediciones o evidencias que aún deben obtenerse o verificarse."
      },
      "activo": true
    }
  ]
}
  $definicion_inspeccion$::jsonb;
  v_tipo_id uuid;
  v_area_id uuid;
  v_plantilla public.plantillas%ROWTYPE;
  v_campos_actuales jsonb;
  v_plantilla_id uuid;
BEGIN
  PERFORM set_config('lock_timeout', '5s', true);
  PERFORM pg_advisory_xact_lock(20261001, 3);

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
      AND table_name='plantillas' AND column_name='secciones_salida')
    OR NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
      AND table_name='versiones_informe' AND column_name='titulo') THEN
    RAISE EXCEPTION 'Faltan las migraciones de secciones o título por versión; revisar prerrequisitos';
  END IF;
  SELECT id INTO v_tipo_id FROM public.tipos_informe
    WHERE codigo=v_definicion->>'tipo_codigo' AND activo FOR SHARE;
  SELECT id INTO v_area_id FROM public.areas_municipales
    WHERE codigo=v_definicion->>'area_codigo' AND activo FOR SHARE;
  IF v_tipo_id IS NULL OR v_area_id IS NULL THEN
    RAISE EXCEPTION 'Se requieren INFORME_INSPECCION y MDT_SGGA activos; no se insertaron registros';
  END IF;

  SELECT * INTO v_plantilla FROM public.plantillas
    WHERE nombre=v_definicion->>'nombre' AND version=(v_definicion->>'version')::integer
    FOR UPDATE;
  IF FOUND THEN
    -- Una versión existente debe coincidir COMPLETA, incluidos campos inactivos.
    -- Una versión parcial también se rechaza; no se rellena silenciosamente.
    IF (v_plantilla.tipo_informe_id,v_plantilla.area_id,v_plantilla.activa,
        v_plantilla.descripcion,v_plantilla.secciones_salida)
      IS DISTINCT FROM (v_tipo_id,v_area_id,(v_definicion->>'activa')::boolean,
                        v_definicion->>'descripcion',v_definicion->'secciones_salida') THEN
      RAISE EXCEPTION 'La plantilla de inspección v1 existente difiere; revisar sin sobrescribir';
    END IF;
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'clave',c.clave,'etiqueta',c.etiqueta,'tipo_dato',c.tipo_dato,
        'obligatorio',c.obligatorio,'orden',c.orden,'configuracion',c.configuracion,'activo',c.activo)
        ORDER BY c.orden,c.clave),'[]'::jsonb)
      INTO v_campos_actuales FROM public.campos_plantilla c WHERE c.plantilla_id=v_plantilla.id;
    IF v_campos_actuales IS DISTINCT FROM v_definicion->'campos' THEN
      RAISE EXCEPTION 'Los campos de inspección existentes difieren o están incompletos; revisar sin sobrescribir';
    END IF;
    RETURN; -- Coincide: cero escrituras, sin cambiar IDs ni timestamps.
  END IF;

  INSERT INTO public.plantillas(nombre,tipo_informe_id,area_id,version,activa,descripcion,secciones_salida)
    VALUES (v_definicion->>'nombre',v_tipo_id,v_area_id,(v_definicion->>'version')::integer,
            (v_definicion->>'activa')::boolean,v_definicion->>'descripcion',v_definicion->'secciones_salida')
    RETURNING id INTO v_plantilla_id;
  INSERT INTO public.campos_plantilla(plantilla_id,clave,etiqueta,tipo_dato,obligatorio,orden,configuracion,activo)
    SELECT v_plantilla_id,c.clave,c.etiqueta,c.tipo_dato,c.obligatorio,c.orden,c.configuracion,c.activo
    FROM jsonb_to_recordset(v_definicion->'campos') AS c(
      clave text,etiqueta text,tipo_dato text,obligatorio boolean,orden integer,configuracion jsonb,activo boolean);
  -- Si cualquier inserción falla, PostgreSQL revierte TODA esta sentencia DO.
END
$naxji_inspeccion$;
