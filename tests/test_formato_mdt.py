"""Anexo 08, adaptación piloto: PostgreSQL loopback, nunca Supabase."""
from copy import deepcopy
import json
import os
from pathlib import Path
from time import perf_counter
from unittest.mock import Mock
from uuid import UUID, uuid4

import psycopg
import pytest

from src.adapters.out.ai.generador_borrador_ollama import GeneradorBorradorOllama
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.domain.value_objects.encabezado_documento import FORMATO_MDT
from src.infrastructure.dependencies import get_current_user
from tests.test_inspeccion_piloto import piloto, preparar_inspeccion, snapshot, db_local, script  # noqa: F401
from tests.test_piloto_v2 import leer_docx

pytestmark = pytest.mark.skipif(not os.getenv('NAXJI_TEST_PG_PORT'), reason='PostgreSQL aislado opt-in')
MIGRACION = 'database/migrations/20261001_03_formato_documento.sql'
SEMILLA = 'database/seeds/20261001_inspeccion_v2_anexo08.sql'

DATOS = {
    'estado_resultados': 'Información parcial por verificar',
    'lugar_inspeccion': 'Parque ficticio de prueba NAXJI, acceso norte',
    'fecha_inspeccion': '2026-09-30',
    'alcance_solicitado': 'Solo el entorno inmediato del acceso norte. No se inspeccionó el resto del parque.',
    'resultados_observados': 'Durante la visita de 10:20 a 10:40 se observaron dos bolsas cerradas junto al acceso norte. Ambas permanecían allí al terminar la observación. No se abrieron, pesaron ni identificó su contenido, origen o tiempo de permanencia. No se entrevistó a personas.',
    'referencias_conocidas': 'El solicitante describe la ficha ficticia F-01 y dos fotografías E-01 y E-02 del 2026-09-30. No están adjuntas; debe cotejarse su contenido antes de citarlas como evidencia verificada.',
    'informacion_pendiente': 'Confirmar ubicación y competencia territorial; obtener ficha y fotografías; verificar contenido, origen y permanencia de las bolsas.',
}


def instalar(db):
    with db.connect(autocommit=True) as c:
        script(c, MIGRACION)
        script(c, SEMILLA)


def test_migracion_y_semilla_idempotentes_preservan_plantillas_y_documentos(piloto):
    db = piloto[0][0]
    with db.connect(autocommit=True) as c:
        previos = c.execute('SELECT to_jsonb(p) FROM public.plantillas p ORDER BY id').fetchall()
        script(c, MIGRACION)
        assert c.execute("SELECT to_jsonb(p)-'formato_documento' FROM public.plantillas p ORDER BY id").fetchall() == previos
        antes = snapshot(c)
        script(c, SEMILLA)
        despues = snapshot(c)
        for tabla, filas in antes.items():
            if tabla in {'plantillas', 'campos_plantilla'}:
                assert all(f in despues[tabla] for f in filas)
            else:
                assert despues[tabla] == filas
        for _ in range(2):
            script(c, MIGRACION); script(c, SEMILLA)
            assert snapshot(c) == despues
        c.execute("UPDATE public.plantillas SET descripcion='Cambio local deliberado de prueba' WHERE formato_documento=%s", (FORMATO_MDT,))
        cambiado = snapshot(c)
        with pytest.raises(psycopg.errors.RaiseException):
            script(c, SEMILLA)
        assert snapshot(c) == cambiado


@pytest.mark.parametrize('con_resultados', [False, True])
@pytest.mark.parametrize('real', [False, pytest.param(True, marks=pytest.mark.skipif(os.getenv('NAXJI_RUN_OLLAMA_TESTS') != '1', reason='Ollama real opt-in'))])
def test_generacion_edicion_recuperacion_exportacion(piloto, tmp_path, con_resultados, real):
    (db, uid, _, iid_legacy, contenido_legacy), deps, client, app = piloto
    instalar(db)
    datos = DATOS if con_resultados else {'estado_resultados': 'Sin resultados de inspección'}
    asunto = 'PRUEBA NAXJI: inspección de bolsas con residuos en parque' if con_resultados else 'PRUEBA NAXJI: inspección de parque'
    sid, anterior, campos_v1, _, body = preparar_inspeccion(client, asunto=asunto, datos_fuente=datos)
    catalogo = client.get('/plantillas', params={'tipo_informe_id': anterior['tipo_informe_id']}).json()
    nueva = next(p for p in catalogo if p['nombre'] == anterior['nombre'] and p['version'] == 2)
    assert nueva['area_id'] == anterior['area_id'] and nueva['formato_documento'] == FORMATO_MDT
    campos = client.get(f"/plantillas/{nueva['id']}/campos").json()
    assert [{k:v for k,v in c.items() if k not in {'id','plantilla_id'}} for c in campos] == [{k:v for k,v in c.items() if k not in {'id','plantilla_id'}} for c in campos_v1]
    guardar = client.put(f'/solicitudes/{sid}/completa', json={**body, 'plantilla_id': nueva['id'],
        'valores': [{'campo_plantilla_id':c['id'], 'valor':datos[c['clave']]} for c in campos if c['clave'] in datos]})
    assert guardar.status_code == 200, guardar.text
    if real:
        generador = GeneradorBorradorOllama()
    else:
        texto = ('Según las observaciones aportadas, se observaron dos bolsas cerradas junto al acceso norte. Su contenido, origen y permanencia siguen pendientes de verificación.\nSe propone cotejar la ficha y las fotografías descritas antes de decidir medidas.'
                 if con_resultados else 'Pendiente de verificación: no se aportaron resultados sobre el parque. Se propone verificar ubicación y competencia y programar una visita si corresponde, para documentar observaciones.')
        generador = GeneradorBorradorOllama(Mock(model='qwen2.5:7b', generar=Mock(return_value=json.dumps({'cuerpo':texto}))))
    deps.generar_borrador.generador = generador
    inicio = perf_counter()
    respuesta = client.post(f'/solicitudes/{sid}/generar-borrador', json={})
    segundos = round(perf_counter()-inicio, 3)
    assert respuesta.status_code == 201, respuesta.text
    generado = respuesta.json(); iid = generado['informe_id']
    h = generado['contenido']['encabezado']
    assert h['formato_documento'] == FORMATO_MDT and h['documento']['destinatario'] == ''
    assert set(generado['contenido']) == {'cuerpo','encabezado'}
    assert generado['modelo_ia'] == 'qwen2.5:7b'
    texto = generado['contenido']['cuerpo'].lower()
    assert 'infantil' not in texto and 'no hay hallazgos confirmados' not in texto
    if con_resultados:
        assert ('dos bolsas' in texto or '2 bolsas' in texto) and 'cerradas' in texto
        assert 'bolsas con residuos' not in texto
        assert 'origen' in texto and 'contenido' in texto
    else:
        assert texto.startswith('pendiente de verificación:')
    contenido = deepcopy(generado['contenido'])
    contenido['cuerpo'] += '\nRevisión humana de prueba: obtener y cotejar las fuentes documentales antes de incorporarlas como anexos.'
    editado = client.put(f'/informes/{iid}', json={'numero_version':1, 'contenido':contenido,
        'encabezado_oficial': {'lugar_emision':'Lugar de prueba NAXJI', 'fecha':'2026-10-01'}})
    assert editado.status_code == 200, editado.text
    assert editado.json()['numero_version'] == 2
    recuperado = client.get(f'/solicitudes/{sid}/informe')
    assert recuperado.status_code == 200 and recuperado.json() == editado.json()
    assert client.get(f'/informes/{iid}/versiones/1').json()['contenido'] == generado['contenido']
    # El formato se conserva por versión, aunque el catálogo deje de anunciarlo.
    with db.connect() as c:
        c.execute('UPDATE public.plantillas SET formato_documento=NULL WHERE id=%s', (nueva['id'],))
    def prohibida(*args, **kwargs): raise AssertionError('Exportación llamó a Ollama')
    generador.generar = prohibida
    with db.connect() as c: antes = snapshot(c)
    descarga = client.get(f'/informes/{iid}/versiones/2/docx')
    doc = leer_docx(descarga)
    textos = '\n'.join(p.text for p in doc.paragraphs)
    assert contenido['cuerpo'] in textos
    assert 'INFORME N° [POR COMPLETAR]' in textos and str(uid) not in textos
    assert not any(p.style.name.startswith('Heading') for p in doc.paragraphs)
    assert 'De:' not in textos and 'Atentamente,' in textos
    assert 'Adjunto: [POR COMPLETAR]' in textos and 'Firma y sello: [POR COMPLETAR]' in textos
    assert '01 de octubre de 2026' in textos
    assert 'PILOTO NAXJI' in '\n'.join(p.text for p in doc.sections[0].header.paragraphs)
    assert round(doc.sections[0].top_margin.cm, 1) == 3.5
    assert round(doc.sections[0].left_margin.cm, 1) == 3
    with db.connect() as c: assert snapshot(c) == antes
    # Histórico anterior al paso 3 sigue siendo descargable y permanece intacto.
    assert client.get(f'/informes/{iid_legacy}/versiones/1').json()['contenido'] == contenido_legacy
    assert client.get(f'/informes/{iid_legacy}/versiones/1/docx').status_code == 200
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(uuid4(), frozenset({Rol.FUNCIONARIO}))
    assert client.get(f'/informes/{iid}/versiones/2/docx').status_code == 403
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(uid, frozenset({Rol.FUNCIONARIO}))
    # Una nueva instancia de repositorio lee exactamente lo guardado.
    from src.adapters.out.persistence.postgres import InformeRepositoryPostgres, PostgresUnidadTrabajo
    assert InformeRepositoryPostgres(PostgresUnidadTrabajo(db)).obtener_por_id(UUID(iid)).versiones[-1].contenido == editado.json()['contenido']
    destino = tmp_path
    if real and os.getenv('NAXJI_MDT_EVIDENCE_DIR'):
        destino = Path(os.environ['NAXJI_MDT_EVIDENCE_DIR']).resolve()
        assert destino.is_relative_to(Path(__file__).resolve().parents[1] / 'docs')
        destino.mkdir(parents=True, exist_ok=True)
    nombre = 'anexo08-con-observaciones' if con_resultados else 'anexo08-sin-resultados'
    (destino / (nombre+'.docx')).write_bytes(descarga.content)
    evidencia = {'entorno':'PostgreSQL aislado; identidad ficticia inyectada; no Supabase', 'ollama_real':real,
        'modelo':generado['modelo_ia'], 'segundos':segundos, 'datos_fuente':datos, 'asunto':asunto,
        'propuesta':generado, 'edicion':editado.json(), 'http':{'generacion':respuesta.status_code, 'edicion':editado.status_code, 'recuperacion':recuperado.status_code, 'descarga':descarga.status_code, 'descarga_ajena':403}}
    (destino/(nombre+'.json')).write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'caso':nombre, 'segundos':segundos, 'http':evidencia['http']}))
