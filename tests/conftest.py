import pytest
from fastapi.testclient import TestClient

from src.infrastructure.auth.mock import usuarios_demo
from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from src.main import create_app
from src.adapters.out.ai.context_predictor_mock import ContextPredictorMock


@pytest.fixture
def deps():
    return Container(Settings(), predictor=ContextPredictorMock())


@pytest.fixture
def usuario():
    return usuarios_demo()["demo-funcionario"]


@pytest.fixture
def client(deps):
    with TestClient(create_app(Settings(), deps), raise_server_exceptions=False) as test_client:
        test_client.headers["Authorization"] = "Bearer demo-funcionario"
        yield test_client
