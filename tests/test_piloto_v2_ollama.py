"""Opt-in: Ollama real y PostgreSQL local aislado; nunca usa .env ni Supabase."""
import json
import os
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.dependencies import get_current_user
from src.main import create_app
from tests.test_estructura_postgres import db_local, script  # noqa: F401
from tests.test_piloto_v2 import preparar_v2, leer_docx
from tests.test_piloto_v2_postgres import SEED


pytestmark = pytest.mark.skipif(os.getenv("NAXJI_RUN_OLLAMA_TESTS") != "1" or not os.getenv("NAXJI_TEST_PG_PORT"),
                               reason="Requiere Ollama real y PostgreSQL local aislado: opt-in")


def test_piloto_v2_real_pocos_datos_edicion_y_word(db_local, tmp_path):
    db, uid, *_ = db_local
    with db.connect(autocommit=True) as c:
        script(c, SEED)
    settings = Settings(persistence_mode="postgres", auth_mode="disabled", ollama_base_url="http://localhost:11434",
                        ollama_model="qwen2.5:7b", ollama_timeout_seconds=300)
    deps = Container(settings, database_settings=db)
    app = create_app(settings, deps)
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(uid, frozenset({Rol.FUNCIONARIO}))
    with TestClient(app) as client:
        sid, plantilla = preparar_v2(client)
        inicio = perf_counter()
        r = client.post(f"/solicitudes/{sid}/generar-borrador", json={})
        segundos = round(perf_counter() - inicio, 3)
        assert r.status_code == 201, r.text
        generado = r.json()
        assert generado["modelo_ia"] == "qwen2.5:7b"
        assert generado["secciones_salida"] == plantilla["secciones_salida"]
        textos = {k: v for k, v in generado["contenido"].items() if k != "encabezado"}
        assert set(textos) == {s["clave"] for s in plantilla["secciones_salida"]}
        (tmp_path / "propuesta-real.json").write_text(json.dumps(generado, ensure_ascii=False, indent=2), encoding="utf-8")
        for clave in ["antecedentes", "analisis_tecnico", "conclusiones"]:
            assert "pendiente de verificación" in textos[clave].lower()
        texto = " ".join(textos.values()).lower()
        for afirmacion in ["se constató", "se observó deterioro", "se realizó una inspección", "se ha realizado una inspección",
                           "césped está en buen estado", "césped está en mal estado", "se recomienda podar", "artículo 5"]:
            assert afirmacion not in texto
        iid = generado["informe_id"]
        contenido = {**generado["contenido"], "conclusiones": "Revisión humana de prueba NAXJI. No se aportaron resultados de inspección.\nPendiente de verificación: observaciones y evidencias del parque ficticio Aurora."}
        edicion = client.put(f"/informes/{iid}", json={"numero_version": 1, "contenido": contenido,
                             "titulo": "Inspección del parque ficticio Aurora"})
        assert edicion.status_code == 200, edicion.text
        recuperado = client.get(f"/solicitudes/{sid}/informe")
        assert recuperado.status_code == 200 and recuperado.json() == edicion.json()
        assert client.get(f"/informes/{iid}/versiones/1").json()["contenido"] == generado["contenido"]
        # Cualquier llamada accidental a Ollama después de guardar debe fallar.
        def prohibida(*args, **kwargs):
            raise AssertionError("No se debe generar al descargar")
        deps.generar_borrador.generador.generar = prohibida
        descargado = client.get(f"/informes/{iid}/versiones/2/docx")
        doc = leer_docx(descargado)
        assert contenido["conclusiones"] in "\n".join(p.text for p in doc.paragraphs)
        assert [p.text for p in doc.paragraphs if p.style.name == "Heading 1"] == ["Encabezado"] + [s["titulo"] for s in plantilla["secciones_salida"]]
        assert client.get(f"/informes/{iid}").json() == edicion.json()
        destino = tmp_path
        if os.getenv("NAXJI_PILOTO_EVIDENCE_DIR"):
            destino = Path(os.environ["NAXJI_PILOTO_EVIDENCE_DIR"]).resolve()
            assert destino.is_relative_to(Path(__file__).resolve().parents[1] / "docs"), "Evidencia solo dentro de docs del repositorio"
            destino.mkdir(parents=True, exist_ok=True)
        (destino / "NAXJI-piloto-v2-corregido.docx").write_bytes(descargado.content)
        evidencia = {"entorno": "PostgreSQL aislado en loopback; identidad de prueba inyectada; sklearn y Ollama reales; sin Supabase",
                     "modelo": generado["modelo_ia"], "generacion_segundos": segundos, "plantilla_version": 2,
                     "solicitud_id": sid, "informe_id": iid, "datos_fuente": {"estado_resultados": "Sin resultados de inspección"},
                     "secciones": plantilla["secciones_salida"], "propuesta": textos, "edicion_guardada": contenido,
                     "http": {"generacion": r.status_code, "edicion": edicion.status_code,
                              "recuperacion": recuperado.status_code, "descarga": descargado.status_code},
                     "limites": "Comprobación de este caso ficticio; no certifica ausencia de alucinaciones para cualquier entrada. Revisión humana obligatoria."}
        (destino / "piloto-v2-ollama.json").write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"modelo": evidencia["modelo"], "segundos": segundos, "http": evidencia["http"]}))
