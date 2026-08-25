"""Conexion a PostgreSQL (SQLAlchemy 2.x, modo sincrono)."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

_settings = get_settings()  # cacheado, levanta una vez y usa las vars del ambiente

# `pool_pre_ping=True` evita conexiones muertas tras reinicios de Postgres.
# `future=True` para API de SQLAlchemy 2.0.
engine = create_engine(
    _settings.database_url,
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