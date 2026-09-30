from uuid import UUID
from copy import deepcopy
from dataclasses import replace

from src.application.ports.output.generador_borrador import ContextoConfirmado, GeneradorBorrador
from src.application.ports.output.informe_repository import InformeRepository
from src.application.use_cases.servicios_solicitud import ServiciosSolicitud
from src.domain.entities.informe import Informe, VersionInforme
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.services.errores import ConflictoEstado, DatosInvalidos
from src.domain.services.informe_service import validar_contenido
from src.domain.services.solicitud_service import SolicitudService
from src.domain.value_objects.estado_solicitud import EstadoSolicitud
from src.domain.value_objects.estados import OrigenVersion, ResultadoValidacion
from src.domain.value_objects.seccion_salida import secciones_efectivas


class GenerarBorrador:

    def __init__(self, servicios: ServiciosSolicitud, informes: InformeRepository,
                 generador: GeneradorBorrador):
        self.s, self.informes, self.generador = servicios, informes, generador

    def ejecutar(self, solicitud_id: UUID, usuario: UsuarioActual, instrucciones: str = ""):
        if not isinstance(instrucciones, str):
            raise DatosInvalidos("Las instrucciones deben ser texto")
        with self.s.uow.transaccion():
            solicitud = self.s.obtener(solicitud_id, usuario, escritura=True)
            SolicitudService.editable(solicitud)
            if self.informes.obtener_por_solicitud(solicitud.id):
                raise ConflictoEstado("Ya existe un informe para esta solicitud")
            p = self.s.predicciones.ultima(solicitud.id)
            if not p or p.resultado_validacion not in (ResultadoValidacion.ACEPTADA, ResultadoValidacion.CORREGIDA):
                raise ConflictoEstado("Debe confirmar o corregir el contexto antes de generar")
            self.s.validar_referencias(solicitud)
            plantilla = self.s.plantilla(solicitud.plantilla_id)
            secciones = secciones_efectivas(plantilla.secciones_salida)
            SolicitudService.validar_obligatorios(solicitud, plantilla)
            self.s.recalcular_estado(solicitud)
            if solicitud.estado != EstadoSolicitud.LISTA_PARA_GENERAR:
                raise ConflictoEstado("La solicitud no está lista para generar")
            solicitud.estado = EstadoSolicitud.PROCESANDO
            self.s.guardar(solicitud)
            claves = {c.id: c.clave for c in plantilla.campos if c.activo}
            datos = {claves[v.campo_plantilla_id]: v.valor for v in solicitud.valores}
            contexto = ContextoConfirmado(solicitud.tipo_informe_id, solicitud.area_destino_id,
                                           tuple(n.normativa_id for n in p.normativas if n.aceptada))
            resultado = self.generador.generar(
                solicitud.asunto, replace(plantilla, secciones_salida=deepcopy(secciones)), datos, contexto, instrucciones,
            )
            validar_contenido(resultado.contenido, secciones)
            if resultado.contenido.keys() - {s.clave for s in secciones}:
                raise DatosInvalidos("El generador devolvió secciones ajenas a la plantilla")
            areas = {a.id: a.nombre for a in self.s.catalogos.areas()}
            resultado.contenido['encabezado'] = {
                'asunto': solicitud.asunto,
                'area_origen': areas.get(solicitud.area_origen_id),
                'area_destino': areas.get(solicitud.area_destino_id),
                'autor_id': str(solicitud.usuario_id),
            }
            informe = Informe(solicitud.id, plantilla.id, usuario.id, titulo=solicitud.asunto)
            informe.versiones.append(VersionInforme(
                informe.id, 1, resultado.contenido, OrigenVersion.IA, usuario.id,
                modelo_ia=resultado.modelo_ia, prompt_version=resultado.prompt_version,
                secciones_salida=deepcopy(secciones),
            ))
            self.informes.guardar(informe)
            solicitud.estado = EstadoSolicitud.GENERADA
            self.s.guardar(solicitud)
            return informe
