"""Opt-in: dos inspecciones ficticias; Ollama real, PostgreSQL aislado, sin Supabase."""
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import UUID

import pytest

from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from tests.test_estructura_postgres import db_local  # noqa: F401
from tests.test_inspeccion_piloto import piloto, preparar_inspeccion, snapshot  # noqa: F401
from tests.test_piloto_v2 import leer_docx

pytestmark = pytest.mark.skipif(os.getenv("NAXJI_RUN_OLLAMA_TESTS") != "1" or not os.getenv("NAXJI_TEST_PG_PORT"), reason="Ollama y PostgreSQL aislado: opt-in")


@pytest.mark.parametrize("con_resultados", [False, True], ids=["sin-resultados", "con-resultados"])
def test_generar_editar_recuperar_y_descargar(piloto, tmp_path, con_resultados):
    (db, uid, *_), deps, client, _ = piloto
    asunto = "PRUEBA NAXJI: preparar un informe de inspección sobre una posible acumulación de residuos en un parque del distrito de Huancayo."
    datos = {"estado_resultados": "Sin resultados de inspección"}
    if con_resultados:
        datos = {"estado_resultados": "Resultados documentados disponibles", "fecha_inspeccion": "2026-09-30",
                 "lugar_inspeccion": "Lugar ficticio de prueba: parque Aurora, entrada norte junto al acceso A, distrito de Huancayo",
                 "alcance_solicitado": "Describir únicamente la observación aportada y proponer su verificación por la unidad competente.",
                 "resultados_observados": "CASO FICTICIO: la ficha E1 del 2026-09-30 registra dos bolsas cerradas junto al acceso A de la entrada norte. No se conoce su contenido, origen ni permanencia. No se evaluó el resto del parque.",
                 "referencias_conocidas": "E1: ficha ficticia de observación del 2026-09-30; extracto aportado: dos bolsas cerradas junto al acceso A. FOTO-E1: referencia a fotografía ficticia, imagen no adjunta ni verificada.",
                 "informacion_pendiente": "Verificar competencia territorial, contenido y permanencia de las bolsas. Contrastar E1 y obtener la fotografía antes de decidir medidas."}
    sid, plantilla, _, _, _ = preparar_inspeccion(client, asunto=asunto, datos_fuente=datos)
    inicio = perf_counter()
    r = client.post(f"/solicitudes/{sid}/generar-borrador", json={})
    segundos = round(perf_counter() - inicio, 3)
    assert r.status_code == 201, r.text
    generado = r.json()
    assert generado["modelo_ia"] == "qwen2.5:7b" and generado["titulo"] == "Informe de Inspección"
    assert generado["plantilla_version"] == 1
    assert generado["secciones_salida"] == plantilla["secciones_salida"]
    propuesta = {s["clave"]: generado["contenido"][s["clave"]] for s in plantilla["secciones_salida"]}
    texto = " ".join(propuesta.values()).lower()
    assert "infantil" not in texto and "césped" not in texto
    recomendaciones = propuesta["recomendaciones"].lower()
    if con_resultados:
        assert "e1" in texto and "bolsas" in texto
        assert "e1" in recomendaciones or "bolsas" in recomendaciones
        assert "e1" in propuesta["actuaciones"].lower()
        assert "bolsas" in propuesta["conclusiones"].lower()
    else:
        assert "ubicaci" in recomendaciones and "visita" in recomendaciones
        assert "se observó" not in texto and "se realizó" not in texto
    iid = generado["informe_id"]
    # Mantiene la propuesta para revisión visual; agrega una nota humana identificable.
    contenido = {**generado["contenido"], "conclusiones": propuesta["conclusiones"] + "\nRevisión humana de prueba: este documento usa datos ficticios y requiere validación antes de cualquier uso."}
    if con_resultados:
        # Edición humana explícita, visible junto a la propuesta sin modificar en la evidencia.
        contenido["objetivo"] = "Describir la observación aportada en E1 y precisar las comprobaciones necesarias antes de decidir una actuación."
        contenido["conclusiones"] = "Según la ficha ficticia E1 aportada, se registran dos bolsas cerradas en la entrada norte, junto al acceso A. Esto no determina su contenido, origen ni permanencia, ni el estado del resto del parque. Se requiere contrastar la fuente y verificar la competencia territorial.\nRevisión humana de prueba: este documento usa datos ficticios y requiere validación antes de cualquier uso."
    oficiales = {"numero": "", "emisor": "Unidad de prueba NAXJI (ficticia)",
                 "destinatario": "Subgerencia de Gestión Ambiental", "fecha": "", "referencia": "Prueba local; sin expediente oficial",
                 "firmante": "", "cargo_firmante": ""}
    editado = client.put(f"/informes/{iid}", json={"numero_version": 1, "contenido": contenido, "encabezado_oficial": oficiales})
    assert editado.status_code == 200, editado.text
    recuperado = client.get(f"/solicitudes/{sid}/informe")
    assert recuperado.status_code == 200 and recuperado.json() == editado.json()
    assert client.get(f"/informes/{iid}/versiones/1").json()["contenido"] == generado["contenido"]
    nuevo = Container(Settings(persistence_mode="postgres", auth_mode="disabled"), database_settings=db)
    guardado = nuevo.obtener_informe.por_solicitud(UUID(sid), UsuarioActual(uid, frozenset({Rol.FUNCIONARIO})))
    assert guardado.versiones[-1].contenido == editado.json()["contenido"]
    def prohibida(*args, **kwargs):
        raise AssertionError("Descargar no debe generar")
    deps.generar_borrador.generador.generar = prohibida
    with db.connect() as c:
        antes = snapshot(c)
    descarga = client.get(f"/informes/{iid}/versiones/2/docx")
    doc = leer_docx(descarga)
    textos = "\n".join(p.text for p in doc.paragraphs)
    assert contenido["conclusiones"] in textos and str(uid) not in textos
    assert "Número: [POR COMPLETAR]" in textos
    assert [p.text for p in doc.paragraphs if p.style.name == "Heading 1"] == ["Encabezado"] + [s["titulo"] for s in plantilla["secciones_salida"]]
    with db.connect() as c:
        assert snapshot(c) == antes
    destino = tmp_path
    if os.getenv("NAXJI_CONTENIDO_EVIDENCE_DIR"):
        destino = Path(os.environ["NAXJI_CONTENIDO_EVIDENCE_DIR"]).resolve()
        assert destino.is_relative_to(Path(__file__).resolve().parents[1] / "docs")
        destino.mkdir(parents=True, exist_ok=True)
    nombre = "inspeccion-" + ("con-resultados" if con_resultados else "sin-resultados")
    (destino / (nombre + ".docx")).write_bytes(descarga.content)
    evidencia = {"entorno": "PostgreSQL aislado; identidad ficticia inyectada; sklearn y Ollama reales; sin Supabase",
                 "solicitud_id": sid, "informe_id": iid, "modelo": generado["modelo_ia"], "segundos": segundos,
                 "asunto": asunto, "datos_fuente": datos, "propuesta": propuesta, "version_guardada": editado.json(),
                 "http": {"generacion": r.status_code, "edicion": editado.status_code, "recuperacion": recuperado.status_code, "descarga": descarga.status_code}}
    (destino / (nombre + ".json")).write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"caso": nombre, "segundos": segundos, "http": evidencia["http"]}))
