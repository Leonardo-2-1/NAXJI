from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.domain.services.errores import ErrorGeneracion
from src.infrastructure.configuration.settings import Settings
from src.main import create_app


def flujo_hasta_generar(client):
    respuesta = client.post("/solicitudes", json={"asunto": "Evaluación de un parque"})
    assert respuesta.status_code == 201, respuesta.text
    sid = respuesta.json()["id"]
    assert client.get(f"/solicitudes/{sid}").status_code == 200
    prediccion = client.post(f"/solicitudes/{sid}/predecir-contexto")
    assert prediccion.status_code == 200, prediccion.text
    p = prediccion.json()
    assert p["es_mock"] is True
    assert 0 <= p["tipo_informe"]["confianza"] <= 1
    validar = client.post(f"/solicitudes/{sid}/validar-prediccion",
                          json={"prediccion_id": p["id"], "resultado": "ACEPTADA"})
    assert validar.status_code == 200, validar.text
    plantillas = client.get("/plantillas", params={"tipo_informe_id": p["tipo_informe"]["id"]}).json()
    plantilla = plantillas[0]
    assert client.put(f"/solicitudes/{sid}", json={"plantilla_id": plantilla["id"]}).status_code == 200
    campos = client.get(f"/plantillas/{plantilla['id']}/campos").json()
    valores = [{"campo_plantilla_id": c["id"], "valor": f"Datos de {c['clave']}"}
               for c in campos if c["obligatorio"]]
    guardar = client.put(f"/solicitudes/{sid}/valores", json={"valores": valores})
    assert guardar.status_code == 200, guardar.text
    assert guardar.json()["estado"] == "LISTA_PARA_GENERAR"
    return sid


def test_flujo_completo_swagger_y_catalogos(client):
    assert client.get("/health").json() == {"status": "ok", "service": "NAXJI API"}
    assert client.get("/docs").status_code == 200
    assert len(client.get("/tipos-informe").json()) == 4
    assert len(client.get("/areas").json()) == 6
    assert client.get("/auth/me").json()["roles"] == ["FUNCIONARIO"]
    schema = client.get("/openapi.json").json()
    assert "/solicitudes/{solicitud_id}/validar-prediccion" in schema["paths"]
    assert "HTTPBearer" in schema["components"]["securitySchemes"]
    sid = flujo_hasta_generar(client)
    r = client.post(f"/solicitudes/{sid}/generar-borrador", json={"instrucciones": "Sea breve"})
    assert r.status_code == 201, r.text
    informe = r.json()
    assert informe["estado"] == "BORRADOR"
    assert informe["modelo_ia"].startswith("MOCK_")
    assert {s["clave"] for s in informe["secciones_salida"]} == set(informe["contenido"]) - {"encabezado"}
    assert client.get(f"/solicitudes/{sid}").json()["estado"] == "GENERADA"
    iid = informe["informe_id"]
    contenido = {**informe["contenido"], "conclusiones": "Revisión del funcionario"}
    editado = client.put(f"/informes/{iid}", json={"contenido": contenido, "numero_version": 1})
    assert editado.status_code == 200, editado.text
    assert editado.json()["numero_version"] == 2
    assert client.get(f"/informes/{iid}").json()["contenido"] == contenido
    assert client.put(f"/informes/{iid}", json={"contenido": contenido, "numero_version": 1}).status_code == 409
    assert client.post(f"/solicitudes/{sid}/generar-borrador", json={}).status_code == 409
    assert client.put(f"/solicitudes/{sid}", json={"asunto": "Cambio"}).status_code == 409


@pytest.mark.parametrize("body", [
    {}, {"asunto": "   "}, {"asunto": "Texto", "plantilla_id": "no-uuid"},
    {"asunto": "Texto", "usuario_id": str(uuid4())},
    {"asunto": "Texto", "estado": "GENERADA"},
    {"asunto": "Texto", "descripcion": "Campo antiguo"},
])
def test_validaciones_request(client, body):
    assert client.post("/solicitudes", json=body).status_code == 422


def test_errores_401_403_404_409_422(client):
    client.headers.pop("Authorization")
    assert client.get("/health").status_code == 200
    assert client.get("/areas").status_code == 401
    client.headers["Authorization"] = "Bearer invalido"
    assert client.get("/auth/me").status_code == 401
    client.headers["Authorization"] = "Bearer demo-revisor"
    assert client.post("/solicitudes", json={"asunto": "Asunto"}).status_code == 403
    client.headers["Authorization"] = "Bearer demo-funcionario"
    assert client.get(f"/solicitudes/{uuid4()}").status_code == 404
    assert client.get(f"/informes/{uuid4()}").status_code == 404
    assert client.get("/solicitudes/no-uuid").status_code == 422
    sid = client.post("/solicitudes", json={"asunto": "Asunto"}).json()["id"]
    assert client.put(f"/solicitudes/{sid}", json={"estado": "GENERADA"}).status_code == 409
    assert client.put(f"/solicitudes/{sid}", json={"estado": "PENDIENTE"}).status_code == 422
    assert client.put(f"/solicitudes/{sid}", json={"asunto": None}).status_code == 422
    client.headers["Authorization"] = "Bearer demo-otro"
    assert client.get(f"/solicitudes/{sid}").status_code == 403
    assert client.put(f"/solicitudes/{sid}", json={"asunto": "Acceso ajeno"}).status_code == 403


def test_informe_de_otro_usuario_y_campos_obligatorios(client):
    sid = flujo_hasta_generar(client)
    iid = client.post(f"/solicitudes/{sid}/generar-borrador", json={}).json()["informe_id"]
    assert client.put(f"/informes/{iid}", json={"contenido": {}, "numero_version": 1}).status_code == 400
    client.headers["Authorization"] = "Bearer demo-otro"
    assert client.get(f"/informes/{iid}").status_code == 403


def test_fallo_generador_devuelve_500_sin_detalles_y_permite_reintentar(client, deps):
    sid = flujo_hasta_generar(client)
    generador = deps.generar_borrador.generador
    original = generador.generar
    def fallar(*args, **kwargs):
        raise ErrorGeneracion("Detalle privado del proveedor")
    generador.generar = fallar
    respuesta = client.post(f"/solicitudes/{sid}/generar-borrador", json={})
    assert respuesta.status_code == 500
    assert "privado" not in respuesta.text
    assert client.get(f"/solicitudes/{sid}").json()["estado"] == "LISTA_PARA_GENERAR"
    generador.generar = original
    assert client.post(f"/solicitudes/{sid}/generar-borrador", json={}).status_code == 201


def test_error_no_controlado_no_expone_detalles(client, deps):
    def fallar(*args):
        raise RuntimeError("Información interna")
    deps.consultar_catalogos.areas = fallar
    respuesta = client.get("/areas")
    assert respuesta.status_code == 500
    assert respuesta.json() == {"detail": "Error interno del servidor"}


def test_modo_disabled_no_acepta_tokens_demo():
    with TestClient(create_app(Settings(auth_mode="disabled"))) as client:
        assert client.get("/areas", headers={"Authorization": "Bearer demo-funcionario"}).status_code == 401


def test_cors_configurable_y_memoria_aislada(client):
    with TestClient(create_app(Settings(cors_origins=("http://localhost:5173",)))) as otro:
        response = otro.options("/solicitudes", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        })
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        sid = client.post("/solicitudes", json={"asunto": "Local"}).json()["id"]
        assert otro.get(f"/solicitudes/{sid}", headers={"Authorization": "Bearer demo-funcionario"}).status_code == 404
