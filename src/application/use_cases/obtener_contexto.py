class ObtenerContexto:
    def __init__(self, servicios):
        self.s = servicios

    def ejecutar(self, solicitud_id, usuario):
        with self.s.uow.transaccion():
            self.s.obtener(solicitud_id, usuario)
            return self.s.predicciones.ultima(solicitud_id)
