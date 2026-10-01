"""Catálogo mediante GET autenticados al backend local; no ejecuta SQL ni escribe datos.

La sesión de consulta se cierra al terminar. No persiste credenciales ni tokens.
"""
import argparse
from datetime import datetime, timezone
from getpass import getpass
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.adapters.out.ai.sklearn_context_predictor import SklearnContextPredictor, TIPOS, AREAS  # noqa: E402
from src.adapters.out.ai.context_predictor_catalogo import ContextPredictorCatalogo  # noqa: E402


def consultar(base_url, credenciales):
    url = urlsplit(base_url)
    if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1"} or url.username or url.password or url.query or url.fragment:
        raise ValueError("Use la URL HTTP del backend local, sin credenciales ni parámetros")
    llamadas = []
    with httpx.Client(base_url=base_url, timeout=45, headers={"X-NAXJI-Client": "web"}) as client:
        def leer(path):
            respuesta = client.get(path)
            llamadas.append({"metodo": "GET", "ruta": path, "status": respuesta.status_code})
            if respuesta.status_code != 200:
                raise ValueError(f"Lectura de catálogo rechazada: HTTP {respuesta.status_code}")
            return respuesta.json()
        config = leer("/auth/config")
        if config.get("mode") != "supabase" or config.get("persistence") != "postgres":
            raise ValueError("El backend debe usar Supabase Auth y PostgreSQL")
        respuesta = client.post("/auth/login", json=credenciales)
        if respuesta.status_code != 200:
            raise ValueError(f"Inicio de sesión rechazado: HTTP {respuesta.status_code}")
        client.headers["Authorization"] = "Bearer " + respuesta.json()["access_token"]
        try:
            tipos, areas, plantillas = leer("/tipos-informe"), leer("/areas"), leer("/plantillas")
            for p in plantillas:
                p["campos"] = leer(f"/plantillas/{p['id']}/campos")
        finally:
            cerrada = client.post("/auth/logout")
            if cerrada.status_code != 204:
                raise ValueError(f"No se pudo cerrar la sesión de consulta: HTTP {cerrada.status_code}")
    predictor = SklearnContextPredictor()
    codigos = [TIPOS[str(nombre)] for nombre in predictor.modelo_tipo.classes_]
    tipo_id = {t["codigo"]: t["id"] for t in tipos}
    area_id = {a["codigo"]: a["id"] for a in areas}
    destino = area_id.get("MDT_SGGA")
    cobertura = []
    for codigo in codigos:
        candidatas = [p for p in plantillas if p["tipo_informe_id"] == tipo_id.get(codigo)]
        compatibles = [p for p in candidatas if p["activa"] and (p["area_id"] is None or p["area_id"] == destino)]
        cobertura.append({"tipo_codigo": codigo, "tipo_id": tipo_id.get(codigo),
                          "plantillas_activas_cualquier_area": [p["id"] for p in candidatas],
                          "compatibles_MDT_SGGA": [p["id"] for p in compatibles]})
    areas_sin_catalogo = []
    for nombre in predictor.modelo_area.classes_:
        codigo = AREAS[str(nombre)]
        resuelto = codigo if codigo in area_id else ContextPredictorCatalogo.AREAS_MDT.get(codigo, codigo)
        if resuelto not in area_id:
            areas_sin_catalogo.append({"etiqueta_modelo": str(nombre), "codigo": codigo})
    return {"fecha_utc": datetime.now(timezone.utc).isoformat(), "lectura": "GET de catálogos por backend local con Supabase Auth; sin SQL enviado a Supabase",
            "tipos": tipos, "areas": areas, "plantillas": plantillas,
            "cobertura_tipos_predichos": cobertura, "areas_modelo_sin_catalogo": areas_sin_catalogo,
            "http": llamadas}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--stdin", action="store_true", help="Credenciales JSON por stdin; no se guardan")
    parser.add_argument("--output", default="docs/evidencias/inspeccion-piloto/catalogo-actual.json")
    args = parser.parse_args()
    credenciales = {}
    try:
        if args.stdin:
            try:
                credenciales = json.loads(sys.stdin.readline())
                if not isinstance(credenciales, dict) or set(credenciales) != {"email", "password"}:
                    raise ValueError
            except ValueError:
                print("Se requiere un objeto JSON con email y password por stdin.")
                return 1
        else:
            credenciales = {"email": input("Correo autorizado: "), "password": getpass("Contraseña: ")}
        datos = consultar(args.base_url, credenciales)
        salida = ROOT / args.output
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"informe": str(salida.relative_to(ROOT)), "tipos": len(datos["tipos"]), "plantillas": len(datos["plantillas"])}, ensure_ascii=True))
    except (httpx.HTTPError, KeyError):
        print("No se pudo consultar el catálogo; revise disponibilidad del backend y autenticación.")
        return 1
    except ValueError as error:
        print(str(error))
        return 1
    finally:
        if isinstance(credenciales, dict):
            credenciales.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
