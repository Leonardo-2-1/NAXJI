from uuid import UUID

from fastapi import APIRouter

from src.application.ports.input.solicitud_use_case import DatosSolicitud
from src.infrastructure.dependencies import Dependencias, Usuario
from ..schemas.error_response import RESPUESTAS_ERROR
from ..schemas.solicitud_request import (
    ActualizarSolicitudRequest, SolicitudRequest, ValoresSolicitudRequest, SolicitudCompletaRequest,
)
from ..schemas.solicitud_response import SolicitudResponse


router = APIRouter(prefix="/solicitudes", tags=["Solicitudes"], responses=RESPUESTAS_ERROR)


@router.post("", response_model=SolicitudResponse, status_code=201, summary="Crear una solicitud en BORRADOR")
@router.post("/", response_model=SolicitudResponse, status_code=201, include_in_schema=False)
def crear(request: SolicitudRequest, usuario: Usuario, deps: Dependencias):
    return deps.crear_solicitud.ejecutar(usuario, DatosSolicitud(**request.model_dump()))


@router.post("/completa", response_model=SolicitudResponse, status_code=201,
             summary="Registrar formulario completo y valores de forma atómica")
def crear_completa(request: SolicitudCompletaRequest, usuario: Usuario, deps: Dependencias):
    return deps.guardar_solicitud_completa.ejecutar(
        usuario, DatosSolicitud(**request.model_dump(exclude={"valores"})),
        {v.campo_plantilla_id: v.valor for v in request.valores})


@router.put("/{solicitud_id}/completa", response_model=SolicitudResponse,
            summary="Actualizar formulario completo; revierte todo si falta un obligatorio")
def actualizar_completa(solicitud_id: UUID, request: SolicitudCompletaRequest,
                       usuario: Usuario, deps: Dependencias):
    return deps.guardar_solicitud_completa.ejecutar(
        usuario, DatosSolicitud(**request.model_dump(exclude={"valores"})),
        {v.campo_plantilla_id: v.valor for v in request.valores}, solicitud_id)


@router.get("/{solicitud_id}", response_model=SolicitudResponse)
def obtener(solicitud_id: UUID, usuario: Usuario, deps: Dependencias):
    return deps.obtener_solicitud.ejecutar(solicitud_id, usuario)


@router.put("/{solicitud_id}", response_model=SolicitudResponse,
            summary="Actualizar campos indicados o cancelar la solicitud")
def actualizar(solicitud_id: UUID, request: ActualizarSolicitudRequest, usuario: Usuario, deps: Dependencias):
    return deps.actualizar_solicitud.ejecutar(solicitud_id, usuario, request.model_dump(exclude_unset=True))


@router.put("/{solicitud_id}/valores", response_model=SolicitudResponse,
            summary="Reemplazar los valores del formulario; permite guardar datos incompletos")
def guardar_valores(solicitud_id: UUID, request: ValoresSolicitudRequest, usuario: Usuario, deps: Dependencias):
    valores = {v.campo_plantilla_id: v.valor for v in request.valores}
    return deps.guardar_valores.ejecutar(solicitud_id, usuario, valores)
