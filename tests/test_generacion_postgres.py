"""Comprueba inferencia sin bloqueos y concurrencia entre instancias; base local aislada."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest

from src.application.ports.input.solicitud_use_case import DatosSolicitud
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.services.errores import ConflictoEstado
from src.domain.value_objects.estados import ResultadoValidacion, Rol
from src.adapters.out.ai.context_predictor_mock import ContextPredictorMock
from src.adapters.out.ai.generador_borrador_mock import GeneradorBorradorMock
from src.infrastructure.configuration.container import Container
from src.infrastructure.configuration.settings import Settings
from tests.test_estructura_postgres import db_local  # noqa: F401 - fixture compartida


pytestmark = pytest.mark.skipif(not os.getenv("NAXJI_TEST_PG_PORT"), reason="PostgreSQL local aislado: opt-in")


def test_inferencia_sin_bloqueo_postgres_y_dos_instancias_no_duplican(db_local):
    settings, uid, pid, _, _ = db_local
    def contenedor():
        return Container(Settings(persistence_mode="postgres", auth_mode="disabled"), database_settings=settings,
                         predictor=ContextPredictorMock(), generador=GeneradorBorradorMock())
    deps, otro = contenedor(), contenedor()
    fixture = json.loads((Path(__file__).parent / "fixtures/inspeccion_parque_sin_resultados.json").read_text(encoding="utf-8"))
    area = deps.catalogos.areas()[0].id
    usuario = UsuarioActual(uid, frozenset({Rol.FUNCIONARIO}), area)
    solicitud = deps.crear_solicitud.ejecutar(usuario, DatosSolicitud(fixture["asunto"]))
    prediccion = deps.predecir_contexto.ejecutar(solicitud.id, usuario)
    plantilla = deps.plantillas.obtener_por_id(pid)
    deps.validar_prediccion.ejecutar(solicitud.id, usuario, prediccion.id, ResultadoValidacion.CORREGIDA,
                                    plantilla.tipo_informe_id, area, [])
    deps.actualizar_solicitud.ejecutar(solicitud.id, usuario, {"plantilla_id": pid})
    deps.guardar_valores.ejecutar(solicitud.id, usuario, {c.id: fixture["datos"][c.clave] for c in plantilla.campos})
    original = deps.generar_borrador.generador
    inicio, continuar = Event(), Event()
    def generar(*args):
        assert not deps.uow.active
        with settings.connect() as c:
            # Fracasaría de inmediato si otra transacción retuviera el bloqueo.
            estado = c.execute("SELECT estado FROM public.solicitudes WHERE id=%s FOR UPDATE NOWAIT", (solicitud.id,)).fetchone()[0]
            assert estado == "PROCESANDO"
            c.execute("SELECT id FROM public.predicciones_ia WHERE id=%s FOR UPDATE NOWAIT", (prediccion.id,)).fetchone()
        inicio.set()
        assert continuar.wait(8)
        return original.generar(*args)
    deps.generar_borrador.generador = Mock(generar=generar)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futuro = pool.submit(deps.generar_borrador.ejecutar, solicitud.id, usuario)
        try:
            assert inicio.wait(4)
            with pytest.raises(ConflictoEstado, match="curso"):
                otro.generar_borrador.ejecutar(solicitud.id, usuario)
        finally:
            continuar.set()
        informe = futuro.result(timeout=4)
    assert otro.informes.obtener_por_solicitud(solicitud.id).id == informe.id
    assert otro.informes.obtener_por_id(informe.id).versiones[0].secciones_salida == plantilla.secciones_salida
    assert otro.solicitudes.obtener_por_id(solicitud.id).estado.value == "GENERADA"
