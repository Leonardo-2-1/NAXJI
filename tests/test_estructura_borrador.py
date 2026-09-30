"""Estructuras sintéticas: no son formatos institucionales ni resultados del predictor."""
import importlib
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.adapters.out.ai.generador_borrador_ollama import GeneradorBorradorOllama
from src.adapters.out.persistence.postgres import entity, save
from src.application.ports.output.generador_borrador import ContextoConfirmado, ResultadoBorrador
from src.domain.entities.informe import Informe, VersionInforme
from src.domain.entities.plantilla import Plantilla
from src.domain.services.errores import DatosInvalidos, ErrorGeneracion
from src.domain.services.informe_service import validar_contenido
from src.domain.value_objects.estados import OrigenVersion
from src.domain.value_objects.estructura_piloto import estructura_piloto
from src.domain.value_objects.seccion_salida import (
    estructura_legacy, secciones_a_json, secciones_desde_json, secciones_efectivas,
)
from tests.test_api import flujo_hasta_generar
from tests.test_casos_uso import preparar

DEMO = json.loads((Path(__file__).parent / "fixtures/estructuras_demostrativas.json").read_text(encoding="utf-8"))
representar_informe = importlib.import_module("src.adapters.in.schemas.informe_response").representar_informe


@pytest.mark.parametrize("demo", DEMO, ids=["piloto-demo", "ficha-sintetica-demo"])
def test_api_genera_edita_recupera_estructura_seleccionada(client, deps, demo):
    sid = flujo_hasta_generar(client)
    solicitud = client.get(f"/solicitudes/{sid}").json()
    plantilla = deps.plantillas.plantillas[next(k for k in deps.plantillas.plantillas if str(k) == solicitud["plantilla_id"])]
    plantilla.secciones_salida = secciones_desde_json(demo["secciones_salida"])
    catalogo = client.get("/plantillas").json()
    assert next(p for p in catalogo if p["id"] == str(plantilla.id))["secciones_salida"] == demo["secciones_salida"]
    respuesta = client.post(f"/solicitudes/{sid}/generar-borrador", json={})
    assert respuesta.status_code == 201, respuesta.text
    informe = respuesta.json()
    assert informe["secciones_salida"] == demo["secciones_salida"]
    assert informe["estructura_legacy"] is False
    assert set(informe["contenido"]) == {s["clave"] for s in demo["secciones_salida"]} | {"encabezado"}
    assert all("DEMOSTRACIÓN MOCK" in informe["contenido"][s["clave"]] for s in demo["secciones_salida"])
    # Una plantilla modificada después no cambia la edición del borrador existente.
    plantilla.secciones_salida = estructura_legacy()
    url = f"/informes/{informe['informe_id']}"
    assert client.get(url).json()["secciones_salida"] == demo["secciones_salida"]
    contenido = informe["contenido"].copy()
    clave = demo["secciones_salida"][0]["clave"]
    del contenido[clave]
    rechazo = client.put(url, json={"contenido": contenido, "numero_version": 1})
    assert rechazo.status_code == 400
    assert clave in rechazo.json()["detail"]
    assert client.get(url).json()["numero_version"] == 1
    contenido[clave] = "Revisión humana de prueba"
    # Omisión opcional válida; encabezado omitido se conserva sin volver a generarlo.
    contenido.pop("encabezado")
    contenido.pop(demo["secciones_salida"][-1]["clave"])
    guardado = client.put(url, json={"contenido": contenido, "numero_version": 1})
    assert guardado.status_code == 200, guardado.text
    assert guardado.json()["contenido"]["encabezado"] == informe["contenido"]["encabezado"]
    assert guardado.json()["secciones_salida"] == demo["secciones_salida"]
    assert client.get(url).json() == guardado.json()


def test_compatibilidad_version_sin_estructura_aunque_plantilla_cambie(deps, usuario):
    solicitud = preparar(deps, usuario)
    contenido = {"antecedentes": "A", "desarrollo": "D", "conclusiones": "C", "objetivo": "Objetivo anterior",
                 "encabezado": {"asunto": "Antiguo"}, "datos": {"fecha": "2020-01-01"}}
    antiguo = Informe(solicitud.id, solicitud.plantilla_id, usuario.id)
    antiguo.versiones.append(VersionInforme(antiguo.id, 1, deepcopy(contenido), OrigenVersion.IA, usuario.id))
    deps.informes.guardar(antiguo)
    deps.plantillas.plantillas[solicitud.plantilla_id].secciones_salida = secciones_desde_json(DEMO[1]["secciones_salida"])
    assert representar_informe(deps.obtener_informe.ejecutar(antiguo.id, usuario)).estructura_legacy
    editado = deps.actualizar_borrador.ejecutar(antiguo.id, usuario, {**contenido, "objetivo": "Editado"}, 1)
    assert editado.versiones[0].contenido == contenido
    assert editado.versiones[-1].contenido["objetivo"] == "Editado"
    assert editado.versiones[-1].secciones_salida is None
    with pytest.raises(DatosInvalidos, match="solo lectura"):
        deps.actualizar_borrador.ejecutar(antiguo.id, usuario, {**contenido, "encabezado": {}}, 2)


def test_plantilla_anterior_y_piloto_de_memoria(client, deps):
    catalogo = client.get("/plantillas").json()
    antiguos = [p for p in catalogo if p["estructura_legacy"]]
    assert antiguos
    assert all(p["secciones_salida"] == secciones_a_json(estructura_legacy()) for p in antiguos)
    piloto = next(p for p in deps.plantillas.listar() if p.secciones_salida is not None)
    assert "DEMO" in piloto.nombre
    assert secciones_a_json(piloto.secciones_salida) == DEMO[0]["secciones_salida"]
    assert piloto.secciones_salida == estructura_piloto()
    piloto.secciones_salida.clear()
    assert deps.plantillas.obtener_por_id(piloto.id).secciones_salida == estructura_piloto()


@pytest.mark.parametrize("contenido", [{}, {"resumen_prueba": "   ", "hallazgos_prueba": "ok"},
                                       {"resumen_prueba": "ok", "hallazgos_prueba": {} },
                                       {"resumen_prueba": "ok", "hallazgos_prueba": "ok", "ajena": "no"}])
def test_generacion_invalida_revierte_solicitud_y_no_guarda_version(deps, usuario, contenido):
    solicitud = preparar(deps, usuario)
    deps.plantillas.plantillas[solicitud.plantilla_id].secciones_salida = secciones_desde_json(DEMO[1]["secciones_salida"])
    deps.generar_borrador.generador = Mock(generar=Mock(return_value=ResultadoBorrador(contenido, "TEST")))
    with pytest.raises(DatosInvalidos):
        deps.generar_borrador.ejecutar(solicitud.id, usuario)
    assert deps.solicitudes.obtener_por_id(solicitud.id).estado == solicitud.estado
    assert deps.informes.obtener_por_solicitud(solicitud.id) is None


@pytest.mark.parametrize("valor", [[], {}, [{"clave": "encabezado", "titulo": "No", "obligatoria": True}],
    [{"clave": "a", "titulo": "", "obligatoria": True}],
    [{"clave": "a", "titulo": "A", "obligatoria": "true"}], DEMO[1]["secciones_salida"] * 2])
def test_rechaza_definiciones_invalidas(valor):
    with pytest.raises(DatosInvalidos):
        secciones_desde_json(valor)


def test_adaptador_postgres_serializa_snapshot_y_null_sql():
    secciones = secciones_desde_json(DEMO[1]["secciones_salida"])
    version = VersionInforme(uuid4(), 1, {"resumen_prueba": "A", "hallazgos_prueba": "B"}, OrigenVersion.IA, None,
                             secciones_salida=secciones)
    conexion = Mock()
    save(conexion, "versiones_informe", version, json_fields=("contenido",), insert_only=True)
    valores = conexion.execute.call_args.args[1]
    assert valores[-1].obj == DEMO[1]["secciones_salida"]
    recuperado = entity(VersionInforme, {**vars(version), "secciones_salida": valores[-1].obj})
    assert recuperado == version
    version.secciones_salida = None
    save(conexion, "versiones_informe", version, json_fields=("contenido",), insert_only=True)
    assert conexion.execute.call_args.args[1][-1] is None
    fila_antigua = {k: v for k, v in vars(version).items() if k != "secciones_salida"}
    assert entity(VersionInforme, fila_antigua).secciones_salida is None


@pytest.mark.parametrize("demo", DEMO)
def test_ollama_recibe_estructura_y_valida_respuesta_sin_servicio(demo):
    secciones = secciones_desde_json(demo["secciones_salida"])
    plantilla = Plantilla(uuid4(), demo["nombre"], uuid4(), secciones_salida=secciones)
    contenido = {s.clave: "Texto de prueba" for s in secciones if s.obligatoria}
    llm = Mock(generar=Mock(return_value=json.dumps(contenido)))
    generador = GeneradorBorradorOllama(llm)
    contexto = ContextoConfirmado(plantilla.tipo_informe_id, uuid4(), ())
    resultado = generador.generar("Asunto de prueba", plantilla, {}, contexto, "")
    assert resultado.contenido == contenido
    assert json.dumps(demo["secciones_salida"], ensure_ascii=False, indent=2) in llm.generar.call_args.args[0]
    for invalido in ["sin JSON", "{}", json.dumps({**contenido, "ajena": "No"})]:
        llm.generar.return_value = invalido
        with pytest.raises(ErrorGeneracion):
            generador.generar("Asunto", plantilla, {}, contexto, "")


def test_validacion_legacy_y_opcionales():
    validar_contenido({"antecedentes": "a", "desarrollo": "d", "conclusiones": "c", "datos": {}})
    with pytest.raises(DatosInvalidos):
        validar_contenido({"antecedentes": "a", "conclusiones": "c"})
    validar_contenido({"resumen_prueba": "R", "hallazgos_prueba": "H"}, secciones_desde_json(DEMO[1]["secciones_salida"]))
    assert secciones_efectivas(None) == estructura_legacy()
