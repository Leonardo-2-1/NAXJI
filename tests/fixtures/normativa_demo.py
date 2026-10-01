"""Documentos FICTICIOS para tests aislados; nunca son semillas de Supabase.

La URL raíz oficial solo satisface la validación de protocolo/dominio del fixture;
no pretende ser una fuente de estos documentos inventados.
"""
from datetime import date
from uuid import uuid4

from src.domain.entities.catalogo import Normativa
from src.domain.entities.correspondencia_normativa import CorrespondenciaNormativa


def correspondencia_demo(numero="A", etiqueta="NORM_RESIDUOS"):
    norma = Normativa(uuid4(), f"DEMO_TEST_{numero}", f"DOCUMENTO FICTICIO TEST {numero}",
                      numero=f"DEMO-{numero}", fecha_publicacion=date(2000, 1, 1), url_fuente="https://www.gob.pe/")
    return CorrespondenciaNormativa(etiqueta, norma, "VERIFICADA", "https://www.gob.pe/",
                                   "https://www.gob.pe/", date(2000, 1, 2), "Ámbito FICTICIO de pruebas",
                                   "VIGENTE", "Asociación simulada exclusivamente en tests")
