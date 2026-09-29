"""Previsualiza con rollback; --apply confirma las inserciones del seed PMV1."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from psycopg import Error, sql
from psycopg.rows import dict_row
from src.infrastructure.configuration.database import DatabaseSettings, database_error

TABLES = ('areas_municipales', 'tipos_informe', 'plantillas', 'campos_plantilla', 'normativas')
SEED = ROOT / 'database/seeds/pmv1_catalogos.sql'
PILOTO = 'Informe Técnico – Piloto NAXJI'


def seed_body():
    # La transacción la controla este programa; el SQL también funciona solo.
    return '\n'.join(line for line in SEED.read_text(encoding='utf8').splitlines()
                     if line.strip() not in {'BEGIN;', 'COMMIT;'})


def snapshot(c):
    return {table: {str(r['id']): r for r in c.execute(
        sql.SQL('SELECT * FROM public.{} ORDER BY id').format(sql.Identifier(table)))}
        for table in TABLES}


def load(c):
    before = snapshot(c)
    c.execute(seed_body())
    after = snapshot(c)
    for table in TABLES:
        if any(after[table].get(key) != row for key, row in before[table].items()):
            raise ValueError('El seed intentó alterar un registro existente')
    piloto = next(r for r in after['plantillas'].values()
                  if r['nombre'] == PILOTO and r['version'] == 1)
    tipo = after['tipos_informe'][str(piloto['tipo_informe_id'])]
    if tipo['codigo'] != 'INFORME_TECNICO' or not piloto['activa'] or piloto['area_id']:
        raise ValueError('La plantilla existente es incompatible; requiere revisión')
    campos = [r for r in after['campos_plantilla'].values() if r['plantilla_id'] == piloto['id']]
    expected = {'referencia_documento': ('text', False, 1), 'fecha': ('date', True, 2),
                'antecedentes': ('textarea', True, 3), 'objetivo': ('textarea', True, 4),
                'detalle': ('textarea', True, 5), 'conclusiones': ('textarea', True, 6),
                'recomendaciones': ('textarea', True, 7)}
    if {r['clave']: (r['tipo_dato'], r['obligatorio'], r['orden']) for r in campos if r['activo']} != expected:
        raise ValueError('Los campos existentes difieren del piloto')
    parents = {'MDT_CONCEJO': None, 'MDT_ALCALDIA': 'MDT_CONCEJO', 'MDT_GM': 'MDT_ALCALDIA',
               'MDT_GSP': 'MDT_GM', 'MDT_GDT': 'MDT_GM', 'MDT_GDE': 'MDT_GM',
               'MDT_GAJ': 'MDT_GM', 'MDT_SGGA': 'MDT_GSP', 'MDT_SGDUR': 'MDT_GDT'}
    areas = {r['codigo']: r for r in after['areas_municipales'].values()}
    for code, parent in parents.items():
        if not areas[code]['activo'] or areas[code]['area_padre_id'] != (areas[parent]['id'] if parent else None):
            raise ValueError('Área existente inactiva o jerarquía incompatible: ' + code)
    changes = {t: [r for k, r in after[t].items() if k not in before[t]] for t in TABLES}
    c.execute(seed_body())
    if snapshot(c) != after:
        raise ValueError('Falló la verificación de idempotencia')
    return changes, after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Confirmar carga; por defecto hace rollback')
    args = parser.parse_args()
    try:
        with DatabaseSettings.from_env().connect(row_factory=dict_row) as c:
            changes, after = load(c)
            print(json.dumps({'insertar': changes, 'actualizar': [],
                              'totales': {t: len(rows) for t, rows in after.items()}},
                             ensure_ascii=True, default=str, indent=2))
            print('IDEMPOTENCIA: segunda ejecución sin cambios')
            if not args.apply:
                c.rollback()
                print('VISTA PREVIA: ROLLBACK, no se guardaron filas')
            else:
                c.commit()
                print('APLICADO: COMMIT, registros anteriores conservados')
        return 0
    except Error as error:
        print(database_error(error), file=sys.stderr)
    except ValueError as error:
        print(str(error), file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
