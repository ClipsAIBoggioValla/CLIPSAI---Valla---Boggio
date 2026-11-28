"""Conexion a PostgreSQL (SQLAlchemy 2.x, modo sincrono)."""

from __future__ import annotations

import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

logger = logging.getLogger(__name__)

# Variable global para indicar si la DB está disponible
DB_AVAILABLE = False

_settings = get_settings()  # cacheado, levanta una vez y usa las vars del ambiente

# Fallback host vs Docker: bidireccional.
def _is_docker() -> bool:
    try:
        from pathlib import Path

        return Path("/.dockerenv").exists()
    except Exception:
        return False


def _esquema_normalizado(url: str) -> str:
    """Normaliza esquemas de nube (postgres://, postgresql://) al dialecto explicito."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def _db_resuelve() -> bool:
    """True si el host 'db' resuelve a nivel DNS."""
    try:
        import socket

        socket.getaddrinfo("db", 5432)
        return True
    except Exception:
        return False


def _url_para_docker(url: str) -> str | None:
    """Dentro de docker: host local reescrito a 'db'; None si no aplica."""
    if _is_docker() and ("@127.0.0.1:" in url or "@localhost:" in url):
        return url.replace("@127.0.0.1:", "@db:").replace("@localhost:", "@db:").replace("@127.0.0.1/", "@db/")
    return None


def _host_local_de_db(url: str) -> bool:
    """True si la URL apunta al host 'db'."""
    return "@db:" in url or "@db/" in url


def _url_para_host(url: str) -> str | None:
    """Fuera de docker: ajusta el host 'db' segun si resuelve; None si no aplica."""
    if _is_docker() or not _host_local_de_db(url):
        return None
    if _db_resuelve():
        return url
    return url.replace("@db:", "@127.0.0.1:").replace("@db/", "@127.0.0.1/")


def _fallback_db_url(url: str) -> str:
    """Normaliza esquema y host de la URL de base de datos segun el entorno."""
    url = _esquema_normalizado(url)
    url = _url_para_docker(url) or url
    url = _url_para_host(url) or url
    return url


# Inicialización perezosa de la base de datos
engine = None
migration_engine = None
SessionLocal = None


def _engine_options(url: str) -> dict:
    options = {"pool_pre_ping": True, "future": True}
    if url.startswith("postgresql+"):
        options.update(
            pool_recycle=240,
            connect_args={
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            },
        )
    return options


def _crear_engine(url: str):
    resolved = _fallback_db_url(url)
    return create_engine(resolved, **_engine_options(resolved))


def _probar_conexion(db_engine) -> None:
    from sqlalchemy import text

    with db_engine.connect() as conn:
        conn.execute(text("SELECT 1"))


runtime_url = _settings.app_database_url.strip() or _settings.database_url
migration_url = _settings.database_url

if runtime_url:
    try:
        engine = _crear_engine(runtime_url)
        migration_engine = _crear_engine(migration_url) if migration_url else engine
        SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )
        _probar_conexion(engine)
        DB_AVAILABLE = True
        logger.info("Database connected successfully (runtime role).")
    except Exception as e:
        logger.warning(f"Database connection failed on startup: {e}. Running in DB-less mode.")
        DB_AVAILABLE = False
else:
    logger.info("No DATABASE_URL provided. Running in DB-less mode (e.g., RunPod worker).")
    DB_AVAILABLE = False


class Base(DeclarativeBase):
    """Base declarativa para los modelos ORM."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: entrega una sesion y garantiza su cierre."""
    if not DB_AVAILABLE or SessionLocal is None:
        raise RuntimeError("Database not available")
    
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
