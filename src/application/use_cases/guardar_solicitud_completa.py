"""Guardado atómico del formulario completo; los borradores conservan su contrato."""
from src.application.use_cases.crear_solicitud import CrearSolicitud
from src.application.use_cases.actualizar_solicitud import ActualizarSolicitud
from src.application.use_cases.guardar_valores_solicitud import GuardarValoresSolicitud
from src.domain.services.solicitud_service import SolicitudService
from src.domain.services.errores import DatosInvalidos


class GuardarSolicitudCompleta:
    def __init__(self, servicios):
        self.s = servicios

    def ejecutar(self, usuario, datos, valores, solicitud_id=None):
        with self.s.uow.transaccion():
            if solicitud_id:
                from dataclasses import asdict
                solicitud = ActualizarSolicitud(self.s).ejecutar(solicitud_id, usuario, asdict(datos))
            else:
                solicitud = CrearSolicitud(self.s).ejecutar(usuario, datos)
            self.s.validar_referencias(solicitud)
            if not all((solicitud.tipo_informe_id, solicitud.plantilla_id,
                        solicitud.area_origen_id, solicitud.area_destino_id)):
                raise DatosInvalidos("El formulario completo requiere tipo, plantilla y áreas de origen y destino")
            solicitud = GuardarValoresSolicitud(self.s).ejecutar(solicitud.id, usuario, valores)
            SolicitudService.validar_obligatorios(solicitud, self.s.plantilla(solicitud.plantilla_id))
            return solicitud
