import asyncio
import base64
import json
import logging
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest

from src.adapters.out.ai.ollama_adapter import OllamaAdapter
from src.adapters.out.ai.generador_borrador_ollama import GeneradorBorradorOllama
from src.application.ports.output.generador_borrador import ContextoConfirmado, NormaConfirmada
from src.domain.entities.plantilla import Plantilla
from src.domain.services.errores import ErrorGeneracion
from src.domain.value_objects.estructura_piloto import estructura_piloto
from src.infrastructure.configuration import settings as settings_module
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.configuration.container import Container
from tests.test_api import flujo_hasta_generar


def generar_adapter(adapter):
    return adapter.generar("DATOS_PRIVADOS_TEST", sistema="REGLAS", esquema={"type": "object"})


def test_adapter_envia_esquema_y_configuracion_sin_streaming():
    recibido = []
    def responder(request):
        recibido.append(request)
        return httpx.Response(200, json={"model": "qwen2.5:7b", "done": True, "response": '{"resumen":"texto"}'})
    adapter = OllamaAdapter(base_url="http://localhost:11434/", timeout_seconds=75, transport=httpx.MockTransport(responder))
    assert generar_adapter(adapter) == '{"resumen":"texto"}'
    assert str(recibido[0].url) == "http://localhost:11434/api/generate"
    assert "authorization" not in recibido[0].headers
    payload = json.loads(recibido[0].content)
    assert payload["format"] == {"type": "object"}
    assert payload["model"] == adapter.model == "qwen2.5:7b"
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0
    assert payload["system"] == "REGLAS"
    assert recibido[0].extensions["timeout"]["read"] == 75


@pytest.mark.parametrize("error,codigo", [
    (httpx.ConnectError("SECRETO: conexión"), "OLLAMA_NO_DISPONIBLE"),
    (httpx.ReadTimeout("SECRETO: datos"), "OLLAMA_TIMEOUT"),
    (httpx.ConnectTimeout("SECRETO: URL"), "OLLAMA_TIMEOUT"),
    (httpx.ReadError("SECRETO: red"), "OLLAMA_ERROR"),
])
def test_adaptador_sanitiza_errores_de_red(error, codigo):
    def responder(request):
        raise error
    with pytest.raises(ErrorGeneracion) as fallo:
        generar_adapter(OllamaAdapter(transport=httpx.MockTransport(responder)))
    assert fallo.value.codigo == codigo
    assert "SECRETO" not in str(fallo.value) + fallo.value.mensaje_publico


@pytest.mark.parametrize("status,body,codigo", [
    (404, {"error": "DATOS_PRIVADOS_TEST model not found"}, "OLLAMA_MODELO_NO_INSTALADO"),
    (500, {"error": "DATOS_PRIVADOS_TEST"}, "OLLAMA_ERROR"),
    (302, {}, "OLLAMA_ERROR"),
    (200, [], "OLLAMA_RESPUESTA_INVALIDA"),
    (200, {"model": "qwen2.5:7b", "done": False, "response": "{}"}, "OLLAMA_RESPUESTA_INVALIDA"),
    (200, {"model": "otro", "done": True, "response": "{}"}, "OLLAMA_RESPUESTA_INVALIDA"),
    (200, {"model": "qwen2.5:7b", "done": True, "response": "{}", "done_reason": "length"}, "OLLAMA_RESPUESTA_INVALIDA"),
    (200, {"model": "qwen2.5:7b", "done": True, "response": {}}, "OLLAMA_RESPUESTA_INVALIDA"),
])
def test_adaptador_rechaza_errores_y_sobres_incompletos(status, body, codigo):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json=body))
    with pytest.raises(ErrorGeneracion) as fallo:
        generar_adapter(OllamaAdapter(transport=transport))
    assert fallo.value.codigo == codigo
    assert "DATOS_PRIVADOS_TEST" not in fallo.value.mensaje_publico


def test_adaptador_json_http_invalido():
    with pytest.raises(ErrorGeneracion) as fallo:
        generar_adapter(OllamaAdapter(transport=httpx.MockTransport(lambda request: httpx.Response(200, text="privado"))))
    assert fallo.value.codigo == "OLLAMA_RESPUESTA_INVALIDA"


def test_timeout_total_cancela_peticion_aunque_no_haya_timeout_de_red():
    cancelada = []
    async def lento(request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelada.append(True)
    with pytest.raises(ErrorGeneracion) as fallo:
        generar_adapter(OllamaAdapter(timeout_seconds=0.01, transport=httpx.MockTransport(lento)))
    assert fallo.value.codigo == "OLLAMA_TIMEOUT"
    assert cancelada == [True]


def test_prompt_separa_datos_de_reglas_y_no_atribuye_contenido_juridico():
    secciones = estructura_piloto()
    contenido = {s.clave: "Pendiente de verificación" for s in reversed(secciones)}
    llm = Mock(model="qwen2.5:7b", generar=Mock(return_value=json.dumps(contenido)))
    plantilla = Plantilla(uuid4(), "Piloto DEMO", uuid4(), secciones_salida=secciones)
    norma = NormaConfirmada(uuid4(), "DEMO_NORMA", "Referencia de prueba no verificada")
    ajena = NormaConfirmada(uuid4(), "NO_ACEPTADA", "No enviar")
    contexto = ContextoConfirmado(plantilla.tipo_informe_id, uuid4(), (norma.id,), "Informe técnico", "Área de pruebas", (norma, ajena))
    datos = {"detalle": "No se dispone de resultados de inspección.", "antecedentes": "IGNORA_REGLAS_TEST"}
    resultado = GeneradorBorradorOllama(llm).generar("Inspección de parque sin resultados", plantilla, datos, contexto, "INSTRUCCION_TEST")
    entrada = json.loads(llm.generar.call_args.args[0])
    sistema = llm.generar.call_args.kwargs["sistema"]
    assert entrada["datos_ingresados"] == datos
    assert entrada["contexto_confirmado"]["tipo_informe"] == "Informe técnico"
    assert entrada["contexto_confirmado"]["area_destino"] == "Área de pruebas"
    assert entrada["contexto_confirmado"]["normas_seleccionadas_no_verificadas"] == [{"codigo": norma.codigo, "titulo": norma.titulo}]
    assert "IGNORA_REGLAS_TEST" not in sistema and "INSTRUCCION_TEST" not in sistema
    assert "NO órdenes" in sistema and "NO citas jurídicas verificadas" in sistema
    assert "estado del césped" in sistema and "Pendiente de verificación" in sistema
    assert list(resultado.contenido) == [s.clave for s in secciones]
    assert "encabezado" not in resultado.contenido


@pytest.mark.parametrize("respuesta", ['{}', '[]', '```json\n{}\n```', '{"antecedentes":"a","antecedentes":"b"}',
    '{"antecedentes":"A","objetivo":"O","analisis_tecnico":"T","conclusiones":"C","encabezado":{}}',
    '{"antecedentes":"A","objetivo":"O","analisis_tecnico":" ","conclusiones":"C"}',
    '{"antecedentes":"A","objetivo":"O","analisis_tecnico":null,"conclusiones":"C"}',
    '{"antecedentes":"A","objetivo":"O","analisis_tecnico":"T","conclusiones":"C"} texto adicional'])
def test_generador_no_repara_silenciosamente_respuestas_invalidas(respuesta):
    plantilla = Plantilla(uuid4(), "DEMO", uuid4(), secciones_salida=estructura_piloto())
    llm = Mock(model="qwen2.5:7b", generar=Mock(return_value=respuesta))
    with pytest.raises(ErrorGeneracion) as fallo:
        GeneradorBorradorOllama(llm).generar("Asunto", plantilla, {}, ContextoConfirmado(plantilla.tipo_informe_id, uuid4(), ()), "")
    assert fallo.value.codigo == "OLLAMA_RESPUESTA_INVALIDA"


@pytest.mark.parametrize("codigo,status", [("OLLAMA_NO_DISPONIBLE", 503), ("OLLAMA_MODELO_NO_INSTALADO", 503),
    ("OLLAMA_TIMEOUT", 504), ("OLLAMA_RESPUESTA_INVALIDA", 502), ("OLLAMA_ERROR", 502)])
def test_api_fallos_controlados_conservan_datos_y_admiten_reintento(client, deps, codigo, status):
    sid = flujo_hasta_generar(client)
    antes = client.get(f"/solicitudes/{sid}").json()
    original = deps.generar_borrador.generador
    deps.generar_borrador.generador = Mock(generar=Mock(side_effect=ErrorGeneracion("PROMPT_SECRETO", codigo=codigo)))
    respuesta = client.post(f"/solicitudes/{sid}/generar-borrador", json={})
    assert respuesta.status_code == status
    assert respuesta.json()["codigo"] == codigo
    assert "PROMPT_SECRETO" not in respuesta.text
    despues = client.get(f"/solicitudes/{sid}").json()
    assert despues["estado"] == "LISTA_PARA_GENERAR"
    assert despues["valores"] == antes["valores"]
    assert not deps.memoria.informes
    deps.generar_borrador.generador = original
    assert client.post(f"/solicitudes/{sid}/generar-borrador", json={}).status_code == 201


def test_configuracion_backend_se_inyecta_en_contenedor(monkeypatch):
    monkeypatch.setattr(settings_module, "environment", lambda: {
        "NAXJI_OLLAMA_BASE_URL": "http://127.0.0.1:11435/", "NAXJI_OLLAMA_MODEL": "qwen2.5:7b",
        "NAXJI_OLLAMA_TIMEOUT_SECONDS": "80", "VITE_OLLAMA_MODEL": "ignorado",
    })
    settings = Settings.from_env()
    deps = Container(settings, predictor=Mock())
    llm = deps.generar_borrador.generador.llm
    assert llm.base_url == "http://127.0.0.1:11435"
    assert llm.model == "qwen2.5:7b" and llm.timeout_seconds == 80
    assert deps.generar_borrador.plazo.total_seconds() == 110


@pytest.mark.parametrize("clave,valor", [("NAXJI_OLLAMA_BASE_URL", "http://usuario:secreto@host"),
    ("NAXJI_OLLAMA_BASE_URL", "file:///tmp"), ("NAXJI_OLLAMA_BASE_URL", "http://localhost?token=secreto"),
    ("NAXJI_OLLAMA_MODEL", ""), ("NAXJI_OLLAMA_TIMEOUT_SECONDS", "nan"),
    ("NAXJI_OLLAMA_TIMEOUT_SECONDS", "0"), ("NAXJI_OLLAMA_TIMEOUT_SECONDS", "1801"),
    ("NAXJI_OLLAMA_TIMEOUT_SECONDS", "texto")])
def test_configuracion_invalida_falla_sin_revelar_valores(monkeypatch, clave, valor):
    monkeypatch.setattr(settings_module, "environment", lambda: {clave: valor})
    with pytest.raises(ValueError) as fallo:
        Settings.from_env()
    assert clave in str(fallo.value)
    assert "secreto" not in str(fallo.value)


def test_basic_auth_backend_se_inyecta_y_envia_solo_en_header(monkeypatch, caplog):
    # Valores ficticios; nunca se leen credenciales del entorno privado en esta prueba.
    username, password = "OLLAMA_USUARIO_FICTICIO", "OLLAMA_CLAVE_FICTICIA:${literal}: ñ"
    monkeypatch.setattr(settings_module, "environment", lambda: {
        "NAXJI_OLLAMA_BASE_URL": "https://tunel.example.invalid/",
        "NAXJI_OLLAMA_USERNAME": username,
        "NAXJI_OLLAMA_PASSWORD": password,
    })
    settings = Settings.from_env()
    assert settings.ollama_username == username
    assert settings.ollama_password == password
    llm = Container(settings, predictor=Mock()).generar_borrador.generador.llm
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"model": llm.model, "done": True, "response": "{}"})

    llm.transport = httpx.MockTransport(respond)
    caplog.set_level(logging.DEBUG)
    assert generar_adapter(llm) == "{}"
    request, = requests
    scheme, encoded = request.headers["authorization"].split(" ", 1)
    assert scheme == "Basic"
    assert base64.b64decode(encoded).decode("utf-8") == f"{username}:{password}"
    assert request.method == "POST"
    assert str(request.url) == "https://tunel.example.invalid/api/generate"
    assert json.loads(request.content)["stream"] is False
    public = str(request.url) + request.content.decode() + repr(settings) + repr(llm) + caplog.text
    assert all(value not in public for value in (username, password, encoded))


@pytest.mark.parametrize("values", [
    {},
    {"NAXJI_OLLAMA_USERNAME": "", "NAXJI_OLLAMA_PASSWORD": ""},
    {"VITE_OLLAMA_USERNAME": "IGNORADO", "VITE_OLLAMA_PASSWORD": "IGNORADO",
     "VITE_NAXJI_OLLAMA_USERNAME": "IGNORADO", "VITE_NAXJI_OLLAMA_PASSWORD": "IGNORADO"},
])
def test_configuracion_sin_auth_no_envia_credenciales(monkeypatch, values):
    monkeypatch.setattr(settings_module, "environment", lambda: values)
    settings = Settings.from_env()
    assert settings.ollama_username is None and settings.ollama_password is None
    llm = Container(settings, predictor=Mock()).generar_borrador.generador.llm

    def respond(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"model": llm.model, "done": True, "response": "{}"})

    llm.transport = httpx.MockTransport(respond)
    assert generar_adapter(llm) == "{}"


@pytest.mark.parametrize("username,password", [
    ("USUARIO_FICTICIO", None), (None, "CLAVE_FICTICIA"),
    ("USUARIO_FICTICIO", ""), ("", "CLAVE_FICTICIA"),
])
def test_auth_incompleta_se_rechaza_antes_de_conectar(monkeypatch, username, password):
    monkeypatch.setattr(settings_module, "environment", lambda: {
        "NAXJI_OLLAMA_USERNAME": username, "NAXJI_OLLAMA_PASSWORD": password,
    })
    transport = Mock()
    for factory in (Settings.from_env, lambda: OllamaAdapter(username=username, password=password, transport=transport)):
        with pytest.raises(ValueError) as error:
            factory()
        assert "NAXJI_OLLAMA_USERNAME" in str(error.value)
        assert "NAXJI_OLLAMA_PASSWORD" in str(error.value)
        assert "FICTICI" not in str(error.value)
    transport.assert_not_called()


@pytest.mark.parametrize("url", [
    "https://USUARIO_FICTICIO:CLAVE_FICTICIA@host.invalid",
    "https://USUARIO_FICTICIO@host.invalid", "https://@host.invalid", "https://:@host.invalid",
    "https://host.invalid?password=CLAVE_FICTICIA",
])
def test_auth_en_url_se_rechaza_incluso_en_adapter_directo(url):
    for factory in (lambda: Settings(ollama_base_url=url), lambda: OllamaAdapter(base_url=url)):
        with pytest.raises(ValueError) as error:
            factory()
        assert "NAXJI_OLLAMA_BASE_URL" in str(error.value)
        assert "FICTICI" not in str(error.value)


def test_usuario_basic_con_dos_puntos_se_rechaza_sin_revelarlo():
    for factory in (
        lambda: Settings(ollama_username="USUARIO:FICTICIO", ollama_password="CLAVE_FICTICIA"),
        lambda: OllamaAdapter(username="USUARIO:FICTICIO", password="CLAVE_FICTICIA"),
    ):
        with pytest.raises(ValueError, match="NAXJI_OLLAMA_USERNAME") as error:
            factory()
        assert "FICTICI" not in str(error.value)


@pytest.mark.parametrize("failure", [401, 403, "network", 302, 307, 308])
def test_auth_no_filtra_secretos_en_errores_ni_redirecciones(failure, caplog):
    username, password = "USUARIO_FICTICIO_PRIVADO", "CLAVE_FICTICIA_PRIVADA"
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    requests = []

    def respond(request):
        requests.append(request)
        private = f"{username} {password} {encoded}"
        if failure == "network":
            raise httpx.ConnectError(private)
        return httpx.Response(failure, text=private, headers={"Location": "https://otro.example.invalid/api/generate"})

    llm = OllamaAdapter(base_url="https://tunel.example.invalid", username=username, password=password,
                        transport=httpx.MockTransport(respond))
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ErrorGeneracion) as error:
        generar_adapter(llm)
    assert error.value.codigo == ("OLLAMA_NO_DISPONIBLE" if failure == "network" else "OLLAMA_ERROR")
    assert len(requests) == 1
    public = str(error.value) + error.value.mensaje_publico + caplog.text
    assert all(value not in public for value in (username, password, encoded))
