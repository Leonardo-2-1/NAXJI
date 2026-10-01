"""Fixtures ficticias en memoria para pruebas del backend.

IMPORTANTE:
- No son registros reales de Supabase.
- Las normativas son etiquetas utilizadas por la PoC RF-IA-01.
- No representan necesariamente normas municipales oficiales vigentes.
"""

from uuid import NAMESPACE_URL, uuid5

from src.domain.entities.catalogo import (
    AreaMunicipal,
    Normativa,
    TipoInforme,
)
from src.domain.entities.plantilla import (
    CampoPlantilla,
    Plantilla,
)
from src.domain.value_objects.estados import TipoDato


def demo_id(nombre: str):
    return uuid5(
        NAMESPACE_URL,
        f"naxji:demo:{nombre}"
    )


# ============================================================
# TIPOS DE INFORME
# ============================================================

TIPOS = [
    TipoInforme(
        demo_id(codigo),
        codigo,
        nombre
    )
    for codigo, nombre in (
        (
            "INFORME_TECNICO",
            "Informe Técnico"
        ),
        (
            "INFORME_LEGAL",
            "Informe Legal"
        ),
        (
            "INFORME_INSPECCION",
            "Informe de Inspección"
        ),
        (
            "MEMORANDO",
            "Memorando"
        ),
    )
]


# ============================================================
# ÁREAS
#
# Deben coincidir con las áreas que conoce el modelo
# entrenado en Colab.
# ============================================================

AREAS = [
    AreaMunicipal(
        demo_id("AREA_ECOLOGIA"),
        "AREA_ECOLOGIA",
        "Subgerencia de Ecología y Medio Ambiente"
    ),

    AreaMunicipal(
        demo_id("AREA_SERVICIOS_PUBLICOS"),
        "AREA_SERVICIOS_PUBLICOS",
        "Gerencia de Servicios Públicos"
    ),

    AreaMunicipal(
        demo_id("AREA_DESARROLLO_URBANO"),
        "AREA_DESARROLLO_URBANO",
        "Gerencia de Desarrollo Urbano"
    ),

    AreaMunicipal(
        demo_id("AREA_DESARROLLO_ECONOMICO"),
        "AREA_DESARROLLO_ECONOMICO",
        "Gerencia de Desarrollo Económico"
    ),

    AreaMunicipal(
        demo_id("AREA_RIESGO_DESASTRES"),
        "AREA_RIESGO_DESASTRES",
        "Subgerencia de Gestión del Riesgo de Desastres"
    ),

    AreaMunicipal(
        demo_id("AREA_ASESORIA_JURIDICA"),
        "AREA_ASESORIA_JURIDICA",
        "Oficina de Asesoría Jurídica"
    ),
]


# ============================================================
# NORMATIVAS / ETIQUETAS DE LA PoC
#
# Estas etiquetas deben coincidir EXACTAMENTE con mlb.classes_
# del modelo entrenado.
# ============================================================

NORMATIVAS = [
    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa municipal sobre gestión de residuos sólidos"
        ),
        "NORM_RESIDUOS",
        "Normativa municipal sobre gestión de residuos sólidos"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa municipal sobre prevención y control de contaminación sonora"
        ),
        "NORM_RUIDO",
        "Normativa municipal sobre prevención y control de contaminación sonora"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa municipal sobre comercio ambulatorio y uso de espacios públicos"
        ),
        "NORM_COMERCIO_AMBULATORIO",
        "Normativa municipal sobre comercio ambulatorio y uso de espacios públicos"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa municipal sobre desarrollo urbano y edificaciones"
        ),
        "NORM_DESARROLLO_URBANO",
        "Normativa municipal sobre desarrollo urbano y edificaciones"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa municipal sobre licencias de funcionamiento"
        ),
        "NORM_LICENCIAS",
        "Normativa municipal sobre licencias de funcionamiento"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa aplicable a inspecciones técnicas de seguridad en edificaciones"
        ),
        "NORM_ITSE",
        "Normativa aplicable a inspecciones técnicas de seguridad en edificaciones"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa municipal sobre gestión de servicios públicos"
        ),
        "NORM_SERVICIOS_PUBLICOS",
        "Normativa municipal sobre gestión de servicios públicos"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Ley del Procedimiento Administrativo General"
        ),
        "LPAG",
        "Ley del Procedimiento Administrativo General",
        tipo="LEY"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa municipal sobre fiscalización y sanciones administrativas"
        ),
        "NORM_FISCALIZACION_SANCIONES",
        "Normativa municipal sobre fiscalización y sanciones administrativas"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa de contratación pública aplicable"
        ),
        "NORM_CONTRATACION_PUBLICA",
        "Normativa de contratación pública aplicable"
    ),

    Normativa(
        demo_id(
            "NORMATIVA:"
            "Normativa de transparencia y acceso a la información pública"
        ),
        "NORM_TRANSPARENCIA",
        "Normativa de transparencia y acceso a la información pública"
    ),
]


# ============================================================
# PLANTILLAS DEMO
# ============================================================

def plantillas_demo() -> list[Plantilla]:
    from src.domain.value_objects.estructura_piloto import estructura_piloto

    resultado = []

    for tipo in TIPOS:

        plantilla = Plantilla(
            demo_id(
                f"plantilla:{tipo.codigo}"
            ),
            f"{tipo.nombre} (DEMO)",
            tipo.id
        )
        if tipo.codigo == "INFORME_TECNICO":
            plantilla.nombre = "Informe Técnico – Piloto NAXJI (DEMO)"
            plantilla.descripcion = "DEMOSTRACIÓN. No constituye un formato oficial municipal. Revisión humana obligatoria."
            plantilla.secciones_salida = estructura_piloto()

        for orden, (
            clave,
            dato,
            obligatorio,
            config
        ) in enumerate(
            (
                (
                    "antecedentes",
                    TipoDato.TEXTAREA,
                    True,
                    {}
                ),
                (
                    "detalle",
                    TipoDato.TEXT,
                    True,
                    {}
                ),
                (
                    "fecha",
                    TipoDato.DATE,
                    False,
                    {}
                ),
                (
                    "cantidad",
                    TipoDato.NUMBER,
                    False,
                    {}
                ),
                (
                    "verificado",
                    TipoDato.BOOLEAN,
                    False,
                    {}
                ),
                (
                    "prioridad",
                    TipoDato.SELECT,
                    False,
                    {
                        "opciones": [
                            "NORMAL",
                            "ALTA"
                        ]
                    }
                ),
            ),
            start=1
        ):

            plantilla.campos.append(
                CampoPlantilla(
                    demo_id(
                        f"{tipo.codigo}:{clave}"
                    ),
                    plantilla.id,
                    clave,
                    clave.capitalize(),
                    dato,
                    obligatorio,
                    orden,
                    config,
                )
            )

        resultado.append(
            plantilla
        )

    # Nueva identidad/version: no se modifican los campos ni IDs de los fixtures anteriores.
    from src.domain.value_objects.fuentes_piloto import campos_fuente_piloto
    piloto = Plantilla(demo_id("plantilla:INFORME_TECNICO:v2"),
                       "Informe Técnico – Piloto NAXJI (DEMO)", TIPOS[0].id, version=2,
                       descripcion="DEMOSTRACIÓN v2 con datos fuente. No constituye un formato oficial municipal. Revisión humana obligatoria.",
                       secciones_salida=estructura_piloto())
    piloto.campos = campos_fuente_piloto(piloto.id)
    resultado.append(piloto)
    return resultado
