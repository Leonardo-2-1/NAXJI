from uuid import UUID

from src.application.ports.output.informe_repository import InformeRepository
from src.application.use_cases.servicios_solicitud import ServiciosSolicitud
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.services.errores import NoEncontrado


class ObtenerInforme:
    def __init__(self, servicios: ServiciosSolicitud, informes: InformeRepository):
        self.s, self.informes = servicios, informes

    def ejecutar(self, informe_id: UUID, usuario: UsuarioActual):
        informe = self.informes.obtener_por_id(informe_id)
        if informe is None:
            raise NoEncontrado("Informe no encontrado")
        self.s.obtener(informe.solicitud_id, usuario)
        return informe

    def por_solicitud(self, solicitud_id: UUID, usuario: UsuarioActual):
        self.s.obtener(solicitud_id, usuario)
        informe = self.informes.obtener_por_solicitud(solicitud_id)
        if informe is None:
            raise NoEncontrado("Informe no encontrado")
        return informe
