from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from src.application.ports.output.catalogo_repository import CatalogoRepository
from src.domain.entities.prediccion_contexto import PrediccionContexto
from src.domain.value_objects.estados import ResultadoValidacion
from .base import ResponseModel


class CategoriaPredicha(ResponseModel):
    id: UUID
    codigo: str | None
    nombre: str
    confianza: float | None = Field(ge=0, le=1)


class CorrespondenciaResponse(ResponseModel):
    etiqueta: str
    estado_verificacion: str
    documento_codigo: str | None
    documento_titulo: str
    documento_numero: str
    documento_url: str
    documento_publicacion: date
    fuente_url: str
    fuente_vigencia_url: str
    verificado_en: date
    ambito: str
    vigencia: str
    justificacion: str
    confianza_tema: float | None = Field(ge=0, le=1)


class TemaNormativoResponse(ResponseModel):
    codigo: str
    etiqueta: str
    confianza: float | None = Field(ge=0, le=1)
    normativa_ids: list[UUID]


class NormativaResponse(ResponseModel):
    normativa_id: UUID
    codigo: str | None
    titulo: str
    confianza: float | None = Field(ge=0, le=1, description="Máxima confianza de los temas asociados; no es probabilidad de vigencia ni aplicabilidad jurídica")
    orden: int | None
    aceptada: bool | None
    correspondencias: list[CorrespondenciaResponse] = Field(default_factory=list)


class PrediccionResponse(ResponseModel):
    id: UUID
    solicitud_id: UUID
    modelo: str
    version_modelo: str | None
    es_mock: bool
    resultado_validacion: ResultadoValidacion
    validado_por: UUID | None
    validado_at: datetime | None
    tipo_informe: CategoriaPredicha | None
    area_destino: CategoriaPredicha | None
    normativas: list[NormativaResponse]
    advertencias: list[str] = Field(default_factory=list)
    temas_normativos: list[TemaNormativoResponse] = Field(default_factory=list)


def representar_prediccion(p: PrediccionContexto, catalogos: CatalogoRepository) -> PrediccionResponse:
    tipo = next((t for t in catalogos.tipos_informe() if t.id == p.tipo_informe_predicho_id), None)
    area = next((a for a in catalogos.areas() if a.id == p.area_destino_predicha_id), None)
    normas = []
    for n in p.normativas:
        normativa = catalogos.normativa(n.normativa_id)
        if normativa:
            normas.append(NormativaResponse(
                normativa_id=normativa.id, codigo=normativa.codigo, titulo=normativa.titulo,
                confianza=n.confianza, orden=n.orden, aceptada=n.aceptada,
                correspondencias=p.parametros.get("correspondencias_normativas", {}).get(str(n.normativa_id), []),
            ))
    def categoria(item, confianza):
        return CategoriaPredicha(id=item.id, codigo=item.codigo, nombre=item.nombre,
                                  confianza=confianza) if item else None
    return PrediccionResponse(
        id=p.id, solicitud_id=p.solicitud_id, modelo=p.modelo, version_modelo=p.version_modelo,
        es_mock=p.modelo.startswith("MOCK_"), resultado_validacion=p.resultado_validacion,
        validado_por=p.validado_por, validado_at=p.validado_at,
        tipo_informe=categoria(tipo, p.confianza_tipo),
        area_destino=categoria(area, p.confianza_area), normativas=normas,
        advertencias=p.parametros.get('advertencias_catalogo', []),
        temas_normativos=p.parametros.get('temas_normativos', []),
    )
