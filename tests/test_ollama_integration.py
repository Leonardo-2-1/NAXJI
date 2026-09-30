"""Opt-in: NAXJI_RUN_OLLAMA_TESTS=1. Datos ficticios, API/memoria + predictor y Ollama reales."""
import json
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient
import pytest

from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from src.main import create_app
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.infrastructure.dependencies import get_current_user
from tests.test_estructura_postgres import db_local  # noqa: F401 - fixture local aislada


pytestmark = pytest.mark.skipif(os.getenv("NAXJI_RUN_OLLAMA_TESTS") != "1", reason="Ollama real: prueba opt-in")


@pytest.mark.parametrize("persistencia", ["memory", "postgres"])
def test_flujo_completo_piloto_tecnico_sin_resultados(tmp_path, request, persistencia):
    if persistencia == "postgres" and not os.getenv("NAXJI_TEST_PG_PORT"):
        pytest.skip("El segundo escenario requiere PostgreSQL local aislado")
    fixture = json.loads((Path(__file__).parent / "fixtures/inspeccion_parque_sin_resultados.json").read_text(encoding="utf-8"))
    settings = Settings(persistence_mode=persistencia, auth_mode="mock" if persistencia == "memory" else "disabled",
                        ollama_base_url=os.getenv("NAXJI_OLLAMA_BASE_URL", "http://localhost:11434"),
                        ollama_model=os.getenv("NAXJI_OLLAMA_MODEL", "qwen2.5:7b"),
                        ollama_timeout_seconds=float(os.getenv("NAXJI_OLLAMA_TIMEOUT_SECONDS", "300")))
    database = request.getfixturevalue("db_local") if persistencia == "postgres" else None
    deps = Container(settings, database_settings=database[0] if database else None)
    app = create_app(settings, deps)
    if database:
        usuario = UsuarioActual(database[1], frozenset({Rol.FUNCIONARIO}), deps.catalogos.areas()[0].id)
        app.dependency_overrides[get_current_user] = lambda: usuario
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer demo-funcionario"
        creada = client.post("/solicitudes", json={"asunto": fixture["asunto"]})
        assert creada.status_code == 201, creada.text
        sid = creada.json()["id"]
        url = f"/solicitudes/{sid}"
        prediccion = client.post(url + "/predecir-contexto")
        assert prediccion.status_code == 200, prediccion.text
        p = prediccion.json()
        assert not p["es_mock"]
        tecnico = next(t for t in client.get("/tipos-informe").json() if t["codigo"] == "INFORME_TECNICO")
        area = p["area_destino"]["id"]
        valida = client.post(url + "/validar-prediccion", json={"prediccion_id": p["id"], "resultado": "CORREGIDA",
                             "tipo_informe_id": tecnico["id"], "area_destino_id": area, "normativa_ids": []})
        assert valida.status_code == 200, valida.text
        piloto = client.get("/plantillas", params={"tipo_informe_id": tecnico["id"]}).json()[0]
        campos = client.get(f"/plantillas/{piloto['id']}/campos").json()
        valores = [{"campo_plantilla_id": c["id"], "valor": fixture["datos"][c["clave"]]} for c in campos if c["clave"] in fixture["datos"]]
        guardada = client.put(url + "/completa", json={"asunto": fixture["asunto"], "tipo_informe_id": tecnico["id"],
                              "area_destino_id": area, "area_origen_id": area, "plantilla_id": piloto["id"], "valores": valores})
        assert guardada.status_code == 200, guardada.text
        inicio = perf_counter()
        generado = client.post(url + "/generar-borrador", json={"instrucciones": "Redactar solo con lo aportado; dejar pendiente lo no verificado."})
        duracion = round(perf_counter() - inicio, 3)
        assert generado.status_code == 201, generado.text
        informe = generado.json()
        assert informe["modelo_ia"] == settings.ollama_model
        assert informe["secciones_salida"] == piloto["secciones_salida"]
        claves = [s["clave"] for s in piloto["secciones_salida"]]
        assert set(informe["contenido"]) <= set(claves) | {"encabezado"}
        for s in piloto["secciones_salida"]:
            if s["obligatoria"]:
                assert informe["contenido"][s["clave"]].strip()
        analisis = informe["contenido"]["analisis_tecnico"].lower()
        conclusiones = informe["contenido"]["conclusiones"].lower()
        assert any(t in analisis for t in ["pendiente", "no se dispone", "no se han", "no hay"])
        assert any(t in conclusiones for t in ["pendiente", "no se dispone", "no se han", "no hay", "no es posible"])
        texto = " ".join(v for v in informe["contenido"].values() if isinstance(v, str)).lower()
        for afirmacion in ["se observó deterioro", "se constató", "césped está en buen estado", "césped está en mal estado", "se recomienda podar"]:
            assert afirmacion not in texto
        evidencia = {"entorno": f"API {persistencia}, datos ficticios, predictor sklearn real, Ollama local real",
                     "modelo": informe["modelo_ia"], "segundos": duracion,
                     "plantilla": piloto["nombre"], "secciones": informe["secciones_salida"],
                     "contenido": {k: v for k, v in informe["contenido"].items() if k != "encabezado"}}
        (tmp_path / "ollama-real.json").write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(evidencia, ensure_ascii=True))
        iid = informe["informe_id"]
        recuperado = client.get(f"/informes/{iid}").json()
        for clave in ("created_at", "updated_at"):
            assert datetime.fromisoformat(recuperado.pop(clave)) == datetime.fromisoformat(informe[clave])
        assert recuperado == {k: v for k, v in informe.items() if k not in {"created_at", "updated_at"}}
        editado = client.put(f"/informes/{iid}", json={"numero_version": 1,
                             "contenido": {**informe["contenido"], "conclusiones": "Revisión humana: pendiente de verificación."}})
        assert editado.status_code == 200 and editado.json()["numero_version"] == 2
        assert editado.json()["contenido"]["encabezado"] == informe["contenido"]["encabezado"]
