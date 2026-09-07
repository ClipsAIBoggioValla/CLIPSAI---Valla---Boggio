"""Conexion a PostgreSQL (SQLAlchemy 2.x, modo sincrono)."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

_settings = get_settings()  # cacheado, levanta una vez y usa las vars del ambiente

# Fallback host vs Docker: bidireccional.
def _is_docker() -> bool:
    try:
        from pathlib import Path

        return Path("/.dockerenv").exists()
    except Exception:
        return False


def _fallback_db_url(url: str) -> str:
    is_docker = _is_docker()
    has_db = "@db:" in url or "@db/" in url
    has_local = "@127.0.0.1:" in url or "@localhost:" in url
    if is_docker and has_local:
        return url.replace("@127.0.0.1:", "@db:").replace("@localhost:", "@db:").replace("@127.0.0.1/", "@db/")
    if not is_docker and has_db:
        try:
            import socket

            socket.getaddrinfo("db", 5432)
            return url
        except socket.gaierror:
            return url.replace("@db:", "@127.0.0.1:").replace("@db/", "@127.0.0.1/")
        except Exception:
            return url.replace("@db:", "@127.0.0.1:").replace("@db/", "@127.0.0.1/")
    return url


_resolved_url = _fallback_db_url(_settings.database_url)

# `pool_pre_ping=True` evita conexiones muertas tras reinicios de Postgres.
# `future=True` para API de SQLAlchemy 2.0.
engine = create_engine(
    _resolved_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Base declarativa para los modelos ORM."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: entrega una sesion y garantiza su cierre."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()