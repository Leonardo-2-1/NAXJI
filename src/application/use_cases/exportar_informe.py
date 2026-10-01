from src.domain.services.errores import NoEncontrado


def version_guardada(informe, numero_version):
    version = next((v for v in informe.versiones if v.numero_version == numero_version), None)
    if version is None:
        raise NoEncontrado("Versión guardada no encontrada")
    return version


class ExportarInforme:
    def __init__(self, obtener_informe, exportador):
        self.obtener_informe, self.exportador = obtener_informe, exportador

    def ejecutar(self, informe_id, numero_version, usuario):
        # Aplica exactamente los permisos de lectura del informe y su solicitud.
        # No mantiene una transacción ni permite al cliente sustituir contenido.
        informe = self.obtener_informe.ejecutar(informe_id, usuario)
        version = version_guardada(informe, numero_version)
        return self.exportador.exportar(informe, version)
