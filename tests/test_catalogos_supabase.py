"""Pruebas opt-in sobre catálogos reales. Autenticación inyectada solo en TestClient."""
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from scripts.cargar_catalogos import load, snapshot, PILOTO
from src.infrastructure.configuration.database import DatabaseSettings
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.configuration.container import Container
from src.infrastructure.dependencies import get_current_user
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.main import create_app

pytestmark = pytest.mark.skipif(os.getenv('NAXJI_RUN_DB_TESTS') != '1', reason='Supabase: prueba opt-in')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db():
    return DatabaseSettings.from_env()


def datos(c):
    p = c.execute('SELECT * FROM public.plantillas WHERE nombre=%s AND version=1', (PILOTO,)).fetchone()
    assert p, 'Ejecute scripts/cargar_catalogos.py --apply'
    campos = c.execute('SELECT * FROM public.campos_plantilla WHERE plantilla_id=%s ORDER BY orden', (p['id'],)).fetchall()
    area = c.execute("SELECT id FROM public.areas_municipales WHERE codigo='MDT_SGGA'").fetchone()['id']
    user = c.execute("SELECT id FROM auth.users WHERE email='funcionario1.naxji@gmail.com'").fetchone()['id']
    return user, {'asunto': 'TEST_PILOTO_' + uuid4().hex, 'tipo_informe_id': str(p['tipo_informe_id']),
                 'plantilla_id': str(p['id']), 'area_origen_id': str(area), 'area_destino_id': str(area),
                 'valores': [{'campo_plantilla_id': str(f['id']),
                             'valor': '2026-09-29' if f['tipo_dato'] == 'date' else 'DEMOSTRACION: ' + f['clave']}
                            for f in campos]}, campos


def app_for(container, user):
    app = create_app(Settings(persistence_mode='postgres', auth_mode='disabled'), container)
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(user, frozenset({Rol.FUNCIONARIO}))
    return app


def test_seed_idempotente_y_catalogos_rls(db):
    with db.connect(row_factory=dict_row) as c:
        before = snapshot(c)
        changes, after = load(c)
        assert all(not rows for rows in changes.values())
        assert before == after
        user, body, campos = datos(c)
        inactive = c.execute("INSERT INTO public.areas_municipales(codigo,nombre,activo) VALUES (%s,'TEST inactiva',false) RETURNING id",
                             ('TEST_' + uuid4().hex[:20],)).fetchone()['id']
        c.execute('SET LOCAL ROLE authenticated')
        c.execute("SELECT set_config('request.jwt.claims',%s,true)", (json.dumps({'sub': str(user), 'role': 'authenticated'}),))
        assert c.execute('SELECT count(*) AS n FROM public.areas_municipales WHERE id=%s', (inactive,)).fetchone()['n'] == 0
        for table in ('areas_municipales','tipos_informe','plantillas','campos_plantilla','normativas'):
            assert c.execute('SELECT count(*) AS n FROM public.' + table).fetchone()['n'] == len(before[table])
        c.rollback()
    print('Seed: 0 inserciones al repetir; RLS authenticated: 9 areas, 4 tipos, 1 plantilla, 7 campos, 1 documento; inactiva invisible; rollback')


def test_piloto_http_validaciones_y_rollback(db):
    container = Container(Settings(persistence_mode='postgres', auth_mode='disabled'), database_settings=db)
    class Abort(Exception): pass
    with pytest.raises(Abort):
        with container.uow.transaccion():
            with container.uow.connection() as c:
                user, body, campos = datos(c)
                inactive = c.execute("INSERT INTO public.plantillas(nombre,tipo_informe_id,activa) VALUES (%s,%s,false) RETURNING id",
                                     ('TEST_' + uuid4().hex, body['tipo_informe_id'])).fetchone()['id']
                foreign = c.execute("INSERT INTO public.campos_plantilla(plantilla_id,clave,etiqueta,tipo_dato,orden) VALUES (%s,'ajeno','Ajeno','text',1) RETURNING id",
                                    (inactive,)).fetchone()['id']
                area_inactive = c.execute("INSERT INTO public.areas_municipales(codigo,nombre,activo) VALUES (%s,'TEST',false) RETURNING id",
                                         ('TEST_' + uuid4().hex[:20],)).fetchone()['id']
                type_inactive = c.execute("INSERT INTO public.tipos_informe(codigo,nombre,activo) VALUES (%s,'TEST',false) RETURNING id",
                                         ('TEST_' + uuid4().hex[:20],)).fetchone()['id']
            with TestClient(app_for(container, user)) as client:
                assert len(client.get('/areas').json()) == 9
                assert len(client.get('/tipos-informe').json()) == 4
                assert len(client.get('/plantillas').json()) == 1
                response = client.get(f"/plantillas/{body['plantilla_id']}/campos")
                assert [r['id'] for r in response.json()] == [str(c['id']) for c in campos]
                for key, value in [('plantilla_id', inactive), ('area_destino_id', area_inactive),
                                   ('tipo_informe_id', type_inactive), ('plantilla_id', uuid4())]:
                    assert client.post('/solicitudes/completa', json={**body, key: str(value)}).status_code == 404
                assert client.post('/solicitudes/completa', json={**body, 'valores': []}).status_code == 400
                bad = {**body, 'valores': [*body['valores'], {'campo_plantilla_id': str(foreign), 'valor': 'Ajeno'}]}
                assert client.post('/solicitudes/completa', json=bad).status_code == 400
                legal = next(t for t in client.get('/tipos-informe').json() if t['codigo']=='INFORME_LEGAL')
                assert client.post('/solicitudes/completa', json={**body,'tipo_informe_id':legal['id']}).status_code == 400
                with container.uow.connection() as c:
                    assert c.execute('SELECT count(*) AS n FROM public.solicitudes WHERE asunto=%s',(body['asunto'],)).fetchone()['n'] == 0
                r = client.post('/solicitudes/completa', json=body)
                assert r.status_code == 201, r.text
                path = '/solicitudes/' + r.json()['id']
                original = client.get(path).json()
                assert len(original['valores']) == 7
                assert client.put(path + '/completa', json={**body,'asunto':'No conservar','valores':[]}).status_code == 400
                assert client.get(path).json() == original
            raise Abort()
    print('FastAPI PostgreSQL: catalogos/UUID/campos 200, piloto 201, invalidos 400/404, update fallido revierte padre y valores')


def test_piloto_sobrevive_otro_proceso(db):
    with db.connect(row_factory=dict_row) as c:
        user, body, _ = datos(c)
    container = Container(Settings(persistence_mode='postgres', auth_mode='disabled'), database_settings=db)
    try:
        with TestClient(app_for(container, user)) as client:
            result = client.post('/solicitudes/completa', json=body)
            assert result.status_code == 201, result.text
            saved = result.json()
        worker = subprocess.run([sys.executable, str(ROOT/'tests/postgres_restart_worker.py'), 'read', str(user), saved['id']],
                                capture_output=True, text=True, timeout=60, check=True)
        assert json.loads(worker.stdout) == saved
        with db.connect() as c:
            assert c.execute('SELECT count(*) FROM public.solicitud_valores WHERE solicitud_id=%s', (saved['id'],)).fetchone()[0] == 7
        print('Piloto persistente: HTTP 201 -> nuevo proceso HTTP GET 200 -> 7 valores SQL iguales')
    finally:
        with db.connect() as c:
            c.execute('DELETE FROM public.solicitudes WHERE usuario_id=%s AND asunto=%s',(user,body['asunto']))
