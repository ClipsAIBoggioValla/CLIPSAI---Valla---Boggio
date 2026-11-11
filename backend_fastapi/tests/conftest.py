"""Shared pytest fixtures for backend_fastapi tests (SQLite in-memory)."""

from __future__ import annotations

import os
import uuid

# Ensure DB-less mode doesn't block imports
os.environ.setdefault("DATABASE_URL", "")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


from backend_fastapi.app.database import Base
from backend_fastapi.app.models import Usuario, Video, Job, Clip, SocialAccount


@pytest.fixture(scope="session")
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Strip PostgreSQL-specific server_defaults for SQLite (gen_random_uuid, etc.)
    for table in Base.metadata.tables.values():
        for column in table.columns:
            sd = column.server_default
            if sd is not None:
                arg = getattr(sd, "arg", None)
                if isinstance(arg, str) and ("gen_random_uuid" in arg or "::" in arg):
                    column.server_default = None
                elif hasattr(arg, "text") and ("gen_random_uuid" in str(arg.text) or "::" in str(arg.text)):
                    column.server_default = None

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine):
    Session = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # clean tables
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()
