"""Compara el catálogo con el JSON literal de la semilla SIN ejecutarla.

Solo SELECT, con transacción PostgreSQL REPEATABLE READ / READ ONLY.
Lee la configuración privada existente sin mostrarla. No inicia sesión Auth,
no inserta, actualiza ni elimina datos. Incluye campos inactivos y extra.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.infrastructure.configuration.database import DatabaseSettings, database_error  # noqa: E402

SEED = ROOT / "database/seeds/20261001_piloto_inspeccion_ambiental.sql"
CLAVES_CAMPO = ("clave", "etiqueta", "tipo_dato", "obligatorio", "orden", "configuracion", "activo")
CLAVES_PLANTILLA = ("nombre", "version", "activa", "descripcion", "tipo_codigo", "area_codigo", "secciones_salida")
COLUMNAS = {("plantillas", "secciones_salida"), ("versiones_informe", "titulo"), ("versiones_informe", "secciones_salida")}


def definicion_sql(path=SEED):
    # Se lee únicamente el literal JSON. NUNCA ejecutar el DO en el destino auditado.
    partes = path.read_text(encoding="utf-8-sig").split("$definicion_inspeccion$")
    if len(partes) != 3:
        raise ValueError("La semilla debe contener una única definición JSON delimitada")
    return json.loads(partes[1])


def diferencias(esperado, actual, ruta=""):
    """Objetos sin orden de claves; arrays ordenados y tipos JSON estrictos."""
    if type(esperado) is not type(actual):
        return [{"ruta": ruta, "esperado": esperado, "guardado": actual}]
    if isinstance(esperado, dict):
        resultado = []
        for k in sorted(esperado.keys() | actual.keys()):
            if k not in esperado or k not in actual:
                resultado.append({"ruta": f"{ruta}.{k}", "esperado": esperado.get(k),
                                  "guardado": actual.get(k), "clave_ausente": k not in actual})
            else:
                resultado.extend(diferencias(esperado[k], actual[k], f"{ruta}.{k}"))
        return resultado
    if isinstance(esperado, list):
        resultado = []
        if len(esperado) != len(actual):
            resultado.append({"ruta": ruta + ".cantidad", "esperado": len(esperado), "guardado": len(actual)})
        for i, (e, a) in enumerate(zip(esperado, actual)):
            resultado.extend(diferencias(e, a, f"{ruta}[{i}]"))
        return resultado
    return [] if esperado == actual else [{"ruta": ruta, "esperado": esperado, "guardado": actual}]


def leer_catalogo(c, esperado):
    solo_lectura = c.execute("SELECT current_setting('transaction_read_only')").fetchone()[0]
    if solo_lectura != "on":
        raise ValueError("La comparación requiere una transacción READ ONLY")
    filas = c.execute("""
      SELECT jsonb_build_object(
        'id',p.id,'nombre',p.nombre,'version',p.version,'activa',p.activa,'descripcion',p.descripcion,
        'tipo_informe_id',p.tipo_informe_id,'tipo_codigo',t.codigo,'tipo_nombre',t.nombre,'tipo_activo',t.activo,
        'area_id',p.area_id,'area_codigo',a.codigo,'area_nombre',a.nombre,'area_activa',a.activo,
        'secciones_salida',p.secciones_salida,
        'campos',COALESCE((SELECT jsonb_agg(jsonb_build_object(
          'id',c.id,'plantilla_id',c.plantilla_id,'clave',c.clave,'etiqueta',c.etiqueta,'tipo_dato',c.tipo_dato,
          'orden',c.orden,'obligatorio',c.obligatorio,'activo',c.activo,'configuracion',c.configuracion)
          ORDER BY c.orden,c.clave) FROM public.campos_plantilla c WHERE c.plantilla_id=p.id),'[]'::jsonb))
        FROM public.plantillas p LEFT JOIN public.tipos_informe t ON t.id=p.tipo_informe_id
        LEFT JOIN public.areas_municipales a ON a.id=p.area_id
        WHERE p.nombre=%s AND p.version=%s
      """, (esperado["nombre"], esperado["version"])).fetchall()
    columnas = c.execute("""SELECT table_name,column_name FROM information_schema.columns
      WHERE table_schema='public' AND ((table_name='versiones_informe' AND column_name IN ('titulo','secciones_salida'))
      OR (table_name='plantillas' AND column_name='secciones_salida')) ORDER BY table_name,column_name""").fetchall()
    return {"transaction_read_only": solo_lectura, "plantillas": [r[0] for r in filas],
            "columnas": [list(r) for r in columnas]}


def comparar(esperado, datos):
    resultado = {"integra": False, "diferencias": [], "comprobaciones": {}}
    if len(datos["plantillas"]) != 1:
        resultado["diferencias"] = [{"ruta": "plantillas.cantidad", "esperado": 1, "guardado": len(datos["plantillas"])}]
        return resultado
    p = datos["plantillas"][0]
    normal = {k: p[k] for k in CLAVES_PLANTILLA}
    normal["campos"] = [{k: c[k] for k in CLAVES_CAMPO} for c in p["campos"]]
    resultado["diferencias"] = diferencias(esperado, normal, "plantilla")
    resultado["comprobaciones"] = {
        "tipo_y_area_activos": p["tipo_activo"] is True and p["area_activa"] is True,
        "metadatos_tipo_area": not diferencias({k: esperado[k] for k in CLAVES_PLANTILLA if k != "secciones_salida"},
                                               {k: normal[k] for k in CLAVES_PLANTILLA if k != "secciones_salida"}),
        "secciones_orden_titulos_y_obligatoriedad": not diferencias(esperado["secciones_salida"], normal["secciones_salida"]),
        "campos_completos_incluida_configuracion": not diferencias(esperado["campos"], normal["campos"]),
        "columnas_para_versiones_y_docx": COLUMNAS <= {tuple(r) for r in datos["columnas"]},
        "consulta_read_only": datos["transaction_read_only"] == "on",
    }
    resultado["campos_comparados"] = [{"clave": c["clave"], "coincide": not diferencias(c, normal["campos"][i])}
                                    for i, c in enumerate(esperado["campos"]) if i < len(normal["campos"])]
    resultado["integra"] = not resultado["diferencias"] and all(resultado["comprobaciones"].values())
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="docs/evidencias/inspeccion-piloto/comparacion-supabase.json")
    args = parser.parse_args()
    try:
        esperado = definicion_sql()
        with DatabaseSettings.from_env().connect() as c:
            c.read_only = True
            c.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            datos = leer_catalogo(c, esperado)
        resultado = comparar(esperado, datos)
        informe = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
                   "fuente_esperada": str(SEED.relative_to(ROOT)), "sha256_sql": sha256(SEED.read_bytes()).hexdigest(),
                   "operacion": "Solo SELECT en PostgreSQL REPEATABLE READ / READ ONLY; no se ejecutó la semilla",
                   "resultado": resultado, "definicion_esperada": esperado, "lectura_guardada": datos}
        destino = (ROOT / args.output).resolve()
        if not destino.is_relative_to(ROOT):
            raise ValueError("El informe debe guardarse dentro del repositorio")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"informe": str(destino.relative_to(ROOT)), **resultado}, ensure_ascii=True))
        return 0 if resultado["integra"] else 2
    except psycopg.Error as error:
        print(database_error(error))  # Mensaje controlado, sin URL ni credenciales.
    except (ValueError, KeyError, OSError):
        print("No se pudo completar la comparación; revise configuración privada y archivos locales. No se muestran secretos.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
