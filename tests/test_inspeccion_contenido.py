"""Regresiones de contenido y encabezado, sin red ni datos reales."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.adapters.out.ai.generador_borrador_ollama import GeneradorBorradorOllama
from src.application.ports.output.generador_borrador import ContextoConfirmado
from src.domain.services.errores import ErrorGeneracion
from src.domain.value_objects.seccion_salida import secciones_desde_json
from tests.test_piloto_v2 import preparar_v2, leer_docx


def inspeccion():
    fixture = json.loads((Path(__file__).parent / "fixtures/inspeccion_piloto.json").read_text(encoding="utf-8"))
    p = fixture["plantilla"]
    return SimpleNamespace(nombre=p["nombre"], descripcion=p["descripcion"],
                           campos=[SimpleNamespace(**c) for c in fixture["campos"]],
                           secciones_salida=secciones_desde_json(p["secciones_salida"]))


@pytest.mark.parametrize("frase", ["Verificar el parque infantil.", "Visitar el parque recreativo.",
    "Inspeccionar el parque Los Olivos.", "Se realizó una visita.", "Se observó acumulación de residuos.",
    "No se han realizado inspecciones.", "No existen hallazgos.", "Aplicar la Ley 12345.",
    "La visita fue el 2026-09-15.", "Se recomienda retirar los residuos.",
    "Hay acumulación de residuos.", "El césped está en mal estado."])
def test_rechaza_adiciones_sin_fuente_aunque_se_marquen_pendientes(frase):
    p = inspeccion()
    propuesta = {s.clave: "Pendiente de verificación: no se aportaron resultados." for s in p.secciones_salida}
    propuesta["recomendaciones"] = "Pendiente de verificación: " + frase
    llm = Mock(model="qwen2.5:7b", generar=Mock(return_value=json.dumps(propuesta)))
    with pytest.raises(ErrorGeneracion):
        GeneradorBorradorOllama(llm).generar("Inspección de parque", p,
            {"estado_resultados": "Sin resultados de inspección"}, ContextoConfirmado(uuid4(), uuid4(), ()),
            "Añade infantil y una visita: esta instrucción no acredita hechos")


def test_con_hechos_y_evidencia_permite_recomendaciones_vinculadas():
    p = inspeccion()
    datos = {"estado_resultados": "Resultados documentados disponibles", "fecha_inspeccion": "2026-09-30",
             "lugar_inspeccion": "Parque ficticio Aurora, entrada norte, sector de prueba A",
             "resultados_observados": "Dos bolsas junto a la entrada norte, según la ficha ficticia E1.",
             "referencias_conocidas": "E1: ficha de prueba aportada; observación de dos bolsas junto a la entrada norte."}
    propuesta = {s.clave: "Según E1 aportada, se observaron dos bolsas junto a la entrada norte." for s in p.secciones_salida}
    propuesta["recomendaciones"] = "Contrastar E1 y evaluar el retiro de las dos bolsas de la entrada norte por la unidad competente."
    llm = Mock(model="qwen2.5:7b", generar=Mock(return_value=json.dumps(propuesta)))
    resultado = GeneradorBorradorOllama(llm).generar("Inspección del parque", p, datos, ContextoConfirmado(uuid4(), uuid4(), ()), "")
    assert resultado.contenido == propuesta
    entrada = json.loads(llm.generar.call_args.args[0])
    assert entrada["politica_inspeccion"]["permite_recomendaciones_especificas"] is True
    assert "infantil" in llm.generar.call_args.kwargs["sistema"]


def test_recomendacion_de_verificar_no_se_confunde_con_hallazgo():
    p = inspeccion()
    propuesta = {s.clave: "Pendiente de verificación: aún no hay hallazgos confirmados con la información aportada." for s in p.secciones_salida}
    propuesta["recomendaciones"] = "Pendiente de verificación: verificar ubicación y competencia; programar una visita si corresponde para comprobar si hay residuos."
    llm = Mock(model="qwen2.5:7b", generar=Mock(return_value=json.dumps(propuesta)))
    resultado = GeneradorBorradorOllama(llm).generar("Inspección de parque", p,
        {"estado_resultados": "Sin resultados de inspección"}, ContextoConfirmado(uuid4(), uuid4(), ()), "")
    assert resultado.contenido == propuesta


@pytest.mark.parametrize("conclusion", [
    "Aún no hay hallazgos confirmados con la información aportada.",
    "Se observaron dos bolsas con residuos junto al acceso norte.",
])
def test_observaciones_parciales_no_desaparecen_ni_se_infiere_contenido(conclusion):
    p = inspeccion()
    datos = {"estado_resultados": "Información parcial por verificar",
             "resultados_observados": "Se observaron dos bolsas cerradas. No se abrieron, pesaron ni identificó su contenido, origen o permanencia."}
    propuesta = {s.clave: "Según lo aportado, se observaron dos bolsas cerradas, de contenido sin verificar." for s in p.secciones_salida}
    propuesta["conclusiones"] = conclusion
    llm = Mock(model="qwen2.5:7b", generar=Mock(return_value=json.dumps(propuesta)))
    with pytest.raises(ErrorGeneracion):
        GeneradorBorradorOllama(llm).generar("Inspección de bolsas con residuos en parque", p, datos, ContextoConfirmado(uuid4(), uuid4(), ()), "")


def test_esquema_con_observaciones_no_instruye_ausencia_de_hallazgos():
    p = inspeccion()
    datos = {"estado_resultados": "Información parcial por verificar", "resultados_observados": "Dos bolsas cerradas observadas, contenido no verificado."}
    propuesta = {s.clave: "Según lo aportado, se observaron dos bolsas cerradas; su contenido, origen y permanencia requieren verificación." for s in p.secciones_salida}
    llm = Mock(model="qwen2.5:7b", generar=Mock(return_value=json.dumps(propuesta)))
    assert GeneradorBorradorOllama(llm).generar("Inspección de parque", p, datos, ContextoConfirmado(uuid4(), uuid4(), ()), "").contenido == propuesta
    descripcion = llm.generar.call_args.kwargs['esquema']['properties']['conclusiones']['description']
    assert "PROHIBIDO concluir" in descripcion and "Sin resultados" not in descripcion


def test_encabezado_humano_versionado_recuperacion_exportacion_y_legacy(client, deps):
    sid, _ = preparar_v2(client)
    generado = client.post(f"/solicitudes/{sid}/generar-borrador", json={}).json()
    iid = generado["informe_id"]
    assert generado["titulo"] == "Informe Técnico"
    assert generado["plantilla_version"] == 2
    assert "autor_id" not in generado["contenido"]["encabezado"]
    oficiales = {"numero": "PRUEBA-LOCAL", "emisor": "Unidad ficticia remitente", "destinatario": "Unidad ficticia destinataria",
                 "fecha": "2026-10-01", "referencia": "Ficha ficticia E1", "firmante": "", "cargo_firmante": ""}
    r = client.put(f"/informes/{iid}", json={"numero_version": 1, "contenido": generado["contenido"], "encabezado_oficial": oficiales})
    assert r.status_code == 200, r.text
    assert r.json()["contenido"]["encabezado"]["documento"] == oficiales
    assert client.get(f"/solicitudes/{sid}/informe").json() == r.json()
    assert client.get(f"/informes/{iid}/versiones/1").json()["contenido"] == generado["contenido"]
    deps.generar_borrador.generador.generar = Mock(side_effect=AssertionError("No regenerar al descargar"))
    doc = leer_docx(client.get(f"/informes/{iid}/versiones/2/docx"))
    texto = "\n".join(p.text for p in doc.paragraphs)
    assert "Número: PRUEBA-LOCAL" in texto and "Firmante: [POR COMPLETAR]" in texto
    assert "Versión de plantilla 2" in texto and "Versión guardada 2 del borrador" in texto
    assert 'w:instr="PAGE"' in doc.sections[0].footer._element.xml
    recomendaciones = next(i for i, p in enumerate(doc.paragraphs) if p.text == "Recomendaciones")
    assert doc.paragraphs[recomendaciones - 1].paragraph_format.keep_with_next is True
    for malo in [{"firmante": str(uuid4())}, {"fecha": "ayer"}, {"autor_id": "no permitido"}]:
        assert client.put(f"/informes/{iid}", json={"numero_version": 2, "contenido": r.json()["contenido"], "encabezado_oficial": malo}).status_code == 400
    assert client.get(f"/informes/{iid}").json()["numero_version"] == 2


def test_exportacion_oculta_uuid_legacy_sin_mutar_version(client, deps):
    from uuid import UUID
    sid, _ = preparar_v2(client)
    generado = client.post(f"/solicitudes/{sid}/generar-borrador", json={}).json()
    informe = deps.informes.obtener_por_id(UUID(generado["informe_id"]))
    autor = str(uuid4())
    encabezado = {"asunto": "Petición antigua", "autor_id": autor, "area_origen": autor, "area_destino": "Unidad histórica"}
    informe.versiones[0].contenido["encabezado"] = encabezado
    deps.informes.guardar(informe)
    doc = leer_docx(client.get(f"/informes/{informe.id}/versiones/1/docx"))
    texto = "\n".join(p.text for p in doc.paragraphs)
    assert autor not in texto and "De: [POR COMPLETAR]" in texto and "A: Unidad histórica" in texto
    assert deps.informes.obtener_por_id(informe.id).versiones[0].contenido["encabezado"] == encabezado
