"""SQL exclusivamente en la base efímera loopback de db_local; nunca Supabase."""
import json
import os
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg import sql
import pytest

from src.adapters.out.ai.context_predictor_mock import ContextPredictorMock
from src.adapters.out.ai.generador_borrador_mock import GeneradorBorradorMock
from src.adapters.out.persistence.postgres import CatalogoRepositoryPostgres, PostgresUnidadTrabajo
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.dependencies import get_current_user
from src.main import create_app
from fastapi.testclient import TestClient
from tests.test_estructura_postgres import db_local, script  # noqa: F401
from tests.fixtures.normativa_demo import correspondencia_demo


pytestmark = pytest.mark.skipif(not os.getenv('NAXJI_TEST_PG_PORT'), reason='Solo PostgreSQL local aislado')
MIGRATION = 'database/migrations/20261001_01_correspondencias_normativas.sql'
SEED = 'database/seeds/20261001_referencias_residuos_verificadas.sql'


def snapshot(c, tabla):
    return c.execute(sql.SQL('SELECT to_jsonb(t) FROM public.{} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(tabla))).fetchall()


def test_migracion_aditiva_idempotente_semilla_y_compatibilidad(db_local):
    settings, _, _, iid, contenido = db_local
    repo = CatalogoRepositoryPostgres(PostgresUnidadTrabajo(settings))
    assert repo.correspondencias_normativas(['NORM_RESIDUOS']) == []  # Antes de migrar.
    with settings.connect(autocommit=True) as c:
        tablas = [r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")]
        before = {t:snapshot(c,t) for t in tablas}
        script(c, MIGRATION)
        script(c, MIGRATION)
        assert {t:snapshot(c,t) for t in tablas} == before
        assert c.execute("SELECT relrowsecurity FROM pg_class WHERE oid='public.normativa_correspondencias'::regclass").fetchone()[0]
        assert not c.execute("SELECT 1 FROM pg_class t, LATERAL aclexplode(t.relacl) a WHERE t.oid='public.normativa_correspondencias'::regclass AND a.grantee=0").fetchall()
        script(c, SEED)
        saved = {t:snapshot(c,t) for t in ('normativas','normativa_correspondencias')}
        script(c, SEED)
        assert {t:snapshot(c,t) for t in saved} == saved
        assert c.execute('SELECT contenido FROM public.versiones_informe WHERE informe_id=%s', (iid,)).fetchone()[0] == contenido
        assert c.execute("SELECT COUNT(*) FROM public.normativa_correspondencias").fetchone()[0] == 2
        assert c.execute("SELECT COUNT(*) FROM public.normativas WHERE codigo LIKE 'NORM_%%'").fetchone()[0] == 0
    mapped = repo.correspondencias_normativas(['NORM_RESIDUOS'])
    assert {r.normativa.codigo for r in mapped} == {'PE_DL_1278','PE_DS_014_2017_MINAM'}
    assert all(r.elegible() for r in mapped)
    assert all(isinstance(r.normativa.id, UUID) for r in mapped)
    assert repo.correspondencias_normativas(['NORM_RUIDO']) == []
    with settings.connect(autocommit=True) as c:
        c.execute('UPDATE public.normativa_correspondencias SET activa=false')
        script(c, SEED)
    assert not any(r.elegible() for r in repo.correspondencias_normativas(['NORM_RESIDUOS']))


def test_sql_rechaza_verificacion_incompleta_y_semilla_no_sobrescribe(db_local):
    settings = db_local[0]
    with settings.connect(autocommit=True) as c:
        script(c, MIGRATION)
        nid = c.execute('SELECT id FROM public.normativas LIMIT 1').fetchone()[0]
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("INSERT INTO public.normativa_correspondencias(etiqueta,normativa_id,estado_verificacion) VALUES ('NORM_RESIDUOS',%s,'VERIFICADA')", (nid,))
        c.execute("INSERT INTO public.normativas(codigo,titulo,tipo) VALUES ('PE_DS_014_2017_MINAM','CONFLICTO FICTICIO PARA TEST','OTRO')")
        with pytest.raises(psycopg.errors.RaiseException):
            script(c, SEED)
        c.execute('ROLLBACK')
        assert c.execute("SELECT titulo FROM public.normativas WHERE codigo='PE_DS_014_2017_MINAM'").fetchone()[0] == 'CONFLICTO FICTICIO PARA TEST'
        assert c.execute("SELECT count(*) FROM public.normativas WHERE codigo='PE_DL_1278'").fetchone()[0] == 0


def test_sql_recupera_descarte_fuentes_y_genera_solo_confirmadas(db_local):
    settings, uid, pid, _, _ = db_local
    with settings.connect(autocommit=True) as c:
        script(c, MIGRATION)
        # Documentos expresamente FICTICIOS: no forman parte de la semilla propuesta.
        for nombre in ('A', 'B'):
            d = correspondencia_demo(nombre)
            c.execute('INSERT INTO public.normativas(id,codigo,titulo,tipo,numero,fecha_publicacion,url_fuente) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                      (d.normativa.id,d.normativa.codigo,d.normativa.titulo,d.normativa.tipo,d.normativa.numero,d.normativa.fecha_publicacion,d.normativa.url_fuente))
            c.execute('INSERT INTO public.normativa_correspondencias(etiqueta,normativa_id,estado_verificacion,fuente_url,fuente_vigencia_url,verificado_en,ambito,vigencia,justificacion) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                      (d.etiqueta,d.normativa.id,d.estado_verificacion,d.fuente_url,d.fuente_vigencia_url,d.verificado_en,d.ambito,d.vigencia,d.justificacion))
    config = Settings(persistence_mode='postgres', auth_mode='disabled')
    deps = Container(config, database_settings=settings, predictor=ContextPredictorMock(), generador=GeneradorBorradorMock())
    area = deps.catalogos.areas()[0].id
    usuario = UsuarioActual(uid, frozenset({Rol.FUNCIONARIO}), area)
    app = create_app(config, deps)
    app.dependency_overrides[get_current_user] = lambda: usuario
    with TestClient(app) as client:
        r = client.post('/solicitudes', json={'asunto':'DEMO TEST: residuos, inspección pendiente sin resultados'})
        assert r.status_code == 201
        url = '/solicitudes/'+r.json()['id']
        p = client.post(url+'/predecir-contexto').json()
        assert len(p['normativas']) == 2
        tipo = str(deps.plantillas.obtener_por_id(pid).tipo_informe_id)
        ids = [n['normativa_id'] for n in p['normativas']]
        r = client.post(url+'/validar-prediccion', json={'prediccion_id':p['id'],'resultado':'CORREGIDA',
            'tipo_informe_id':tipo,'area_destino_id':str(area),'normativa_ids':[ids[1]]})
        assert r.status_code == 200, r.text
        # Otra instancia, sin memoria de la sesión previa.
        fresh = Container(config, database_settings=settings, predictor=ContextPredictorMock(), generador=GeneradorBorradorMock())
        recovered = fresh.predicciones.ultima(UUID(url.rsplit('/',1)[1]))
        assert [n.aceptada for n in recovered.normativas] == [False, True]
        assert recovered.parametros['correspondencias_normativas'] == deps.predicciones.ultima(recovered.solicitud_id).parametros['correspondencias_normativas']
        fixture = json.loads(Path('tests/fixtures/inspeccion_parque_sin_resultados.json').read_text(encoding='utf-8'))
        campos = deps.plantillas.obtener_por_id(pid).campos
        saved = client.put(url+'/completa', json={'asunto':'DEMO TEST: residuos, inspección pendiente sin resultados',
            'tipo_informe_id':tipo,'area_destino_id':str(area),'area_origen_id':str(area),'plantilla_id':str(pid),
            'valores':[{'campo_plantilla_id':str(c.id),'valor':fixture['datos'][c.clave]} for c in campos]})
        assert saved.status_code == 200, saved.text
        captured = []
        original = deps.generar_borrador.generador
        class Capturar:
            def generar(self, *args):
                captured.append(args[3])
                return original.generar(*args)
        deps.generar_borrador.generador = Capturar()
        generado = client.post(url+'/generar-borrador', json={})
        assert generado.status_code == 201, generado.text
        assert [str(n.id) for n in captured[0].normas] == [ids[1]]
        assert 'artículo' not in json.dumps(generado.json()['contenido'], ensure_ascii=False).lower()
        iid = generado.json()['informe_id']
        content = generado.json()['contenido']
        assert client.put('/informes/'+iid, json={'numero_version':1,'contenido':content}).json()['numero_version'] == 2


@pytest.mark.skipif(os.getenv('NAXJI_RUN_OLLAMA_TESTS') != '1', reason='Ollama real: opt-in')
def test_sklearn_y_ollama_reales_con_semilla_verificada_sin_citas(db_local, tmp_path):
    from time import perf_counter
    settings, uid, pid, _, _ = db_local
    with settings.connect(autocommit=True) as c:
        script(c, MIGRATION)
        script(c, SEED)
    config = Settings(persistence_mode='postgres', auth_mode='disabled')
    deps = Container(config, database_settings=settings)  # Ambos modelos reales.
    area = deps.catalogos.areas()[0].id
    app = create_app(config, deps)
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(uid, frozenset({Rol.FUNCIONARIO}), area)
    asunto = 'PRUEBA NAXJI: evaluar acumulación de residuos sólidos en un parque ficticio; inspección pendiente sin resultados.'
    with TestClient(app) as client:
        url = '/solicitudes/'+client.post('/solicitudes', json={'asunto': asunto}).json()['id']
        p = client.post(url+'/predecir-contexto').json()
        assert not p['es_mock'] and p['modelo'] == 'SKLEARN_RF_IA_01'
        assert len(p['normativas']) == 2
        elegido = next(n for n in p['normativas'] if n['codigo'] == 'PE_DL_1278')
        tipo = str(deps.plantillas.obtener_por_id(pid).tipo_informe_id)
        r = client.post(url+'/validar-prediccion', json={'prediccion_id':p['id'],'resultado':'CORREGIDA',
            'tipo_informe_id':tipo,'area_destino_id':str(area),'normativa_ids':[elegido['normativa_id']]})
        assert r.status_code == 200, r.text
        assert len([n for n in client.get(url+'/contexto').json()['normativas'] if n['aceptada']]) == 1
        fixture = json.loads(Path('tests/fixtures/inspeccion_parque_sin_resultados.json').read_text(encoding='utf-8'))
        plantilla = deps.plantillas.obtener_por_id(pid)
        r = client.put(url+'/completa', json={'asunto':asunto,'tipo_informe_id':tipo,
            'area_destino_id':str(area),'area_origen_id':str(area),'plantilla_id':str(pid),
            'valores':[{'campo_plantilla_id':str(c.id),'valor':fixture['datos'][c.clave]} for c in plantilla.campos]})
        assert r.status_code == 200, r.text
        start = perf_counter()
        r = client.post(url+'/generar-borrador', json={'instrucciones':'No añadir hechos ni citas jurídicas. Información no aportada: pendiente de verificación.'})
        seconds = round(perf_counter()-start,3)
        assert r.status_code == 201, r.text
        data = r.json()
        contenido = {k:v for k,v in data['contenido'].items() if k != 'encabezado'}
        assert data['modelo_ia'] == 'qwen2.5:7b'
        assert list(contenido) == ['antecedentes','objetivo','analisis_tecnico','conclusiones','recomendaciones']
        texto = ' '.join(contenido.values()).lower()
        assert 'artículo' not in texto and '014-2017' not in texto
        assert 'pendiente' in texto
        for frase in ('se constató','se observó deterioro','se recomienda podar'):
            assert frase not in texto
        evidence = {'entorno':'PostgreSQL efímero local; identidad ficticia; sklearn y Ollama reales, sin Supabase',
                    'modelo_ia':data['modelo_ia'],'segundos':seconds,'etiquetas':p['temas_normativos'],
                    'codigos_propuestos':[n['codigo'] for n in p['normativas']],
                    'codigo_aceptado':elegido['codigo'],'codigo_descartado':'PE_DS_014_2017_MINAM',
                    'contenido_ficticio':contenido}
        (tmp_path/'normas-ollama-real.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(evidence,ensure_ascii=True))
