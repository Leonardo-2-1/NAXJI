"""Configuración PostgreSQL privada, compartida por el backend y el diagnóstico."""
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path

from dotenv import dotenv_values
import psycopg


ROOT = Path(__file__).resolve().parents[3]


def environment():
    # No interpolar contraseñas que contengan ${...}; el entorno tiene prioridad.
    logger = logging.getLogger("dotenv.main")
    previous = logger.disabled
    logger.disabled = True
    try:
        values = dotenv_values(ROOT / ".env", encoding="utf-8-sig", interpolate=False)
        # Configuración adicional local sin sobrescribir el archivo .env original.
        values.update(dotenv_values(ROOT / ".env.local", encoding="utf-8-sig", interpolate=False))
    finally:
        logger.disabled = previous
    return {**values, **os.environ}


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str = field(repr=False)
    sslmode: str = "require"
    connect_timeout: int = 10

    @classmethod
    def from_env(cls):
        values = environment()
        keys = ("HOST", "PORT", "NAME", "USER", "PASSWORD", "SSLMODE")
        missing = ["NAXJI_DB_" + k for k in keys if not values.get("NAXJI_DB_" + k)]
        if missing:
            raise ValueError("Faltan variables: " + ", ".join(missing))
        password = values["NAXJI_DB_PASSWORD"]
        if password.startswith(("postgres://", "postgresql://")) or password.strip().lower() in {
            "[your-password]", "<contraseña_local>", "<password>", "your-password",
        }:
            raise ValueError("NAXJI_DB_PASSWORD debe contener la contraseña local, no una URI ni un marcador")
        try:
            port = int(values["NAXJI_DB_PORT"])
            timeout = int(values.get("NAXJI_DB_CONNECT_TIMEOUT") or "10")
            if not 1 <= port <= 65535 or not 1 <= timeout <= 60:
                raise ValueError
        except ValueError:
            raise ValueError("Puerto o tiempo de conexión inválido") from None
        sslmode = values["NAXJI_DB_SSLMODE"]
        if sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("NAXJI_DB_SSLMODE debe exigir SSL: require, verify-ca o verify-full")
        return cls(values["NAXJI_DB_HOST"], port, values["NAXJI_DB_NAME"],
                   values["NAXJI_DB_USER"], password, sslmode, timeout)

    def connect(self, **kwargs):
        return psycopg.connect(
            host=self.host, port=self.port, dbname=self.dbname, user=self.user,
            password=self.password, sslmode=self.sslmode, connect_timeout=self.connect_timeout,
            application_name="naxji", options="-c statement_timeout=15000 -c lock_timeout=5000",
            **kwargs,
        )


def database_error(error):
    """No retorna mensajes del servidor, valores SQL ni credenciales."""
    state = error.sqlstate
    if state == "28P01":
        return "Autenticación PostgreSQL rechazada"
    if state == "42501":
        return "Permiso PostgreSQL insuficiente"
    if state == "23503":
        return "Falta un registro relacionado requerido por la base de datos"
    if isinstance(error, psycopg.OperationalError):
        return "No se pudo conectar u operar con PostgreSQL; revise red, SSL y configuración local"
    return "Error PostgreSQL (SQLSTATE: " + (state or "no disponible") + ")"
