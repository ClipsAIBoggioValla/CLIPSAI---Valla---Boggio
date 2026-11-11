"""Harness compartido para los tests del backend FastAPI sin PostgreSQL real.

Convenciones:
- `DATABASE_URL` se fuerza vacío ANTES de cualquier import de `app.*`, así
  `database.py` entra en modo DB-less y no intenta una conexión TCP real al importar.
- `TestClient(app)` SIN context manager: el lifespan (migraciones + cleanup) no corre.
- Los fakes viven en `_fixtures.py` para que fixtures y tests compartan las clases.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (_TESTS_DIR,):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import _fixtures  # noqa: E402  (módulo plano del mismo directorio)

build_client = _fixtures.build_client
FakeResult = _fixtures.FakeResult
FakeSession = _fixtures.FakeSession
make_clip = _fixtures.make_clip
make_job = _fixtures.make_job
make_social_account = _fixtures.make_social_account
make_usuario = _fixtures.make_usuario
make_video = _fixtures.make_video

from backend_fastapi.app.deps import get_current_user, get_db  # noqa: E402
from backend_fastapi.app.main import app as fastapi_app  # noqa: E402
from backend_fastapi.app.security import create_access_token  # noqa: E402

__all__ = [
    "FakeResult",
    "FakeSession",
    "build_client",
    "make_clip",
    "make_job",
    "make_social_account",
    "make_usuario",
    "make_video",
]


@pytest.fixture()
def db() -> FakeSession:
    return FakeSession()


@pytest.fixture()
def user() -> Any:
    user = make_usuario()
    return user


@pytest.fixture()
def client(db: FakeSession, user: Any) -> TestClient:
    test_client = build_client(db, user)
    try:
        yield test_client
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def auth_header(user: Any) -> dict[str, str]:
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}
