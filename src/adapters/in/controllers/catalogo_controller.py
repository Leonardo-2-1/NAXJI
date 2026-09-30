from uuid import UUID

from fastapi import APIRouter

from src.infrastructure.dependencies import Dependencias, Usuario
from ..schemas.catalogo_response import AreaResponse, CampoResponse, CatalogoResponse, PlantillaResponse
from ..schemas.catalogo_response import representar_plantilla
from ..schemas.error_response import RESPUESTAS_ERROR


router = APIRouter(tags=["Catálogos"], responses=RESPUESTAS_ERROR)


@router.get("/tipos-informe", response_model=list[CatalogoResponse])
def tipos(usuario: Usuario, deps: Dependencias):
    return deps.consultar_catalogos.tipos(usuario)


@router.get("/areas", response_model=list[AreaResponse])
def areas(usuario: Usuario, deps: Dependencias):
    return deps.consultar_catalogos.areas(usuario)


@router.get("/plantillas", response_model=list[PlantillaResponse])
def plantillas(usuario: Usuario, deps: Dependencias, tipo_informe_id: UUID | None = None):
    return [representar_plantilla(p) for p in deps.consultar_catalogos.plantillas(usuario, tipo_informe_id)]


@router.get("/plantillas/{plantilla_id}/campos", response_model=list[CampoResponse])
def campos(plantilla_id: UUID, usuario: Usuario, deps: Dependencias):
    return deps.consultar_catalogos.campos(usuario, plantilla_id)
