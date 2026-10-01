"""Inspección piloto en una base desechable loopback. Nunca usa Supabase."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter
from unittest.mock import Mock
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
import pytest
from fastapi.testclient import TestClient

from src.adapters.out.ai.generador_borrador_ollama import GeneradorBorradorOllama
from src.application.ports.output.generador_borrador import ContextoConfirmado
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.dependencies import get_current_user
from src.main import create_app
from tests.test_estructura_postgres import db_local, script, ROOT  # noqa: F401
from tests.test_piloto_v2 import leer_docx


pytestmark = pytest.mark.skipif(not os.getenv("NAXJI_TEST_PG_PORT"), reason="PostgreSQL aislado: opt-in")
SEED = "database/seeds/20261001_piloto_inspeccion_ambiental.sql"
TECNICA = "database/seeds/20261001_piloto_v2_datos_fuente.sql"
NOMBRE = "Informe de Inspección – Piloto NAXJI"
ASUNTO = "PRUEBA NAXJI INSPECCIÓN: solicitud de inspección ambiental del parque ficticio Aurora, sin resultados"


def snapshot(c):
    # Incluye filas y timestamps previos, no solo cantidades o textos.
    tablas = c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
    return {t: c.execute(sql.SQL("SELECT to_jsonb(t) FROM public.{} t ORDER BY to_jsonb(t)::text").format(sql.Identifier(t))).fetchall()
            for (t,) in tablas}


@pytest.fixture
def piloto(db_local):
    db, uid, *_ = db_local
    with db.connect(autocommit=True) as c:
        script(c, TECNICA)
        script(c, SEED)
    settings = Settings(persistence_mode="postgres", auth_mode="disabled", ollama_base_url="http://localhost:11434",
                        ollama_model="qwen2.5:7b", ollama_timeout_seconds=300)
    deps = Container(settings, database_settings=db)  # predictor sklearn real, sin cambios
    app = create_app(settings, deps)
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(uid, frozenset({Rol.FUNCIONARIO}))
    with TestClient(app) as client:
        yield db_local, deps, client, app


def preparar_inspeccion(client, *, notas=False, asunto=ASUNTO, datos_fuente=None):
    r = client.post("/solicitudes", json={"asunto": asunto})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    url = f"/solicitudes/{sid}"
    r = client.post(url + "/predecir-contexto")
    assert r.status_code == 200, r.text
    prediccion = r.json()
    tipos, areas = client.get("/tipos-informe").json(), client.get("/areas").json()
    tipo = next(t for t in tipos if t["codigo"] == "INFORME_INSPECCION")
    area = next(a for a in areas if a["codigo"] == "MDT_SGGA")
    # La revisión humana puede corregir la clasificación; no se fuerza el predictor.
    r = client.post(url + "/validar-prediccion", json={"prediccion_id": prediccion["id"], "resultado": "CORREGIDA",
                    "tipo_informe_id": tipo["id"], "area_destino_id": area["id"], "normativa_ids": []})
    assert r.status_code == 200, r.text
    assert all(n["aceptada"] is False for n in client.get(url + "/contexto").json()["normativas"])
    r = client.get("/plantillas", params={"tipo_informe_id": tipo["id"]})
    assert r.status_code == 200
    plantilla = next(p for p in r.json() if p["nombre"] == NOMBRE)
    assert plantilla["area_id"] == area["id"] and plantilla["tipo_informe_id"] == tipo["id"]
    assert "No constituye un formato municipal oficial" in plantilla["descripcion"]
    # Verifica el filtro real del frontend con el catálogo real de esta base aislada.
    comprobacion = subprocess.run(["node", "--input-type=module", "-e", """
import { plantillaCompatible } from './src/adapters/in/web/services/flujoInforme.js';
import assert from 'node:assert/strict';
let input = ''; for await (const chunk of process.stdin) input += chunk;
const {plantilla:p, tipo:t, area:a} = JSON.parse(input);
assert.equal(plantillaCompatible(p,t.id,a.id), true);
assert.equal(plantillaCompatible(p,'otro-tipo',a.id), false);
assert.equal(plantillaCompatible(p,t.id,'otra-area'), false);
"""], input=json.dumps({"plantilla": plantilla, "tipo": tipo, "area": area}), text=True,
        capture_output=True, cwd=ROOT)
    assert comprobacion.returncode == 0, comprobacion.stderr
    campos = client.get(f"/plantillas/{plantilla['id']}/campos").json()
    assert len(campos) == 7 and len(plantilla["secciones_salida"]) == 6
    fixture = json.loads((ROOT / "tests/fixtures/inspeccion_piloto.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in plantilla.items() if k not in {"id", "tipo_informe_id", "area_id"}} == {
        k: v for k, v in fixture["plantilla"].items() if k not in {"id", "tipo_informe_id", "area_id"}}
    assert [{k: v for k, v in c.items() if k not in {"id", "plantilla_id"}} for c in campos] == [
        {k: v for k, v in c.items() if k not in {"id", "plantilla_id"}} for c in fixture["campos"]]
    assert {c["clave"] for c in campos if c["obligatorio"]} == {"estado_resultados"}
    assert not {c["clave"] for c in campos} & {s["clave"] for s in plantilla["secciones_salida"]}
    datos = {"estado_resultados": "Sin resultados de inspección"}
    if notas:
        datos["resultados_observados"] = "Sin acta ni visita documentada; esta nota no acredita hallazgos."
    if datos_fuente is not None:
        datos = datos_fuente
    body = {"asunto": asunto, "tipo_informe_id": tipo["id"], "area_destino_id": area["id"],
            "area_origen_id": area["id"], "plantilla_id": plantilla["id"],
            "valores": [{"campo_plantilla_id": c["id"], "valor": datos[c["clave"]]} for c in campos if c["clave"] in datos]}
    otra_area = next(a["id"] for a in areas if a["id"] != area["id"])
    incompatible = client.put(url + "/completa", json={**body, "area_destino_id": otra_area})
    assert incompatible.status_code == 400 and "área de destino" in incompatible.text
    assert client.put(url + "/completa", json={**body, "valores": []}).status_code == 400
    guardada = client.put(url + "/completa", json=body)
    assert guardada.status_code == 200, guardada.text
    assert guardada.json()["estado"] == "LISTA_PARA_GENERAR"
    return sid, plantilla, campos, prediccion, body


def test_sql_idempotente_preserva_todas_las_filas_tecnicas_y_documentos(db_local):
    db = db_local[0]
    with db.connect(autocommit=True) as c:
        script(c, TECNICA)
        antes = snapshot(c)
        script(c, SEED)
        despues = snapshot(c)
        for tabla, registros in antes.items():
            if tabla not in {"plantillas", "campos_plantilla"}:
                assert despues[tabla] == registros, tabla
            else:
                assert all(r in despues[tabla] for r in registros), tabla
        assert len(despues["plantillas"]) == len(antes["plantillas"]) + 1
        assert len(despues["campos_plantilla"]) == len(antes["campos_plantilla"]) + 7
        script(c, SEED)
        assert snapshot(c) == despues
        script(c, "database/checks/20261001_verificar_piloto_inspeccion.sql")
        assert snapshot(c) == despues


@pytest.mark.parametrize("cambio", [
    "UPDATE public.plantillas SET activa=false WHERE nombre=%s",
    "UPDATE public.plantillas SET area_id=NULL WHERE nombre=%s",
    "UPDATE public.campos_plantilla SET etiqueta='Campo personalizado' WHERE plantilla_id IN (SELECT id FROM public.plantillas WHERE nombre=%s)",
])
def test_sql_rechaza_conflictos_sin_reactivar_o_sobrescribir(db_local, cambio):
    db = db_local[0]
    with db.connect(autocommit=True) as c:
        script(c, SEED)
        c.execute(cambio, (NOMBRE,))
        antes = snapshot(c)
        with pytest.raises(psycopg.errors.RaiseException):
            script(c, SEED)
        c.execute("ROLLBACK")
        assert snapshot(c) == antes


@pytest.mark.parametrize("cambio", [
    "UPDATE public.areas_municipales SET activo=false WHERE codigo='MDT_SGGA'",
    "UPDATE public.tipos_informe SET activo=false WHERE codigo='INFORME_INSPECCION'",
    "ALTER TABLE public.versiones_informe DROP COLUMN titulo",
])
def test_sql_sin_prerrequisito_no_inserta_registros(db_local, cambio):
    db = db_local[0]
    with db.connect(autocommit=True) as c:
        c.execute(cambio)  # Solo en la base desechable creada por el fixture.
        antes = snapshot(c)
        with pytest.raises(psycopg.errors.RaiseException):
            script(c, SEED)
        c.execute("ROLLBACK")
        assert snapshot(c) == antes


def comprobar_edicion_y_descarga(client, deps, db, sid, plantilla, generado):
    iid = generado["informe_id"]
    original = deepcopy(generado)
    contenido = {**generado["contenido"], "conclusiones": "Revisión humana ficticia NAXJI: no se aportaron resultados de inspección.\nPendiente de verificación: obtener el acta y las evidencias antes de emitir conclusiones sobre el parque ficticio Aurora."}
    editado = client.put(f"/informes/{iid}", json={"numero_version": 1, "contenido": contenido,
                         "titulo": "Inspección piloto del parque ficticio Aurora"})
    assert editado.status_code == 200, editado.text
    assert editado.json()["numero_version"] == 2
    recuperado = client.get(f"/solicitudes/{sid}/informe")
    assert recuperado.status_code == 200 and recuperado.json() == editado.json()
    # Otra instancia comprueba persistencia más allá de objetos/cachés de esta petición.
    nueva = Container(Settings(persistence_mode="postgres", auth_mode="disabled"), database_settings=db)
    uid = UUID(client.get(f"/solicitudes/{sid}").json()["usuario_id"])
    restaurado = nueva.obtener_informe.por_solicitud(UUID(sid), UsuarioActual(uid, frozenset({Rol.FUNCIONARIO})))
    assert restaurado.versiones[-1].contenido == contenido
    historica = client.get(f"/informes/{iid}/versiones/1").json()
    for campo in ("contenido", "titulo", "numero_version", "secciones_salida", "modelo_ia"):
        assert historica[campo] == original[campo]
    def prohibida(*args, **kwargs):
        raise AssertionError("La descarga no debe llamar a Ollama")
    deps.generar_borrador.generador.generar = prohibida
    with db.connect() as c:
        antes = snapshot(c)
    descarga = client.get(f"/informes/{iid}/versiones/2/docx")
    doc = leer_docx(descarga)
    assert [p.text for p in doc.paragraphs if p.style.name == "Heading 1"] == ["Encabezado"] + [s["titulo"] for s in plantilla["secciones_salida"]]
    textos = "\n".join(p.text for p in doc.paragraphs)
    assert contenido["conclusiones"] in textos and "Asunto: " + ASUNTO in textos
    assert "Formato Word piloto" in textos and "[object Object]" not in textos
    assert client.get(f"/informes/{iid}").json() == editado.json()
    with db.connect() as c:
        assert snapshot(c) == antes
    return descarga, contenido, {"edicion": editado.status_code, "recuperacion": recuperado.status_code, "descarga": descarga.status_code}


def test_inspeccion_sin_resultados_reintento_edicion_recuperacion_docx_y_permisos(piloto):
    (db, uid, _, iid_legacy, contenido_legacy), deps, client, app = piloto
    sid, plantilla, _, _, body = preparar_inspeccion(client, notas=True)
    propuesta = {s["clave"]: "Texto no marcado pese a que no hay resultados." for s in plantilla["secciones_salida"]}
    llm = Mock(model="qwen2.5:7b", generar=Mock(return_value=json.dumps(propuesta)))
    deps.generar_borrador.generador = GeneradorBorradorOllama(llm)
    r = client.post(f"/solicitudes/{sid}/generar-borrador", json={})
    assert r.status_code == 502 and r.json()["codigo"] == "OLLAMA_RESPUESTA_INVALIDA"
    assert client.get(f"/solicitudes/{sid}").json()["estado"] == "LISTA_PARA_GENERAR"
    assert client.get(f"/solicitudes/{sid}/informe").status_code == 404
    entrada = json.loads(llm.generar.call_args.args[0])
    assert entrada["fuentes_sin_hechos"] is True  # incluso con notas escritas
    assert entrada["contexto_confirmado"]["tipo_informe"] == "Informe de Inspección"
    assert entrada["contexto_confirmado"]["area_destino"] == "Subgerencia de Gestión Ambiental"
    assert entrada["contexto_confirmado"]["normas_seleccionadas_no_verificadas"] == []
    esquema = llm.generar.call_args.kwargs["esquema"]
    assert esquema["properties"]["hallazgos"]["pattern"] == "^Pendiente de verificación:"
    llm.generar.return_value = json.dumps({k: "Pendiente de verificación: no se aportaron resultados ni actas." for k in propuesta})
    r = client.post(f"/solicitudes/{sid}/generar-borrador", json={})
    assert r.status_code == 201, r.text
    generado = r.json()
    assert generado["modelo_ia"] == "qwen2.5:7b"
    assert generado["contenido"]["encabezado"]["asunto"] == ASUNTO
    assert generado["secciones_salida"] == plantilla["secciones_salida"]
    comprobar_edicion_y_descarga(client, deps, db, sid, plantilla, generado)
    assert llm.generar.call_count == 2
    recuperados = client.get(f"/solicitudes/{sid}").json()["valores"]
    assert {v["campo_plantilla_id"]: v["valor"] for v in recuperados} == {v["campo_plantilla_id"]: v["valor"] for v in body["valores"]}
    assert client.get(f"/informes/{iid_legacy}").json()["contenido"] == contenido_legacy
    leer_docx(client.get(f"/informes/{iid_legacy}/versiones/1/docx"))
    # Otro funcionario no puede leer ni descargar; el permiso no depende del template.
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(uuid4(), frozenset({Rol.FUNCIONARIO}))
    assert client.get(f"/informes/{generado['informe_id']}/versiones/2/docx").status_code == 403
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(uid, frozenset({Rol.REVISOR}))
    assert client.get(f"/informes/{generado['informe_id']}/versiones/2/docx").status_code == 200


@pytest.mark.parametrize("estado,hechos,sin_hechos", [
    ("Sin resultados de inspección", "Notas sin acreditar resultados.", True),
    ("Información parcial por verificar", "", True),
    ("Resultados documentados disponibles", "", True),
    ("Resultados documentados disponibles", "Acta ficticia de prueba: se aportó una medición identificada.", False),
])
def test_estado_sin_resultados_y_hechos_se_interpretan_separadamente(piloto, estado, hechos, sin_hechos):
    _, deps, _, _ = piloto
    plantilla = next(p for p in deps.plantillas.listar() if p.nombre == NOMBRE)
    llm = Mock(model="qwen2.5:7b", generar=Mock(return_value=json.dumps({
        s.clave: "Pendiente de verificación: texto simulado." for s in plantilla.secciones_salida})))
    contexto = ContextoConfirmado(plantilla.tipo_informe_id, plantilla.area_id, ())
    GeneradorBorradorOllama(llm).generar(ASUNTO, plantilla,
        {"estado_resultados": estado, "resultados_observados": hechos}, contexto, "")
    assert json.loads(llm.generar.call_args.args[0])["fuentes_sin_hechos"] is sin_hechos
    assert ("pattern" in llm.generar.call_args.kwargs["esquema"]["properties"]["hallazgos"]) is sin_hechos


@pytest.mark.skipif(os.getenv("NAXJI_RUN_OLLAMA_TESTS") != "1", reason="Ollama real: opt-in")
def test_inspeccion_ollama_real_pocos_datos(piloto, tmp_path):
    (db, *_), deps, client, _ = piloto
    sid, plantilla, _, prediccion, _ = preparar_inspeccion(client)
    inicio = perf_counter()
    r = client.post(f"/solicitudes/{sid}/generar-borrador", json={})
    segundos = round(perf_counter() - inicio, 3)
    assert r.status_code == 201, r.text
    generado = r.json()
    assert generado["modelo_ia"] == "qwen2.5:7b"
    assert generado["secciones_salida"] == plantilla["secciones_salida"]
    textos = {k: v for k, v in generado["contenido"].items() if k != "encabezado"}
    for s in plantilla["secciones_salida"]:
        if s["obligatoria"]:
            assert s["clave"] in textos
        if s["clave"] != "objetivo" and s["clave"] in textos:
            assert textos[s["clave"]].startswith("Pendiente de verificación:")
    texto = " ".join(textos.values()).lower()
    for afirmacion in ["se constató", "se observó deterioro", "se realizó una inspección", "se ha realizado una inspección",
                       "no se han realizado", "no se realizó", "no existen hallazgos", "no se registraron incidencias",
                       "no se aportaron conclusiones", "no se aportaron recomendaciones",
                       "césped está en buen estado", "césped está en mal estado", "se recomienda podar", "artículo 5"]:
        assert afirmacion not in texto
    descarga, contenido, http = comprobar_edicion_y_descarga(client, deps, db, sid, plantilla, generado)
    destino = tmp_path
    if os.getenv("NAXJI_INSPECCION_EVIDENCE_DIR"):
        destino = Path(os.environ["NAXJI_INSPECCION_EVIDENCE_DIR"]).resolve()
        assert destino.is_relative_to(ROOT / "docs")
        destino.mkdir(parents=True, exist_ok=True)
    (destino / "NAXJI-inspeccion-piloto-corregido.docx").write_bytes(descarga.content)
    evidencia = {"entorno": "PostgreSQL aislado; identidad de prueba inyectada; sklearn y Ollama reales; sin Supabase",
                 "modelo": generado["modelo_ia"], "generacion_segundos": segundos,
                 "solicitud_id": sid, "informe_id": generado["informe_id"], "plantilla": plantilla,
                 "prediccion": prediccion, "confirmacion": {"tipo": "INFORME_INSPECCION", "area": "MDT_SGGA", "normativa_ids": []},
                 "datos_fuente": {"estado_resultados": "Sin resultados de inspección"}, "propuesta": textos,
                 "edicion_guardada": contenido, "http": {"generacion": r.status_code, **http},
                 "limites": "Caso ficticio, no certifica fidelidad del modelo para cualquier entrada. Revisión humana obligatoria."}
    (destino / "ollama-real.json").write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"modelo": evidencia["modelo"], "segundos": segundos, "http": evidencia["http"]}))
