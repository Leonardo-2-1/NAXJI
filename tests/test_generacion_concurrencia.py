from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from threading import Event
from unittest.mock import Mock

import pytest

from src.application.use_cases.generar_borrador import GenerarBorrador
from src.domain.entities.solicitud import ahora
from src.domain.services.errores import ConflictoEstado, ErrorGeneracion, NoEncontrado
from src.domain.value_objects.estado_solicitud import EstadoSolicitud
from tests.test_casos_uso import preparar


def test_contexto_enviado_resuelve_nombres_y_solo_normas_aceptadas(deps, usuario):
    solicitud = preparar(deps, usuario)
    original = deps.generar_borrador.generador
    espia = Mock(wraps=original)
    GenerarBorrador(deps.servicios, deps.informes, espia).ejecutar(solicitud.id, usuario)
    contexto = espia.generar.call_args.args[3]
    assert contexto.tipo_informe_nombre == next(t.nombre for t in deps.catalogos.tipos_informe() if t.id == solicitud.tipo_informe_id)
    assert contexto.area_destino_nombre == next(a.nombre for a in deps.catalogos.areas() if a.id == solicitud.area_destino_id)
    assert contexto.normas
    assert tuple(n.id for n in contexto.normas) == contexto.normativa_ids
    assert all(n.titulo == deps.catalogos.normativa(n.id).titulo for n in contexto.normas)


def test_inferencia_fuera_de_transaccion_con_reserva_visible_y_sin_bloquear_lecturas(deps, usuario):
    solicitud = preparar(deps, usuario)
    original_tx = deps.uow.transaccion
    activo = []
    @contextmanager
    def transaccion():
        with original_tx():
            activo.append(True)
            try:
                yield
            finally:
                activo.pop()
    deps.uow.transaccion = transaccion
    original = deps.generar_borrador.generador
    inicio, continuar = Event(), Event()
    def generar(*args):
        assert not activo
        inicio.set()
        assert continuar.wait(5)
        return original.generar(*args)
    deps.generar_borrador.generador = Mock(generar=generar)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futuro = pool.submit(deps.generar_borrador.ejecutar, solicitud.id, usuario)
        try:
            assert inicio.wait(2)
            lectura = pool.submit(deps.obtener_solicitud.ejecutar, solicitud.id, usuario).result(timeout=2)
            assert lectura.estado == EstadoSolicitud.PROCESANDO
            with pytest.raises(ConflictoEstado, match="curso"):
                deps.generar_borrador.ejecutar(solicitud.id, usuario)
            with pytest.raises(ConflictoEstado):
                deps.actualizar_solicitud.ejecutar(solicitud.id, usuario, {"asunto": "Cambio no permitido"})
        finally:
            continuar.set()
        assert futuro.result(timeout=2).versiones[0].contenido
    assert len(deps.memoria.informes) == 1


@pytest.mark.parametrize("falla_anterior", [False, True])
def test_resultado_o_fallo_tardio_no_pisa_una_reserva_nueva(deps, usuario, monkeypatch, falla_anterior):
    reloj = [ahora()]
    monkeypatch.setattr("src.application.use_cases.servicios_solicitud.ahora", lambda: reloj[0])
    solicitud = preparar(deps, usuario)
    generador = deps.generar_borrador.generador
    primero, segundo, liberar_primero, liberar_segundo = (Event() for _ in range(4))
    calls = []
    def generar(*args):
        calls.append(True)
        if len(calls) == 1:
            primero.set()
            assert liberar_primero.wait(5)
            if falla_anterior:
                raise ErrorGeneracion(codigo="OLLAMA_TIMEOUT")
        else:
            segundo.set()
            assert liberar_segundo.wait(5)
        return generador.generar(*args)
    caso = GenerarBorrador(deps.servicios, deps.informes, Mock(generar=generar), tiempo_maximo=1, reloj=lambda: reloj[0])
    with ThreadPoolExecutor(max_workers=2) as pool:
        anterior = pool.submit(caso.ejecutar, solicitud.id, usuario)
        try:
            assert primero.wait(2)
            reloj[0] += timedelta(seconds=32)
            nuevo = pool.submit(caso.ejecutar, solicitud.id, usuario)
            assert segundo.wait(2)
            reserva = deps.solicitudes.obtener_por_id(solicitud.id)
            liberar_primero.set()
            with pytest.raises(ErrorGeneracion if falla_anterior else ConflictoEstado):
                anterior.result(timeout=2)
            assert deps.solicitudes.obtener_por_id(solicitud.id) == reserva
        finally:
            liberar_primero.set()
            liberar_segundo.set()
        assert nuevo.result(timeout=2).versiones[0].contenido
    assert len(deps.memoria.informes) == 1


def test_reserva_abandonada_se_recupera_despues_de_reiniciar_caso_de_uso(deps, usuario):
    solicitud = preparar(deps, usuario)
    deps.generar_borrador._reservar(solicitud.id, usuario)
    reservada = deps.solicitudes.obtener_por_id(solicitud.id)
    reservada.updated_at -= timedelta(hours=1)
    deps.solicitudes.guardar(reservada)
    nuevo = GenerarBorrador(deps.servicios, deps.informes, deps.generar_borrador.generador)
    assert nuevo.ejecutar(solicitud.id, usuario)
    assert deps.solicitudes.obtener_por_id(solicitud.id).estado == EstadoSolicitud.GENERADA


def test_cambio_de_plantilla_durante_inferencia_descarta_resultado_y_libera(deps, usuario):
    solicitud = preparar(deps, usuario)
    original = deps.generar_borrador.generador
    def generar(*args):
        resultado = original.generar(*args)
        deps.plantillas.plantillas[solicitud.plantilla_id].nombre = "Plantilla actualizada mientras se generaba"
        return resultado
    deps.generar_borrador.generador = Mock(generar=generar)
    with pytest.raises(ConflictoEstado, match="cambiaron"):
        deps.generar_borrador.ejecutar(solicitud.id, usuario)
    assert deps.solicitudes.obtener_por_id(solicitud.id).estado == EstadoSolicitud.LISTA_PARA_GENERAR
    assert not deps.memoria.informes


def test_plantilla_retirada_no_deja_solicitud_bloqueada(deps, usuario):
    solicitud = preparar(deps, usuario)
    original = deps.generar_borrador.generador
    def generar(*args):
        resultado = original.generar(*args)
        deps.plantillas.plantillas[solicitud.plantilla_id].activa = False
        return resultado
    deps.generar_borrador.generador = Mock(generar=generar)
    with pytest.raises(NoEncontrado):
        deps.generar_borrador.ejecutar(solicitud.id, usuario)
    assert deps.solicitudes.obtener_por_id(solicitud.id).estado == EstadoSolicitud.BORRADOR


def test_error_inesperado_del_proveedor_se_sanitiza_y_se_puede_reintentar(deps, usuario):
    solicitud = preparar(deps, usuario)
    deps.generar_borrador.generador = Mock(generar=Mock(side_effect=RuntimeError("PROMPT_PRIVADO")))
    with pytest.raises(ErrorGeneracion) as fallo:
        deps.generar_borrador.ejecutar(solicitud.id, usuario)
    assert "PRIVADO" not in str(fallo.value)
    assert deps.solicitudes.obtener_por_id(solicitud.id).estado == EstadoSolicitud.LISTA_PARA_GENERAR
