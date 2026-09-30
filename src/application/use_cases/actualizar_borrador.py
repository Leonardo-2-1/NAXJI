from uuid import UUID
from copy import deepcopy

from src.application.ports.output.informe_repository import InformeRepository
from src.application.use_cases.obtener_informe import ObtenerInforme
from src.application.use_cases.servicios_solicitud import ServiciosSolicitud, autorizar
from src.domain.entities.informe import VersionInforme
from src.domain.entities.solicitud import ahora
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.services.errores import ConflictoEstado, DatosInvalidos
from src.domain.services.informe_service import validar_contenido
from src.domain.value_objects.estados import EstadoInforme, OrigenVersion
from src.domain.value_objects.seccion_salida import CLAVES_TECNICAS, secciones_efectivas


class ActualizarBorrador:
    def __init__(self, servicios: ServiciosSolicitud, informes: InformeRepository):
        self.s, self.informes = servicios, informes

    def ejecutar(self, informe_id: UUID, usuario: UsuarioActual, contenido: dict,
                numero_version: int, titulo: str | None = None):
        autorizar(usuario, escritura=True)
        if titulo is not None and not titulo.strip():
            raise DatosInvalidos("El título no puede estar vacío")
        with self.s.uow.transaccion():
            informe = ObtenerInforme(self.s, self.informes).ejecutar(informe_id, usuario)
            if informe.estado != EstadoInforme.BORRADOR:
                raise ConflictoEstado("Solo se puede editar un informe en BORRADOR")
            anterior = max(informe.versiones, key=lambda v: v.numero_version)
            if numero_version != anterior.numero_version:
                raise ConflictoEstado("El borrador cambió; recargue su última versión")
            validar_contenido(contenido, anterior.secciones_salida)
            claves = {s.clave for s in secciones_efectivas(anterior.secciones_salida)}
            if anterior.secciones_salida is not None and contenido.keys() - claves - anterior.contenido.keys():
                raise DatosInvalidos("El contenido incluye secciones ajenas a esta versión")
            # Conserva metadatos de versiones antiguas incluso si un cliente omite esas claves.
            protegido = {k: v for k, v in anterior.contenido.items()
                         if k not in claves and (k in CLAVES_TECNICAS or not isinstance(v, str)
                                                 or anterior.secciones_salida is not None)}
            for clave, valor in protegido.items():
                if clave in contenido and contenido[clave] != valor:
                    raise DatosInvalidos(f"El dato {clave} es de solo lectura")
            contenido = {**deepcopy(protegido), **contenido}
            informe.versiones.append(VersionInforme(
                informe.id, anterior.numero_version + 1, contenido, OrigenVersion.USUARIO, usuario.id,
                secciones_salida=deepcopy(anterior.secciones_salida),
            ))
            if titulo is not None:
                informe.titulo = titulo.strip()
            informe.updated_at = ahora()
            return self.informes.guardar(informe)
