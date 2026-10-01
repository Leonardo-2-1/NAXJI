"""Contrato Word sin servicios externos ni base de datos."""
from io import BytesIO
from types import SimpleNamespace

from docx import Document
import pytest

from src.adapters.out.documents.exportador_docx import ExportadorDocx
from src.domain.services.errores import DatosInvalidos
from src.domain.value_objects.encabezado_documento import FORMATO_MDT
from src.domain.value_objects.seccion_salida import secciones_desde_json


def version():
    return SimpleNamespace(titulo='Informe de prueba', secciones_salida=secciones_desde_json([
        {'clave':'cuerpo','titulo':'Cuerpo del informe interno','obligatoria':True}]),
        contenido={'cuerpo':'Texto literal {{numero}}.\n\nSegundo párrafo conservado.',
                   'encabezado':{'formato_documento':FORMATO_MDT,'asunto':'Asunto {{firmante}}',
                                 'documento':{'numero':'PRUEBA', 'firmante':'Persona ficticia'}}})


def test_no_interpreta_el_texto_guardado_como_variables_ni_permite_firmas_tecnicas():
    v = version()
    doc = Document(BytesIO(ExportadorDocx().exportar(None, v)))
    textos = '\n'.join(p.text for p in doc.paragraphs)
    assert v.contenido['cuerpo'] in textos
    assert 'Asunto {{firmante}}' in textos
    assert 'INFORME N° PRUEBA' in textos
    assert 'Persona ficticia' in textos
    assert 'De:' not in textos


def test_formato_desconocido_o_estructura_distinta_no_se_disfrazan_de_piloto():
    v = version(); v.contenido['encabezado']['formato_documento'] = 'desconocido'
    with pytest.raises(DatosInvalidos): ExportadorDocx().exportar(None, v)
    v = version(); v.secciones_salida = None
    with pytest.raises(DatosInvalidos): ExportadorDocx().exportar(None, v)
