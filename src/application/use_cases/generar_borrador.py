from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import logging
from math import ceil
from uuid import UUID

from src.application.ports.output.generador_borrador import ContextoConfirmado, GeneradorBorrador, NormaConfirmada
from src.application.ports.output.informe_repository import InformeRepository
from src.application.use_cases.servicios_solicitud import ServiciosSolicitud
from src.domain.entities.informe import Informe, VersionInforme
from src.domain.entities.solicitud import ahora
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.services.errores import ConflictoEstado, DatosInvalidos, ErrorGeneracion, NoEncontrado
from src.domain.services.informe_service import validar_contenido
from src.domain.services.solicitud_service import SolicitudService
from src.domain.value_objects.estado_solicitud import EstadoSolicitud
from src.domain.value_objects.estados import OrigenVersion, ResultadoValidacion
from src.domain.value_objects.seccion_salida import secciones_efectivas
from src.application.use_cases.verificar_referencias_normativas import verificar_referencias_normativas


logger = logging.getLogger(__name__)


class GenerarBorrador:
    def __init__(self, servicios: ServiciosSolicitud, informes: InformeRepository,
                 generador: GeneradorBorrador, *, tiempo_maximo=300.0, reloj=ahora):
        self.s, self.informes, self.generador = servicios, informes, generador
        self.plazo = timedelta(seconds=tiempo_maximo + 30)
        self.reloj = reloj

    def _vencida(self, solicitud):
        return self.reloj() >= solicitud.updated_at + self.plazo

    def _restaurar_estado(self, solicitud):
        solicitud.estado = EstadoSolicitud.BORRADOR
        try:
            self.s.recalcular_estado(solicitud)
        except (DatosInvalidos, NoEncontrado):
            # Una plantilla retirada durante la inferencia requiere corregir el formulario.
            solicitud.estado = EstadoSolicitud.BORRADOR
        self.s.guardar(solicitud)

    def _recuperar_vencida(self, solicitud_id, usuario):
        # También recupera procesos caídos/reiniciados. Solo escribe tras vencer la reserva.
        with self.s.uow.transaccion():
            solicitud = self.s.obtener(solicitud_id, usuario, escritura=True)
            if solicitud.estado != EstadoSolicitud.PROCESANDO:
                return
            if not self._vencida(solicitud):
                segundos = max(1, ceil((solicitud.updated_at + self.plazo - self.reloj()).total_seconds()))
                raise ConflictoEstado(f"Hay una generación en curso. Si se interrumpió, reintente en {segundos} segundos.")
            if self.informes.obtener_por_solicitud(solicitud.id):
                solicitud.estado = EstadoSolicitud.GENERADA
                self.s.guardar(solicitud)
            else:
                self._restaurar_estado(solicitud)

    def _contexto(self, solicitud, prediccion):
        verificar_referencias_normativas(self.s.catalogos, prediccion,
                                        {n.normativa_id for n in prediccion.normativas if n.aceptada})
        tipos = {t.id: t.nombre for t in self.s.catalogos.tipos_informe()}
        areas = {a.id: a.nombre for a in self.s.catalogos.areas()}
        normas = []
        for propuesta in prediccion.normativas:
            if not propuesta.aceptada:
                continue
            norma = self.s.catalogos.normativa(propuesta.normativa_id)
            if norma is None or not norma.activo:
                raise DatosInvalidos("Una norma seleccionada ya no está disponible; revise el contexto")
            normas.append(NormaConfirmada(norma.id, norma.codigo, norma.titulo))
        return ContextoConfirmado(solicitud.tipo_informe_id, solicitud.area_destino_id,
                                  tuple(n.id for n in normas), tipos[solicitud.tipo_informe_id],
                                  areas[solicitud.area_destino_id], tuple(normas)), areas

    def _reservar(self, solicitud_id, usuario):
        with self.s.uow.transaccion():
            solicitud = self.s.obtener(solicitud_id, usuario, escritura=True)
            SolicitudService.editable(solicitud)
            if self.informes.obtener_por_solicitud(solicitud.id):
                raise ConflictoEstado("Ya existe un informe para esta solicitud")
            p = self.s.predicciones.ultima(solicitud.id)
            if not p or p.resultado_validacion not in (ResultadoValidacion.ACEPTADA, ResultadoValidacion.CORREGIDA):
                raise ConflictoEstado("Debe confirmar o corregir el contexto antes de generar")
            if p.parametros.get("asunto") != solicitud.asunto:
                raise ConflictoEstado("El asunto cambió; solicite y confirme una nueva predicción")
            self.s.validar_referencias(solicitud)
            plantilla = self.s.plantilla(solicitud.plantilla_id)
            secciones_efectivas(plantilla.secciones_salida)
            SolicitudService.validar_obligatorios(solicitud, plantilla)
            self.s.recalcular_estado(solicitud)
            if solicitud.estado != EstadoSolicitud.LISTA_PARA_GENERAR:
                raise ConflictoEstado("La solicitud no está lista para generar")
            contexto, areas = self._contexto(solicitud, p)
            solicitud.estado = EstadoSolicitud.PROCESANDO
            # Usa el timestamp devuelto por PostgreSQL, cuya autoridad es el trigger.
            solicitud = self.s.guardar(solicitud)
            return deepcopy((solicitud, plantilla, p, contexto, areas))

    @staticmethod
    def _mismo_intento(actual, reservada):
        return actual.estado == EstadoSolicitud.PROCESANDO and actual.updated_at == reservada.updated_at

    def _liberar(self, reservada, usuario):
        try:
            with self.s.uow.transaccion():
                actual = self.s.obtener(reservada.id, usuario, escritura=True)
                if self._mismo_intento(actual, reservada):
                    self._restaurar_estado(actual)
        except Exception:
            # Una caída de DB no oculta el error original. El próximo POST recupera
            # la reserva al vencer; no registra prompts ni excepciones del proveedor.
            logger.warning("No se pudo liberar una reserva de generación; podrá recuperarse al vencer")

    def ejecutar(self, solicitud_id: UUID, usuario: UsuarioActual, instrucciones: str = ""):
        if not isinstance(instrucciones, str):
            raise DatosInvalidos("Las instrucciones deben ser texto")
        self._recuperar_vencida(solicitud_id, usuario)
        solicitud, plantilla, prediccion, contexto, areas = self._reservar(solicitud_id, usuario)
        secciones = secciones_efectivas(plantilla.secciones_salida)
        claves = {c.id: c.clave for c in plantilla.campos if c.activo}
        datos = {claves[v.campo_plantilla_id]: v.valor for v in solicitud.valores}
        try:
            # Ninguna transacción ni conexión a PostgreSQL vive durante la inferencia.
            try:
                resultado = self.generador.generar(solicitud.asunto,
                    replace(plantilla, secciones_salida=deepcopy(secciones)), datos, contexto, instrucciones)
            except ErrorGeneracion:
                raise
            except Exception:
                raise ErrorGeneracion() from None
            validar_contenido(resultado.contenido, secciones)
            if resultado.contenido.keys() - {s.clave for s in secciones}:
                raise DatosInvalidos("El generador devolvió secciones ajenas a la plantilla")
            contenido = {s.clave: resultado.contenido[s.clave] for s in secciones if s.clave in resultado.contenido}
            contenido["encabezado"] = {
                "asunto": solicitud.asunto,
                "area_origen": areas.get(solicitud.area_origen_id),
                "area_destino": areas.get(solicitud.area_destino_id),
                "autor_id": str(solicitud.usuario_id),
            }
            with self.s.uow.transaccion():
                actual = self.s.obtener(solicitud.id, usuario, escritura=True)
                if not self._mismo_intento(actual, solicitud) or self._vencida(actual):
                    raise ConflictoEstado("La generación perdió su vigencia; consulte la solicitud y reintente")
                if self.informes.obtener_por_solicitud(solicitud.id):
                    raise ConflictoEstado("Ya existe un informe para esta solicitud")
                self.s.validar_referencias(actual)
                if (self.s.plantilla(actual.plantilla_id) != plantilla
                        or self.s.predicciones.ultima(actual.id) != prediccion
                        or actual != solicitud):
                    raise ConflictoEstado("La solicitud, el contexto o la plantilla cambiaron durante la generación; reintente")
                verificar_referencias_normativas(self.s.catalogos, prediccion,
                                                {n.normativa_id for n in prediccion.normativas if n.aceptada})
                informe = Informe(actual.id, plantilla.id, usuario.id, titulo=actual.asunto)
                informe.versiones.append(VersionInforme(
                    informe.id, 1, contenido, OrigenVersion.IA, usuario.id,
                    modelo_ia=resultado.modelo_ia, prompt_version=resultado.prompt_version,
                    secciones_salida=deepcopy(secciones),
                ))
                self.informes.guardar(informe)
                actual.estado = EstadoSolicitud.GENERADA
                self.s.guardar(actual)
                return informe
        except Exception:
            # Solo libera SU reserva. Una respuesta/fallo tardío no pisa otro intento.
            self._liberar(solicitud, usuario)
            raise
