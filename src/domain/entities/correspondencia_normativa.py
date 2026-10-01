"""Curación documental y temática; no certifica aplicabilidad al expediente."""
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from src.domain.entities.catalogo import Normativa


def fuente_oficial(url):
    try:
        parts = urlsplit(url or "")
        host = parts.hostname or ""
        return (parts.scheme == "https" and not parts.username and not parts.password
                and (host.endswith(".gob.pe") or host == "gob.pe"
                     or host == "elperuano.pe" or host.endswith(".elperuano.pe")))
    except ValueError:
        return False


@dataclass(frozen=True)
class CorrespondenciaNormativa:
    etiqueta: str
    normativa: Normativa
    estado_verificacion: str = "PENDIENTE"
    fuente_url: str | None = None
    fuente_vigencia_url: str | None = None
    verificado_en: date | None = None
    ambito: str | None = None
    vigencia: str = "PENDIENTE"
    justificacion: str | None = None
    activa: bool = True

    def elegible(self, hoy=None):
        hoy = hoy or date.today()
        n = self.normativa
        return bool(self.activa and n.activo and self.estado_verificacion == "VERIFICADA"
                    and self.vigencia in {"VIGENTE", "VIGENTE_CON_MODIFICACIONES"}
                    and self.verificado_en and self.verificado_en <= hoy
                    and self.ambito and self.ambito.strip() and self.justificacion and self.justificacion.strip()
                    and n.numero and n.fecha_publicacion and n.fecha_publicacion <= hoy
                    and fuente_oficial(n.url_fuente) and fuente_oficial(self.fuente_url)
                    and fuente_oficial(self.fuente_vigencia_url)
                    and (n.fecha_inicio_vigencia is None or n.fecha_inicio_vigencia <= hoy)
                    and (n.fecha_fin_vigencia is None or n.fecha_fin_vigencia >= hoy))

    def evidencia(self):
        return {"etiqueta": self.etiqueta, "estado_verificacion": self.estado_verificacion,
                "documento_codigo": self.normativa.codigo, "documento_titulo": self.normativa.titulo,
                "documento_numero": self.normativa.numero, "documento_url": self.normativa.url_fuente,
                "documento_publicacion": self.normativa.fecha_publicacion.isoformat(),
                "fuente_url": self.fuente_url, "fuente_vigencia_url": self.fuente_vigencia_url,
                "verificado_en": self.verificado_en.isoformat(), "ambito": self.ambito,
                "vigencia": self.vigencia, "justificacion": self.justificacion}
