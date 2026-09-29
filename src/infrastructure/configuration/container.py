
from src.adapters.out.ai.sklearn_context_predictor import SklearnContextPredictor
from src.adapters.out.ai.generador_borrador_ollama import GeneradorBorradorOllama
from src.adapters.out.persistence.catalogo_repository_memory import CatalogoRepositoryMemory
from src.adapters.out.persistence.informe_repository_memory import InformeRepositoryMemory
from src.adapters.out.persistence.memoria import Memoria
from src.adapters.out.persistence.plantilla_repository_memory import PlantillaRepositoryMemory
from src.adapters.out.persistence.prediccion_repository_memory import PrediccionRepositoryMemory
from src.adapters.out.persistence.solicitud_repository_memory import SolicitudRepositoryMemory
from src.application.use_cases.actualizar_borrador import ActualizarBorrador
from src.application.use_cases.actualizar_solicitud import ActualizarSolicitud
from src.application.use_cases.consultar_catalogos import ConsultarCatalogos
from src.application.use_cases.crear_solicitud import CrearSolicitud
from src.application.use_cases.generar_borrador import GenerarBorrador
from src.application.use_cases.guardar_valores_solicitud import GuardarValoresSolicitud
from src.application.use_cases.guardar_solicitud_completa import GuardarSolicitudCompleta
from src.application.use_cases.obtener_informe import ObtenerInforme
from src.application.use_cases.obtener_solicitud import ObtenerSolicitud
from src.application.use_cases.obtener_contexto import ObtenerContexto
from src.application.use_cases.predecir_contexto import PredecirContexto
from src.application.use_cases.servicios_solicitud import ServiciosSolicitud
from src.application.use_cases.validar_prediccion import ValidarPrediccion
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.configuration.database import DatabaseSettings


class Container:
    """Composición explícita; PostgreSQL nunca cae silenciosamente a memoria."""

    def __init__(self, settings=None, *, database_settings=None, predictor=None):
        settings = settings or Settings.from_env()
        self.persistence_mode = settings.persistence_mode

        if self.persistence_mode == "memory":
            self.memoria = Memoria()
            self.uow = self.memoria
            self.solicitudes = SolicitudRepositoryMemory(self.memoria)
            self.plantillas = PlantillaRepositoryMemory()
            self.predicciones = PrediccionRepositoryMemory(self.memoria)
            self.informes = InformeRepositoryMemory(self.memoria)
            self.catalogos = CatalogoRepositoryMemory()

        elif self.persistence_mode == "postgres":
            from src.adapters.out.persistence.postgres import (
                PostgresUnidadTrabajo,
                SolicitudRepositoryPostgres,
                PlantillaRepositoryPostgres,
                PrediccionRepositoryPostgres,
                InformeRepositoryPostgres,
                CatalogoRepositoryPostgres,
            )

            self.uow = PostgresUnidadTrabajo(
                database_settings or DatabaseSettings.from_env()
            )

            self.solicitudes = SolicitudRepositoryPostgres(self.uow)
            self.plantillas = PlantillaRepositoryPostgres(self.uow)
            self.predicciones = PrediccionRepositoryPostgres(self.uow)
            self.informes = InformeRepositoryPostgres(self.uow)
            self.catalogos = CatalogoRepositoryPostgres(self.uow)

            from src.adapters.out.persistence.perfil_repository_postgres import (
                PerfilRepositoryPostgres
            )

            self.perfiles = PerfilRepositoryPostgres(self.uow)

        else:
            raise ValueError("Modo de persistencia desconocido")

        self.servicios = ServiciosSolicitud(
            self.solicitudes,
            self.plantillas,
            self.predicciones,
            self.catalogos,
            self.uow
        )

        self.crear_solicitud = CrearSolicitud(self.servicios)
        self.obtener_solicitud = ObtenerSolicitud(self.servicios)
        self.obtener_contexto = ObtenerContexto(self.servicios)
        self.actualizar_solicitud = ActualizarSolicitud(self.servicios)
        self.guardar_valores = GuardarValoresSolicitud(self.servicios)

        self.guardar_solicitud_completa = GuardarSolicitudCompleta(
            self.servicios
        )

        predictor = predictor or SklearnContextPredictor()

        if self.persistence_mode == "postgres":
            from src.adapters.out.ai.context_predictor_catalogo import (
                ContextPredictorCatalogo
            )

            predictor = ContextPredictorCatalogo(
                predictor,
                self.catalogos
            )

        self.predecir_contexto = PredecirContexto(
            self.servicios,
            predictor
        )

        self.validar_prediccion = ValidarPrediccion(self.servicios)

        self.generar_borrador = GenerarBorrador(
            self.servicios,
            self.informes,
            GeneradorBorradorOllama()
        )

        self.obtener_informe = ObtenerInforme(
            self.servicios,
            self.informes
        )

        self.actualizar_borrador = ActualizarBorrador(
            self.servicios,
            self.informes
        )

        self.consultar_catalogos = ConsultarCatalogos(
            self.catalogos,
            self.plantillas
        )