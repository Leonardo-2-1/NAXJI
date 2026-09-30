from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.application.ports.input.solicitud_use_case import DatosSolicitud
from src.application.ports.output.context_predictor import ContextPredictor
from src.application.ports.output.generador_borrador import GeneradorBorrador as GeneradorPort
from src.application.use_cases.generar_borrador import GenerarBorrador
from src.application.use_cases.predecir_contexto import PredecirContexto
from src.domain.services.errores import ConflictoEstado, DatosInvalidos, ErrorGeneracion, NoAutorizado
from src.domain.value_objects.estado_solicitud import EstadoSolicitud
from src.domain.value_objects.estados import ResultadoValidacion, OrigenVersion
from src.infrastructure.auth.mock import usuarios_demo


def preparar(deps, usuario, completar=True):
    solicitud = deps.crear_solicitud.ejecutar(usuario, DatosSolicitud("Inspección de un parque"))
    p = deps.predecir_contexto.ejecutar(solicitud.id, usuario)
    deps.validar_prediccion.ejecutar(solicitud.id, usuario, p.id, ResultadoValidacion.ACEPTADA)
    plantilla = next(p for p in deps.plantillas.listar() if p.tipo_informe_id == p_tipo(deps, solicitud.id))
    deps.actualizar_solicitud.ejecutar(solicitud.id, usuario, {"plantilla_id": plantilla.id})
    if completar:
        valores = {c.id: f"Datos para {c.clave}" for c in plantilla.campos if c.obligatorio}
        deps.guardar_valores.ejecutar(solicitud.id, usuario, valores)
    return deps.obtener_solicitud.ejecutar(solicitud.id, usuario)


def p_tipo(deps, solicitud_id):
    return deps.predicciones.ultima(solicitud_id).tipo_informe_predicho_id


def test_crear_y_obtener_con_uuid_y_propietario(deps, usuario):
    solicitud = deps.crear_solicitud.ejecutar(usuario, DatosSolicitud("  Asunto  "))
    assert solicitud.asunto == "Asunto"
    assert solicitud.usuario_id == usuario.id
    assert solicitud.estado == EstadoSolicitud.BORRADOR
    assert deps.obtener_solicitud.ejecutar(solicitud.id, usuario) == solicitud
    solicitud.asunto = "Mutación externa"
    assert deps.solicitudes.obtener_por_id(solicitud.id).asunto == "Asunto"


def test_crear_rechaza_asunto_vacio(deps, usuario):
    with pytest.raises(DatosInvalidos):
        deps.crear_solicitud.ejecutar(usuario, DatosSolicitud("   "))
    assert not deps.memoria.solicitudes


def test_prediccion_usa_puerto_y_no_confirma_automaticamente(deps, usuario):
    s = deps.crear_solicitud.ejecutar(usuario, DatosSolicitud("Asunto"))
    predictor = Mock(spec=ContextPredictor)
    predictor.predecir.return_value = deps.predecir_contexto.predictor.predecir(s.asunto, s.id)
    p = PredecirContexto(deps.servicios, predictor).ejecutar(s.id, usuario)
    predictor.predecir.assert_called_once_with("Asunto", s.id)
    assert p.modelo.startswith("MOCK_")
    assert p.resultado_validacion == ResultadoValidacion.PENDIENTE
    assert deps.solicitudes.obtener_por_id(s.id).tipo_informe_id is None


def test_prediccion_confianza_invalida_no_se_persiste(deps, usuario):
    s = deps.crear_solicitud.ejecutar(usuario, DatosSolicitud("Asunto"))
    predictor = Mock(spec=ContextPredictor)
    p = deps.predecir_contexto.predictor.predecir(s.asunto, s.id)
    p.confianza_tipo = 1.1
    predictor.predecir.return_value = p
    with pytest.raises(DatosInvalidos):
        PredecirContexto(deps.servicios, predictor).ejecutar(s.id, usuario)
    assert deps.predicciones.ultima(s.id) is None


def test_generar_transmite_plantilla_datos_contexto_instrucciones(deps, usuario):
    s = preparar(deps, usuario)
    assert s.estado == EstadoSolicitud.LISTA_PARA_GENERAR
    generador = Mock(spec=GeneradorPort, wraps=deps.generar_borrador.generador)
    informe = GenerarBorrador(deps.servicios, deps.informes, generador).ejecutar(s.id, usuario, "Sea breve")
    args = generador.generar.call_args.args
    assert args[0] == s.asunto
    assert args[1].id == s.plantilla_id
    assert args[2]["antecedentes"] == "Datos para antecedentes"
    assert args[3].tipo_informe_id == s.tipo_informe_id
    assert len(args[3].normativa_ids) == 1
    assert args[4] == "Sea breve"
    assert informe.versiones[0].origen == OrigenVersion.IA
    assert deps.solicitudes.obtener_por_id(s.id).estado == EstadoSolicitud.GENERADA
    with pytest.raises(ConflictoEstado):
        deps.generar_borrador.ejecutar(s.id, usuario)


def test_generar_fallo_hace_rollback_incluso_despues_de_guardar_informe(deps, usuario):
    s = preparar(deps, usuario)
    original_guardar = deps.informes.guardar
    def guardar_y_fallar(informe):
        original_guardar(informe)
        raise ErrorGeneracion("Fallo simulado")
    deps.informes.guardar = guardar_y_fallar
    with pytest.raises(ErrorGeneracion):
        deps.generar_borrador.ejecutar(s.id, usuario)
    assert deps.solicitudes.obtener_por_id(s.id).estado == EstadoSolicitud.LISTA_PARA_GENERAR
    assert deps.informes.obtener_por_solicitud(s.id) is None


def test_generar_requiere_datos_obligatorios(deps, usuario):
    s = preparar(deps, usuario, completar=False)
    with pytest.raises(DatosInvalidos, match="obligatorio"):
        deps.generar_borrador.ejecutar(s.id, usuario)


def test_generar_requiere_contexto_confirmado(deps, usuario):
    s = deps.crear_solicitud.ejecutar(usuario, DatosSolicitud("Asunto"))
    deps.predecir_contexto.ejecutar(s.id, usuario)
    with pytest.raises(ConflictoEstado):
        deps.generar_borrador.ejecutar(s.id, usuario)


def test_editar_conserva_versiones_y_detecta_edicion_obsoleta(deps, usuario):
    s = preparar(deps, usuario)
    informe = deps.generar_borrador.ejecutar(s.id, usuario)
    original = informe.versiones[0].contenido.copy()
    contenido = {**original, "conclusiones": "Conclusiones editadas"}
    editado = deps.actualizar_borrador.ejecutar(informe.id, usuario, contenido, 1)
    assert editado.versiones[0].contenido == original
    assert editado.versiones[1].numero_version == 2
    assert editado.versiones[1].origen == OrigenVersion.USUARIO
    assert deps.obtener_informe.ejecutar(informe.id, usuario) == editado
    with pytest.raises(ConflictoEstado):
        deps.actualizar_borrador.ejecutar(informe.id, usuario, contenido, 1)


def test_cambiar_asunto_invalida_contexto(deps, usuario):
    s = preparar(deps, usuario)
    s = deps.actualizar_solicitud.ejecutar(s.id, usuario, {"asunto": "Nuevo asunto"})
    assert s.estado == EstadoSolicitud.BORRADOR
    p = deps.predicciones.ultima(s.id)
    assert p.resultado_validacion == ResultadoValidacion.PENDIENTE
    with pytest.raises(ConflictoEstado, match="asunto"):
        deps.validar_prediccion.ejecutar(s.id, usuario, p.id, ResultadoValidacion.ACEPTADA)


def test_corregir_contexto_usa_seleccion_usuario_en_generacion(deps, usuario):
    s = deps.crear_solicitud.ejecutar(usuario, DatosSolicitud("Asunto"))
    p = deps.predecir_contexto.ejecutar(s.id, usuario)
    tipo = deps.catalogos.tipos_informe()[0]
    area = deps.catalogos.areas()[1]
    deps.validar_prediccion.ejecutar(s.id, usuario, p.id, ResultadoValidacion.CORREGIDA,
                                    tipo.id, area.id, [])
    plantilla = next(p for p in deps.plantillas.listar() if p.tipo_informe_id == tipo.id)
    deps.actualizar_solicitud.ejecutar(s.id, usuario, {"plantilla_id": plantilla.id})
    deps.guardar_valores.ejecutar(s.id, usuario, {c.id: "Datos" for c in plantilla.campos if c.obligatorio})
    generador = Mock(spec=GeneradorPort, wraps=deps.generar_borrador.generador)
    GenerarBorrador(deps.servicios, deps.informes, generador).ejecutar(s.id, usuario)
    contexto = generador.generar.call_args.args[3]
    assert (contexto.tipo_informe_id, contexto.area_destino_id, contexto.normativa_ids) == (tipo.id, area.id, ())
    assert deps.predicciones.ultima(s.id).tipo_informe_predicho_id == p.tipo_informe_predicho_id


def test_rechazar_o_repetir_prediccion_bloquea_generacion(deps, usuario):
    s = preparar(deps, usuario)
    anterior = deps.predicciones.ultima(s.id)
    nueva = deps.predecir_contexto.ejecutar(s.id, usuario)
    with pytest.raises(ConflictoEstado):
        deps.validar_prediccion.ejecutar(s.id, usuario, anterior.id, ResultadoValidacion.ACEPTADA)
    deps.validar_prediccion.ejecutar(s.id, usuario, nueva.id, ResultadoValidacion.RECHAZADA)
    with pytest.raises(ConflictoEstado):
        deps.generar_borrador.ejecutar(s.id, usuario)


def test_campo_ajeno_y_cambio_plantilla(deps, usuario):
    s = preparar(deps, usuario)
    with pytest.raises(DatosInvalidos):
        deps.guardar_valores.ejecutar(s.id, usuario, {uuid4(): "valor"})
    s = deps.actualizar_solicitud.ejecutar(s.id, usuario, {"plantilla_id": None})
    assert s.valores == []
    assert s.estado == EstadoSolicitud.BORRADOR


def test_cancelacion_impide_operaciones(deps, usuario):
    s = preparar(deps, usuario)
    deps.actualizar_solicitud.ejecutar(s.id, usuario, {"estado": EstadoSolicitud.CANCELADA})
    with pytest.raises(ConflictoEstado):
        deps.predecir_contexto.ejecutar(s.id, usuario)
    with pytest.raises(ConflictoEstado):
        deps.generar_borrador.ejecutar(s.id, usuario)


def test_acceso_por_propietario_y_rol(deps, usuario):
    s = preparar(deps, usuario)
    with pytest.raises(NoAutorizado):
        deps.obtener_solicitud.ejecutar(s.id, usuarios_demo()["demo-otro"])
    with pytest.raises(NoAutorizado):
        deps.generar_borrador.ejecutar(s.id, usuarios_demo()["demo-revisor"])


def test_generaciones_concurrentes_crean_un_solo_informe(deps, usuario):
    s = preparar(deps, usuario)
    def generar():
        try:
            return deps.generar_borrador.ejecutar(s.id, usuario).id
        except ConflictoEstado:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda _: generar(), range(2)))
    assert sum(r is not None for r in resultados) == 1
    assert len(deps.memoria.informes) == 1
