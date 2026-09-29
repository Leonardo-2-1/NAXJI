"""Evidencia real con tokens recibidos por stdin; nunca los imprime o guarda."""
import json
from contextlib import nullcontext
import socket
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from src.infrastructure.configuration.database import DatabaseSettings
from src.infrastructure.auth.supabase import SupabaseAuthSettings
from scripts.verificar_auth_supabase import backend, check, VerificationError


def run(data):
    raw_identifier = data["solicitud"]["id"]

    if not isinstance(raw_identifier, str):
        raise VerificationError("Identificador no válido")
    try:
        identifier = str(UUID(raw_identifier))
    except (ValueError, AttributeError):
        raise VerificationError("Identificador no válido") from None
    
    expected = data['solicitud']
    db = DatabaseSettings.from_env()
    with db.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        row = c.execute('SELECT usuario_id::text,asunto,plantilla_id::text FROM public.solicitudes WHERE id=%s', (identifier,)).fetchone()
        check(row == (expected['usuario_id'], expected['asunto'], expected['plantilla_id']), 'React_solicitud_confirmada_SQL')
        fields = c.execute('SELECT campo_plantilla_id::text,valor FROM public.solicitud_valores WHERE solicitud_id=%s', (identifier,)).fetchall()
        check(dict(fields) == {v['campo_plantilla_id']: v['valor'] for v in expected['valores']} and len(fields)==7,
              'Siete_valores_React_iguales_SQL')
    reuse_servers = data.get('reuse_servers', False)
    port = 8000
    if not reuse_servers:
        with socket.socket() as s:
            s.bind(('127.0.0.1',0))
            port=s.getsockname()[1]
    url=f'http://127.0.0.1:{port}'
    headers={'Authorization': 'Bearer '+data['tokens']['A']}
    with httpx.Client(base_url=url, headers=headers, timeout=40, trust_env=False) as a:
        with (nullcontext() if reuse_servers else backend(port)) as first:
            r=a.get('/solicitudes/'+identifier)
            check(r.status_code==200 and r.json()==expected, 'Servidor_existente_recupera_piloto' if reuse_servers else 'Proceso_uno_recupera_piloto_completo')
        with (nullcontext() if reuse_servers else backend(port)) as second:
            if not reuse_servers:
                check(first != second, 'Backend_reiniciado_PID_diferente')
            r=a.get('/solicitudes/'+identifier)
            check(r.status_code==200 and r.json()==expected, 'Persistencia_y_recuperacion_servidor_existente' if reuse_servers else 'Proceso_dos_conserva_piloto_y_valores')
            b={'Authorization': 'Bearer '+data['tokens']['B']}
            check(a.get('/solicitudes/'+identifier,headers=b).status_code==403, 'Funcionario_B_lectura_ajena_403')
            check(a.get('/solicitudes/'+identifier+'/contexto',headers=b).status_code==403, 'Funcionario_B_contexto_ajeno_403')
            check(a.put('/solicitudes/'+identifier,json={'asunto':'No alterar'},headers=b).status_code==403, 'Funcionario_B_escritura_ajena_403')
            with db.connect() as c:
                c.execute('SET TRANSACTION READ ONLY')
                expected_ids={str(r[0]) for r in c.execute('SELECT id FROM public.areas_municipales WHERE activo')}
            r=a.get('/areas')
            check(r.status_code==200 and {x['id'] for x in r.json()}==expected_ids, 'Endpoint_areas_UUID_reales_PostgreSQL')
    auth=SupabaseAuthSettings.from_env()
    with httpx.Client(timeout=30) as client:
        for letter,count in [('A',1),('B',0)]:
            r=client.get(auth.url+'/rest/v1/solicitudes',params={'select':'id','id':'eq.'+identifier},
                         headers={'apikey':auth.publishable_key,'Authorization':'Bearer '+data['tokens'][letter]})
            check(r.status_code==200 and len(r.json())==count,'RLS_Data_API_'+letter)
    print('SOLICITUD_DEMO_CONSERVADA: '+identifier,flush=True)


if __name__=='__main__':
    try:
        # Node envía JSON UTF-8 por stdin; Windows puede usar cp1252 por defecto.
        # Una decodificación distinta altera tildes y produce comparaciones falsas.
        sys.stdin.reconfigure(encoding='utf-8')
        run(json.load(sys.stdin))
    except VerificationError as e:
        print(str(e),flush=True)
        raise SystemExit(1)
    except Exception as e:
        print('VERIFICACION_NO_COMPLETADA: '+type(e).__name__+'; sin datos privados',flush=True)
        raise SystemExit(1)
