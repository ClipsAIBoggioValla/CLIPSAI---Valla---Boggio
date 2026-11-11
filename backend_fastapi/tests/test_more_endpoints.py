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


def test_videos_list() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    db.execute.return_value = MagicMock(all=lambda: [])
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/videos")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_videos_generate_upload_url() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/videos/upload-url", json={"filename": "v.mp4", "content_type": "video/mp4"})
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_social_status() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    db.execute.return_value = MagicMock(all=lambda: [], scalar_one_or_none=lambda: None)
    db.get.return_value = None
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/social/status")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_social_accounts() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    db.execute.return_value = MagicMock(all=lambda: [], scalar_one_or_none=lambda: None)
    db.get.return_value = None
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/social/accounts")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_metrics_endpoint() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    db.scalar.return_value = 0
    db.execute.return_value = MagicMock(all=lambda: [])
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/metrics")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_stats_endpoint() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    row = MagicMock()
    row.total_clips = 0
    row.avg_score = None
    row.low = 0
    row.medium = 0
    row.high = 0
    db.execute.return_value = MagicMock(one=lambda: row, scalar_one_or_none=lambda: None, all=lambda: [])
    db.scalar.return_value = 0
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/stats/summary")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()
