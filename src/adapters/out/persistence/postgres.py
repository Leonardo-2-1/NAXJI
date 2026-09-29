"""Adaptadores del esquema PMV1 existente. No ejecutan migraciones ni datos semilla."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import fields
from enum import Enum

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.application.ports.output.unidad_trabajo import UnidadTrabajo
from src.application.ports.output.catalogo_repository import CatalogoRepository
from src.application.ports.output.plantilla_repository import PlantillaRepository
from src.application.ports.output.solicitud_repository import SolicitudRepository
from src.application.ports.output.prediccion_repository import PrediccionRepository
from src.application.ports.output.informe_repository import InformeRepository
from src.domain.entities.catalogo import TipoInforme, AreaMunicipal, Normativa
from src.domain.entities.plantilla import Plantilla, CampoPlantilla
from src.domain.entities.solicitud import Solicitud, SolicitudValor
from src.domain.entities.prediccion_contexto import PrediccionContexto, NormativaPredicha
from src.domain.entities.informe import Informe, VersionInforme
from src.domain.services.errores import ConflictoEstado, DatosInvalidos
from src.domain.value_objects.estado_solicitud import EstadoSolicitud
from src.domain.value_objects.estados import EstadoInforme, OrigenVersion, ResultadoValidacion, TipoDato
from src.infrastructure.configuration.database import DatabaseSettings, database_error


class PersistenceError(RuntimeError):
    """Error sanitizado: nunca incluye SQL, parámetros ni mensajes del proveedor."""


class PostgresUnidadTrabajo(UnidadTrabajo):
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self._current = ContextVar("naxji_connection", default=None)

    @property
    def active(self):
        return self._current.get() is not None

    @contextmanager
    def transaccion(self):
        if self.active:
            # Savepoint: también revierte errores capturados por el llamador.
            with self._current.get().transaction():
                yield
            return
        try:
            with self.settings.connect(row_factory=dict_row) as connection:
                token = self._current.set(connection)
                try:
                    yield
                finally:
                    self._current.reset(token)
        except psycopg.errors.UniqueViolation:
            raise ConflictoEstado("El registro o número de versión ya existe") from None
        except (psycopg.errors.ForeignKeyViolation, psycopg.errors.CheckViolation):
            raise DatosInvalidos("Referencias o valores incompatibles con el esquema PostgreSQL") from None
        except psycopg.Error as error:
            raise PersistenceError(database_error(error)) from None

    @contextmanager
    def connection(self, *, write=False):
        if self.active:
            yield self._current.get()
        elif write:
            with self.transaccion():
                yield self._current.get()
        else:
            try:
                with self.settings.connect(row_factory=dict_row) as connection:
                    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                    yield connection
            except psycopg.Error as error:
                raise PersistenceError(database_error(error)) from None


def entity(cls, row, **enums):
    values = {f.name: row[f.name] for f in fields(cls) if f.name in row}
    for name, enum in enums.items():
        values[name] = enum(values[name])
    for name in ("confianza", "confianza_tipo", "confianza_area"):
        if values.get(name) is not None:
            values[name] = float(values[name])
    return cls(**values)


def save(connection, table, item, *, omit=(), json_fields=(), extra=None, insert_only=False):
    """Los identificadores provienen solo de clases internas, nunca del cliente HTTP."""
    values = {f.name: getattr(item, f.name) for f in fields(item) if f.name not in omit}
    values.update(extra or {})
    for key, value in values.items():
        if key in json_fields:
            values[key] = Jsonb(value)
        elif isinstance(value, Enum):
            values[key] = value.value
    columns = list(values)
    statement = sql.SQL("INSERT INTO public.{} ({}) VALUES ({})").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    if not insert_only:
        updates = [c for c in columns if c not in {"id", "created_at"}]
        statement += sql.SQL(" ON CONFLICT (id) DO UPDATE SET ") + sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c)) for c in updates
        )
    connection.execute(statement, list(values.values()))


class Repository:
    def __init__(self, uow):
        self.uow = uow

    def lock(self):
        return " FOR UPDATE" if self.uow.active else ""


class CatalogoRepositoryPostgres(Repository, CatalogoRepository):
    def tipos_informe(self):
        with self.uow.connection() as c:
            return [entity(TipoInforme, r) for r in c.execute("SELECT * FROM public.tipos_informe ORDER BY codigo")]

    def areas(self):
        with self.uow.connection() as c:
            return [entity(AreaMunicipal, r) for r in c.execute("SELECT * FROM public.areas_municipales ORDER BY codigo")]

    def normativa(self, normativa_id):
        with self.uow.connection() as c:
            row = c.execute("SELECT * FROM public.normativas WHERE id=%s", (normativa_id,)).fetchone()
            return entity(Normativa, row) if row else None

    def normativa_por_codigo(self, codigo):
        with self.uow.connection() as c:
            row = c.execute("SELECT * FROM public.normativas WHERE codigo=%s AND activo", (codigo,)).fetchone()
            return entity(Normativa, row) if row else None


class PlantillaRepositoryPostgres(Repository, PlantillaRepository):
    @staticmethod
    def load(c, row):
        item = entity(Plantilla, row)
        item.campos = [entity(CampoPlantilla, r, tipo_dato=TipoDato) for r in c.execute(
            "SELECT * FROM public.campos_plantilla WHERE plantilla_id=%s ORDER BY orden", (item.id,))]
        return item

    def listar(self):
        with self.uow.connection() as c:
            rows = c.execute("SELECT * FROM public.plantillas WHERE activa ORDER BY nombre, version").fetchall()
            return [self.load(c, row) for row in rows]

    def obtener_por_id(self, plantilla_id):
        with self.uow.connection() as c:
            row = c.execute("SELECT * FROM public.plantillas WHERE id=%s", (plantilla_id,)).fetchone()
            return self.load(c, row) if row else None


class SolicitudRepositoryPostgres(Repository, SolicitudRepository):
    def guardar(self, solicitud):
        with self.uow.connection(write=True) as c:
            save(c, "solicitudes", solicitud, omit=("valores",))
            c.execute("DELETE FROM public.solicitud_valores WHERE solicitud_id=%s AND NOT (id=ANY(%s::uuid[]))",
                      (solicitud.id, [v.id for v in solicitud.valores]))
            for value in solicitud.valores:
                save(c, "solicitud_valores", value, json_fields=("valor",))
            # Los triggers PostgreSQL son la autoridad de updated_at.
            # Leer en la misma transacción evita devolver timestamps solo locales.
            return self.obtener_por_id(solicitud.id)

    def obtener_por_id(self, solicitud_id):
        with self.uow.connection() as c:
            row = c.execute("SELECT * FROM public.solicitudes WHERE id=%s" + self.lock(), (solicitud_id,)).fetchone()
            if row is None:
                return None
            item = entity(Solicitud, row, estado=EstadoSolicitud)
            item.valores = [entity(SolicitudValor, r) for r in c.execute(
                "SELECT * FROM public.solicitud_valores WHERE solicitud_id=%s ORDER BY created_at, id", (item.id,))]
            return item


class PrediccionRepositoryPostgres(Repository, PrediccionRepository):
    def guardar(self, prediccion):
        with self.uow.connection(write=True) as c:
            save(c, "predicciones_ia", prediccion, omit=("normativas",), json_fields=("parametros",))
            c.execute("DELETE FROM public.prediccion_normativas WHERE prediccion_id=%s AND NOT (id=ANY(%s::uuid[]))",
                      (prediccion.id, [n.id for n in prediccion.normativas]))
            for norma in prediccion.normativas:
                save(c, "prediccion_normativas", norma, extra={"prediccion_id": prediccion.id})
        return prediccion

    def ultima(self, solicitud_id):
        with self.uow.connection() as c:
            row = c.execute("SELECT * FROM public.predicciones_ia WHERE solicitud_id=%s "
                            "ORDER BY created_at DESC, id DESC LIMIT 1" + self.lock(), (solicitud_id,)).fetchone()
            if row is None:
                return None
            item = entity(PrediccionContexto, row, resultado_validacion=ResultadoValidacion)
            item.normativas = [entity(NormativaPredicha, r) for r in c.execute(
                "SELECT * FROM public.prediccion_normativas WHERE prediccion_id=%s ORDER BY orden, id", (item.id,))]
            return item


class InformeRepositoryPostgres(Repository, InformeRepository):
    def guardar(self, informe):
        numbers = [v.numero_version for v in informe.versiones]
        if len(numbers) != len(set(numbers)) or any(n < 1 for n in numbers):
            raise ConflictoEstado("Número de versión inválido o duplicado")
        with self.uow.connection(write=True) as c:
            save(c, "informes", informe, omit=("versiones",))
            existing = {r["id"] for r in c.execute("SELECT id FROM public.versiones_informe WHERE informe_id=%s", (informe.id,))}
            for version in informe.versiones:
                if version.id not in existing:
                    save(c, "versiones_informe", version, json_fields=("contenido",), insert_only=True)
        return informe

    @staticmethod
    def load(c, row):
        if row is None:
            return None
        item = entity(Informe, row, estado=EstadoInforme)
        item.versiones = [entity(VersionInforme, r, origen=OrigenVersion) for r in c.execute(
            "SELECT * FROM public.versiones_informe WHERE informe_id=%s ORDER BY numero_version", (item.id,))]
        return item

    def obtener_por_id(self, informe_id):
        with self.uow.connection() as c:
            return self.load(c, c.execute("SELECT * FROM public.informes WHERE id=%s" + self.lock(), (informe_id,)).fetchone())

    def obtener_por_solicitud(self, solicitud_id):
        with self.uow.connection() as c:
            return self.load(c, c.execute("SELECT * FROM public.informes WHERE solicitud_id=%s" + self.lock(), (solicitud_id,)).fetchone())
