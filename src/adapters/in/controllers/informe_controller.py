from uuid import UUID

from fastapi import APIRouter, Path, Response
from typing import Annotated

from src.infrastructure.dependencies import Dependencias, Usuario
from ..schemas.error_response import RESPUESTAS_ERROR
from ..schemas.informe_request import InformeRequest
from ..schemas.informe_response import InformeResponse, representar_informe


router = APIRouter(prefix="/informes", tags=["Informes"], responses=RESPUESTAS_ERROR)


@router.get("/{informe_id}", response_model=InformeResponse)
def obtener(informe_id: UUID, usuario: Usuario, deps: Dependencias):
    return representar_informe(deps.obtener_informe.ejecutar(informe_id, usuario))


@router.get("/{informe_id}/versiones/{numero_version}", response_model=InformeResponse,
            summary="Consultar el contenido y estructura de una versión guardada")
def obtener_version(informe_id: UUID, numero_version: Annotated[int, Path(ge=1)], usuario: Usuario, deps: Dependencias):
    return representar_informe(deps.obtener_informe.ejecutar(informe_id, usuario), numero_version)


@router.get("/{informe_id}/versiones/{numero_version}/docx", response_class=Response,
            summary="Descargar una versión guardada en formato Word piloto",
            description="Requiere los mismos permisos que consultar el informe. Usa su contenido y estructura guardados, "
                        "sin invocar Ollama ni guardar cambios. Formato piloto no institucional.",
            responses={200: {"content": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}}}})
def descargar_docx(informe_id: UUID, numero_version: Annotated[int, Path(ge=1)], usuario: Usuario, deps: Dependencias):
    contenido = deps.exportar_informe.ejecutar(informe_id, numero_version, usuario)
    return Response(contenido, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="NAXJI-{informe_id}-v{numero_version}.docx"',
                             "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.put("/{informe_id}", response_model=InformeResponse, summary="Guardar una nueva versión del borrador")
def actualizar(informe_id: UUID, request: InformeRequest, usuario: Usuario, deps: Dependencias):
    informe = deps.actualizar_borrador.ejecutar(informe_id, usuario, **request.model_dump())
    return representar_informe(informe)
