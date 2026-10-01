from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from joblib import load
import pytest

from src.adapters.out.ai.context_predictor_catalogo import ContextPredictorCatalogo
from src.adapters.out.ai.context_predictor_mock import ContextPredictorMock
from src.adapters.out.ai.generador_borrador_ollama import GeneradorBorradorOllama
from src.adapters.out.persistence.catalogo_repository_memory import CatalogoRepositoryMemory
from src.adapters.out.persistence.datos_demo import NORMATIVAS
from src.domain.entities.prediccion_contexto import NormativaPredicha
from tests.fixtures.normativa_demo import correspondencia_demo


def repo_demo(correspondencias):
    return CatalogoRepositoryMemory(normativas=[c.normativa for c in correspondencias], correspondencias=correspondencias)


def instalar(deps, correspondencias):
    repo = repo_demo(correspondencias)
    deps.catalogos = deps.servicios.catalogos = repo
    deps.predecir_contexto.predictor = ContextPredictorCatalogo(ContextPredictorMock(), repo)
    return repo


def preparar(client):
    sid = client.post('/solicitudes', json={'asunto': 'DEMO: inspección pendiente sin resultados'}).json()['id']
    url = f'/solicitudes/{sid}'
    p = client.post(url + '/predecir-contexto').json()
    return url, p


def confirmar(client, url, p, ids):
    return client.post(url + '/validar-prediccion', json={
        'prediccion_id': p['id'], 'resultado': 'CORREGIDA',
        'tipo_informe_id': p['tipo_informe']['id'], 'area_destino_id': p['area_destino']['id'], 'normativa_ids': ids})


def campos(client, url, p):
    plantilla = client.get('/plantillas', params={'tipo_informe_id': p['tipo_informe']['id']}).json()[0]
    client.put(url, json={'plantilla_id': plantilla['id']})
    campos = client.get(f"/plantillas/{plantilla['id']}/campos").json()
    assert client.put(url + '/valores', json={'valores': [{'campo_plantilla_id': c['id'],
        'valor': 'No hay resultados de inspección; pendiente de verificación.'} for c in campos if c['obligatorio']]}).status_code == 200


def test_etiquetas_coinciden_con_artefacto_entrenado_sin_modificarlo():
    modelo = Path('src/infrastructure/ai/models/mlb.joblib')
    assert set(load(modelo).classes_) == {n.titulo for n in NORMATIVAS}


def test_sin_correspondencia_no_convierte_etiqueta_en_documento():
    # Incluso si el catálogo contiene un código idéntico al del modelo.
    repo = CatalogoRepositoryMemory()
    p = ContextPredictorCatalogo(ContextPredictorMock(), repo).predecir('DEMO', uuid4())
    assert p.normativas == []
    assert p.parametros['temas_normativos'][0]['codigo'] == 'NORM_RESIDUOS'
    assert not p.parametros['temas_normativos'][0]['normativa_ids']
    assert any('No existe una norma verificable' in aviso for aviso in p.parametros['advertencias_catalogo'])


@pytest.mark.parametrize('cantidad', [1, 2])
def test_una_etiqueta_resuelve_una_o_varias_normas(cantidad):
    asociaciones = [correspondencia_demo(str(i)) for i in range(cantidad)]
    p = ContextPredictorCatalogo(ContextPredictorMock(), repo_demo(asociaciones)).predecir('DEMO', uuid4())
    assert [n.normativa_id for n in p.normativas] == [c.normativa.id for c in asociaciones]
    assert [n.orden for n in p.normativas] == list(range(1, cantidad+1))
    assert all(n.aceptada is None and n.confianza == 0.82 for n in p.normativas)


def test_dos_temas_mismo_documento_conserva_procedencia_sin_duplicar():
    primera = correspondencia_demo()
    segunda = replace(primera, etiqueta='NORM_RUIDO')
    raw = ContextPredictorMock().predecir('DEMO', uuid4())
    raw.normativas.append(NormativaPredicha(NORMATIVAS[1].id, 0.7, 2))
    predictor = Mock(predecir=Mock(return_value=raw))
    p = ContextPredictorCatalogo(predictor, repo_demo([primera, segunda])).predecir('DEMO', raw.solicitud_id)
    assert len(p.normativas) == 1 and p.normativas[0].confianza == 0.82
    assert len(p.parametros['correspondencias_normativas'][str(primera.normativa.id)]) == 2


@pytest.mark.parametrize('cambios', [{'estado_verificacion': 'PENDIENTE'}, {'activa': False},
    {'vigencia': 'NO_VIGENTE'}, {'fuente_url': 'https://example.com/'}, {'fuente_url': 'javascript:alert(1)'},
    {'ambito': ''}, {'verificado_en': date.today()+timedelta(days=1)}])
def test_rechaza_curacion_incompleta_inactiva_o_fuente_ajena(cambios):
    c = replace(correspondencia_demo(), **cambios)
    p = ContextPredictorCatalogo(ContextPredictorMock(), repo_demo([c])).predecir('DEMO', uuid4())
    assert not p.normativas


def test_norma_caducada_o_sin_identidad_no_se_propone():
    c = correspondencia_demo()
    for n in [replace(c.normativa, fecha_fin_vigencia=date(2001, 1, 1)), replace(c.normativa, numero=None),
              replace(c.normativa, activo=False)]:
        assert not replace(c, normativa=n).elegible()


def test_descartar_recuperar_y_generar_sin_citas_inventadas(client, deps):
    a, b = correspondencia_demo('A'), correspondencia_demo('B')
    instalar(deps, [a, b])
    url, p = preparar(client)
    assert len(p['normativas']) == 2 and p['temas_normativos'][0]['confianza'] == 0.82
    assert confirmar(client, url, p, [str(b.normativa.id)]).status_code == 200
    recovered = client.get(url + '/contexto').json()
    assert [n['aceptada'] for n in recovered['normativas']] == [False, True]
    assert recovered['normativas'][1]['correspondencias'] == p['normativas'][1]['correspondencias']
    campos(client, url, p)
    # Adaptador Ollama con respuesta simulada: no requiere servicio externo.
    llm = Mock(model='qwen2.5:7b', generar=Mock(return_value=json.dumps({
        k: 'Pendiente de verificación; no hay resultados de inspección.' for k in ('antecedentes','desarrollo','conclusiones')})))
    deps.generar_borrador.generador = GeneradorBorradorOllama(llm)
    generated = client.post(url + '/generar-borrador', json={})
    assert generated.status_code == 201, generated.text
    prompt = json.loads(llm.generar.call_args.args[0])
    assert prompt['contexto_confirmado']['normas_seleccionadas_no_verificadas'] == [
        {'codigo': b.normativa.codigo, 'titulo': b.normativa.titulo}]
    rules = llm.generar.call_args.kwargs['sistema']
    assert 'NO citas jurídicas verificadas' in rules and 'no atribuyas artículos' in rules
    assert 'artículo' not in json.dumps(generated.json()['contenido'], ensure_ascii=False).lower()


def test_aceptada_confirma_todas_y_rechaza_norma_externa(client, deps):
    instalar(deps, [correspondencia_demo('A'), correspondencia_demo('B')])
    url, p = preparar(client)
    assert confirmar(client, url, p, [str(uuid4())]).status_code == 400
    r = client.post(url+'/validar-prediccion', json={'prediccion_id':p['id'], 'resultado':'ACEPTADA'})
    assert r.status_code == 200 and all(n['aceptada'] for n in r.json()['normativas'])


def test_revocar_correspondencia_impide_confirmar_o_generar_pero_no_leer(client, deps):
    c = correspondencia_demo()
    repo = instalar(deps, [c])
    url, p = preparar(client)
    repo.correspondencias = [replace(c, activa=False)]
    assert confirmar(client, url, p, [str(c.normativa.id)]).status_code == 400
    repo.correspondencias = [c]
    assert confirmar(client, url, p, [str(c.normativa.id)]).status_code == 200
    campos(client, url, p)
    repo.correspondencias = [replace(c, normativa=replace(c.normativa, titulo='Otro documento'))]
    assert client.get(url+'/contexto').status_code == 200
    assert client.post(url+'/generar-borrador', json={}).status_code == 400
    assert not deps.memoria.informes


def test_retiro_durante_inferencia_no_guarda_documento_y_permite_reintentar(client, deps):
    c = correspondencia_demo()
    repo = instalar(deps, [c])
    url, p = preparar(client)
    assert confirmar(client, url, p, [str(c.normativa.id)]).status_code == 200
    campos(client, url, p)
    original = deps.generar_borrador.generador
    def generar(*args):
        repo.correspondencias = [replace(c, activa=False)]
        return original.generar(*args)
    deps.generar_borrador.generador = Mock(generar=generar)
    assert client.post(url+'/generar-borrador', json={}).status_code == 400
    assert not deps.memoria.informes
    assert client.get(url).json()['estado'] == 'LISTA_PARA_GENERAR'
    # El funcionario aún puede descartar la referencia retirada.
    assert confirmar(client, url, p, []).status_code == 200
    deps.generar_borrador.generador = original
    assert client.post(url+'/generar-borrador', json={}).status_code == 201
