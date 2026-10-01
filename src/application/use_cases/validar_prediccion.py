from uuid import UUID

from src.application.use_cases.servicios_solicitud import ServiciosSolicitud
from src.domain.entities.solicitud import ahora
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.services.errores import ConflictoEstado, DatosInvalidos, NoEncontrado
from src.domain.services.solicitud_service import SolicitudService
from src.domain.value_objects.estados import ResultadoValidacion
from src.application.use_cases.verificar_referencias_normativas import verificar_referencias_normativas


class ValidarPrediccion:
    def __init__(self, servicios: ServiciosSolicitud):
        self.s = servicios

    def ejecutar(self, solicitud_id: UUID, usuario: UsuarioActual, prediccion_id: UUID,
                resultado: ResultadoValidacion, tipo_informe_id: UUID | None = None,
                area_destino_id: UUID | None = None, normativa_ids: list[UUID] | None = None):
        if resultado == ResultadoValidacion.PENDIENTE:
            raise DatosInvalidos("Debe aceptar, corregir o rechazar la predicción")
        with self.s.uow.transaccion():
            solicitud = self.s.obtener(solicitud_id, usuario, escritura=True)
            SolicitudService.editable(solicitud)
            p = self.s.predicciones.ultima(solicitud_id)
            if not p:
                raise NoEncontrado("No hay una predicción para validar")
            if p.id != prediccion_id:
                raise ConflictoEstado("Solo puede validar la predicción más reciente")
            if p.parametros.get("asunto") != solicitud.asunto:
                raise ConflictoEstado("El asunto cambió; solicite una nueva predicción")
            predichas = {n.normativa_id for n in p.normativas}
            seleccionadas = predichas if normativa_ids is None else set(normativa_ids)
            if normativa_ids is not None and len(normativa_ids) != len(seleccionadas):
                raise DatosInvalidos("No repita normativas")
            if seleccionadas - predichas:
                raise DatosInvalidos("Solo se pueden confirmar normativas de esta predicción")
            if resultado == ResultadoValidacion.CORREGIDA:
                if tipo_informe_id is None or area_destino_id is None:
                    raise DatosInvalidos("La corrección requiere tipo de informe y área de destino")
            elif tipo_informe_id is not None or area_destino_id is not None:
                raise DatosInvalidos("Use CORREGIDA para modificar el contexto")
            if resultado == ResultadoValidacion.ACEPTADA and seleccionadas != predichas:
                raise DatosInvalidos("Use CORREGIDA para cambiar las normativas confirmadas")
            if resultado != ResultadoValidacion.RECHAZADA:
                verificar_referencias_normativas(self.s.catalogos, p, seleccionadas)
                solicitud.tipo_informe_id = tipo_informe_id or p.tipo_informe_predicho_id
                solicitud.area_destino_id = area_destino_id or p.area_destino_predicha_id
                # Al confirmar un contexto distinto se vuelve a elegir plantilla.
                # No se conservan valores que pertenecen al formato anterior.
                if solicitud.plantilla_id:
                    plantilla = self.s.plantilla(solicitud.plantilla_id)
                    if (plantilla.tipo_informe_id != solicitud.tipo_informe_id or
                            (plantilla.area_id and plantilla.area_id != solicitud.area_destino_id)):
                        solicitud.plantilla_id = None
                        solicitud.valores = []
                self.s.validar_referencias(solicitud)
            p.resultado_validacion = resultado
            p.validado_por, p.validado_at = usuario.id, ahora()
            for n in p.normativas:
                n.aceptada = resultado != ResultadoValidacion.RECHAZADA and n.normativa_id in seleccionadas
            self.s.predicciones.guardar(p)
            self.s.recalcular_estado(solicitud)
            self.s.guardar(solicitud)
            return p
