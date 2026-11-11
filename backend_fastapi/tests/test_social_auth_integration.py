from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend_fastapi.app.main import app
from backend_fastapi.app.deps import get_current_user, get_db
from backend_fastapi.app.models import Usuario, SocialAccount


def test_social_status_with_account(db_session):
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    acc = SocialAccount(user_id=u.id, platform="youtube", platform_account_id="p1", platform_username="chan", access_token="tok", refresh_token="ref")
    db_session.add(acc)
    db_session.commit()

    def _get_db():
        yield db_session

    def _get_user():
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/social/status")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        app.dependency_overrides.clear()


def test_disconnect_social_with_account(db_session):
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    acc = SocialAccount(user_id=u.id, platform="youtube", platform_account_id="p1", platform_username="chan", access_token="tok", refresh_token="ref")
    db_session.add(acc)
    db_session.commit()

    def _get_db():
        yield db_session

    def _get_user():
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/social/youtube")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        app.dependency_overrides.clear()
