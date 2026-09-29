"""Contratos de formulario completo y sugerencias, sin red."""
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from src.adapters.out.ai.context_predictor_catalogo import ContextPredictorCatalogo
from src.adapters.out.ai.context_predictor_mock import ContextPredictorMock
from src.adapters.out.persistence.datos_demo import TIPOS, AREAS
from src.domain.services.errores import DatosInvalidos


def formulario(client):
    p = client.get('/plantillas').json()[0]
    campos = client.get(f"/plantillas/{p['id']}/campos").json()
    area = p['area_id'] or client.get('/areas').json()[0]['id']
    return {'asunto': 'TEST formulario completo', 'tipo_informe_id': p['tipo_informe_id'],
            'plantilla_id': p['id'], 'area_origen_id': area, 'area_destino_id': area,
            'valores': [{'campo_plantilla_id': c['id'], 'valor': 'Datos de prueba'}
                        for c in campos if c['obligatorio']]}


def test_completa_creacion_actualizacion_y_rollback(client, deps):
    body = formulario(client)
    bad = {**body, 'valores': []}
    assert client.post('/solicitudes/completa', json=bad).status_code == 400
    assert not deps.memoria.solicitudes
    created = client.post('/solicitudes/completa', json=body)
    assert created.status_code == 201, created.text
    url = '/solicitudes/' + created.json()['id']
    original = client.get(url).json()
    assert client.put(url + '/completa', json={**bad, 'asunto': 'No debe quedar'}).status_code == 400
    assert client.get(url).json() == original
    assert client.put(url + '/completa', json={**body, 'asunto': 'Actualizado'}).status_code == 200
    client.headers['Authorization'] = 'Bearer demo-otro'
    assert client.put(url + '/completa', json=body).status_code == 403
    assert client.get(url + '/contexto').status_code == 403


@pytest.mark.parametrize('field', ['tipo_informe_id','plantilla_id','area_destino_id','area_origen_id'])
def test_completa_rechaza_referencias_desconocidas(client, deps, field):
    body = formulario(client)
    body[field] = str(uuid4())
    assert client.post('/solicitudes/completa', json=body).status_code == 404
    assert not deps.memoria.solicitudes


def test_completa_rechaza_campo_ajeno(client, deps):
    body = formulario(client)
    body['valores'].append({'campo_plantilla_id': str(uuid4()), 'valor': 'Ajeno'})
    assert client.post('/solicitudes/completa', json=body).status_code == 400
    assert not deps.memoria.solicitudes


def test_asunto_solo_y_recuperacion_contexto(client):
    r = client.post('/solicitudes', json={'asunto': 'Evaluación de parque'})
    url = '/solicitudes/' + r.json()['id']
    assert client.get(url + '/contexto').json() is None
    p = client.post(url + '/predecir-contexto')
    assert p.status_code == 200
    assert client.get(url + '/contexto').json() == p.json()
    assert client.post(url + '/generar-borrador', json={}).status_code == 409


def test_mapeo_mdt_sin_inventar_normativas_y_categoria_ausente():
    repo = Mock()
    repo.tipos_informe.return_value = [replace(t, id=uuid4()) for t in TIPOS]
    area = replace(AREAS[0], id=uuid4(), codigo='MDT_SGGA', nombre='Subgerencia de Gestión Ambiental')
    repo.areas.return_value = [area]
    repo.normativa_por_codigo.return_value = None
    adapter = ContextPredictorCatalogo(ContextPredictorMock(), repo)
    p = adapter.predecir('Evaluación parque', uuid4())
    assert p.area_destino_predicha_id == area.id
    assert not p.normativas
    assert p.parametros['advertencias_catalogo']
    repo.areas.return_value = [replace(area, activo=False)]
    with pytest.raises(DatosInvalidos, match='catálogo'):
        adapter.predecir('Evaluación parque', uuid4())
