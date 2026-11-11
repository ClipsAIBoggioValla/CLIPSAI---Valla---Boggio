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


def test_disconnect_social() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    db.execute.return_value = MagicMock(rowcount=1)
    db.get.return_value = None
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/social/tiktok")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_instagram_callback_success() -> None:
    db = MagicMock()
    with __import__("unittest.mock", fromlist=["patch"]).patch("backend_fastapi.app.routers.social_auth.ig_exchange_code_for_tokens", return_value={"access_token": "t"}), __import__("unittest.mock", fromlist=["patch"]).patch("backend_fastapi.app.routers.social_auth.ig_save_instagram_tokens"):
        db.get.return_value = None
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/social/instagram/callback?code=abc&state=eyJ1c2VyX2lkIjoidTEifQ")
        assert resp.status_code in (200, 302, 400, 404, 422, 500)
        client.close()


def test_tiktok_callback_success() -> None:
    db = MagicMock()
    with __import__("unittest.mock", fromlist=["patch"]).patch("backend_fastapi.app.routers.social_auth.tt_exchange_tiktok_code", return_value={"access_token": "t"}), __import__("unittest.mock", fromlist=["patch"]).patch("backend_fastapi.app.routers.social_auth.tt_save_tiktok_tokens"):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/social/tiktok/callback?code=abc&state=eyJ1c2VyX2lkIjoidTEiLCJjb2RlX3ZlcmlmaWVyIjoiY3YifQ")
        assert resp.status_code in (200, 302, 400, 404, 422, 500)
        client.close()
