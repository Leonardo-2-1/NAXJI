"""Pruebas locales; no usan red ni el .env privado."""
from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4
from unittest.mock import Mock

import psycopg
import pytest
from fastapi.testclient import TestClient

from src.infrastructure.configuration import database
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.configuration.container import Container
from src.infrastructure.dependencies import get_current_user
from src.infrastructure.auth.mock import usuarios_demo
from src.adapters.out.persistence.postgres import PostgresUnidadTrabajo, PersistenceError
from src.adapters.out.ai.context_predictor_mock import ContextPredictorMock
from src.adapters.out.ai.context_predictor_catalogo import ContextPredictorCatalogo
from src.adapters.out.persistence.datos_demo import TIPOS, AREAS, NORMATIVAS
from src.domain.services.errores import DatosInvalidos
from src.main import create_app
from tests.fixtures.normativa_demo import correspondencia_demo


@pytest.fixture
def config(monkeypatch):
    values = {"NAXJI_DB_HOST": "localhost", "NAXJI_DB_PORT": "5432", "NAXJI_DB_NAME": "test",
              "NAXJI_DB_USER": "test", "NAXJI_DB_PASSWORD": "private-${literal}", "NAXJI_DB_SSLMODE": "require"}
    monkeypatch.setattr(database, "environment", lambda: values)
    return values


def test_config_validates_before_connecting_and_hides_password(config):
    settings = database.DatabaseSettings.from_env()
    assert settings.password == "private-${literal}"
    assert settings.password not in repr(settings)
    del config["NAXJI_DB_PASSWORD"]
    with pytest.raises(ValueError, match="NAXJI_DB_PASSWORD"):
        database.DatabaseSettings.from_env()


@pytest.mark.parametrize("key,value", [("NAXJI_DB_PORT", "invalid"), ("NAXJI_DB_PORT", "0"),
                                      ("NAXJI_DB_SSLMODE", "disable"), ("NAXJI_DB_CONNECT_TIMEOUT", "0"),
                                      ("NAXJI_DB_PASSWORD", "[YOUR-PASSWORD]")])
def test_config_rejects_invalid_values(config, key, value):
    config[key] = value
    with pytest.raises(ValueError):
        database.DatabaseSettings.from_env()


def test_dotenv_absolute_root_preserves_literals_and_os_priority(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("NAXJI_DB_PASSWORD='literal-${NAXJI_TEST}'\nNAXJI_DB_HOST=file\n", encoding="utf-8")
    monkeypatch.setattr(database, "ROOT", tmp_path)
    monkeypatch.delenv("NAXJI_DB_PASSWORD", raising=False)
    monkeypatch.setenv("NAXJI_DB_HOST", "process")
    values = database.environment()
    assert values["NAXJI_DB_PASSWORD"] == "literal-${NAXJI_TEST}"
    assert values["NAXJI_DB_HOST"] == "process"


def test_uow_rolls_back_and_releases_connection_on_failure():
    events = []
    connection = Mock()
    @contextmanager
    def connect(**kwargs):
        try:
            yield connection
        except Exception:
            events.append("rollback")
            raise
        else:
            events.append("commit")
        finally:
            events.append("close")
    settings = Mock(connect=connect)
    uow = PostgresUnidadTrabajo(settings)
    with pytest.raises(ValueError):
        with uow.transaccion():
            with uow.connection(write=True) as current:
                assert current is connection
            raise ValueError("fallo controlado")
    assert events == ["rollback", "close"]
    assert not uow.active
    with uow.transaccion():
        assert uow.active
    assert events[-2:] == ["commit", "close"]


def test_postgres_never_falls_back_to_memory_or_exposes_connection_error():
    settings = Mock()
    settings.connect.side_effect = psycopg.OperationalError("password=secret-test")
    config = Settings(persistence_mode="postgres")
    deps = Container(config, database_settings=settings, predictor=ContextPredictorMock())
    assert not hasattr(deps, "memoria")
    app = create_app(config, deps)
    with TestClient(app) as client:
        assert client.get("/areas", headers={"Authorization": "Bearer demo-admin"}).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: usuarios_demo()["demo-funcionario"]
        response = client.get("/areas")
        assert response.status_code == 503
        assert response.json() == {"detail": "Persistencia PostgreSQL no disponible"}
    with pytest.raises(PersistenceError) as error:
        deps.catalogos.areas()
    assert "secret-test" not in str(error.value)


def test_predictor_resolves_real_ids_and_rejects_missing_catalogs():
    catalogos = Mock()
    catalogos.tipos_informe.return_value = [replace(t, id=uuid4()) for t in TIPOS]
    catalogos.areas.return_value = [replace(a, id=uuid4()) for a in AREAS]
    correspondencia = correspondencia_demo()
    norma = correspondencia.normativa
    catalogos.correspondencias_normativas.return_value = [correspondencia]
    predictor = ContextPredictorCatalogo(ContextPredictorMock(), catalogos)
    prediction = predictor.predecir("prueba", uuid4())
    assert prediction.tipo_informe_predicho_id == catalogos.tipos_informe.return_value[2].id
    assert prediction.area_destino_predicha_id == catalogos.areas.return_value[0].id
    assert prediction.normativas[0].normativa_id == norma.id
    catalogos.areas.return_value = []
    with pytest.raises(DatosInvalidos, match="catálogo"):
        predictor.predecir("prueba", uuid4())


def test_real_sklearn_predictor_remains_available():
    deps = Container(Settings())
    prediction = deps.predecir_contexto.predictor.predecir("Inspección de parque municipal", uuid4())
    assert prediction.modelo == "SKLEARN_RF_IA_01"
    assert prediction.tipo_informe_predicho_id in {t.id for t in TIPOS}
    assert prediction.area_destino_predicha_id in {a.id for a in AREAS}
