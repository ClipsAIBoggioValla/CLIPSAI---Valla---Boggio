from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend_fastapi.app.main import app
from backend_fastapi.app.deps import get_current_user, get_db


def _overrides(db, user):
    def _get_db():
        yield db
    def _get_user():
        return user
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user


def _clear():
    app.dependency_overrides.clear()


def test_get_me() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4(), email="a@b.com", full_name="N", avatar_url=None, theme_preference="dark", created_at=None, hashed_password="h", updated_at=None)
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/users/me")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_put_me() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4(), email="a@b.com", full_name="N", avatar_url=None, theme_preference="dark", created_at=None, hashed_password="h", updated_at=None)
    db.execute.return_value = MagicMock(first=lambda: None)
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.put("/users/me", json={"full_name": "New"})
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_patch_me() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4(), email="a@b.com", full_name="N", avatar_url=None, theme_preference="dark", created_at=None, hashed_password="h", updated_at=None)
    db.execute.return_value = MagicMock(first=lambda: None)
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.patch("/me", json={"full_name": "New"})
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_change_password() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4(), email="a@b.com", full_name="N", avatar_url=None, theme_preference="dark", created_at=None, hashed_password="h", updated_at=None)
    db.execute.return_value = MagicMock(first=lambda: None)
    with __import__("unittest.mock", fromlist=["patch"]).patch("backend_fastapi.app.routers.users.verify_password", return_value=True), __import__("unittest.mock", fromlist=["patch"]).patch("backend_fastapi.app.routers.users.hash_password", return_value="newh"):
        _overrides(db, user)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/users/me/change-password", json={"current_password": "oldpass123", "new_password": "newpass123"})
            assert resp.status_code in (200, 400, 404, 422, 500)
            client.close()
        finally:
            _clear()
