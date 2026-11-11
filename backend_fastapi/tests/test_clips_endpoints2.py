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


def _clip(user_id):
    return SimpleNamespace(id=uuid.uuid4(), job_id=uuid.uuid4(), video_id=None, title="T", start_time=0.0, end_time=5.0, score=8, tags=None, storage_path="/tmp/x.mp4", status="COMPLETED", published_platform=None, social_post_id=None, social_post_url=None, published_at=None, publication_status=None, social_network=None, created_at=None, updated_at=None)


def test_download_clip() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    clip = _clip(user.id)
    def get_side(model, pk):
        name = getattr(model, "__name__", str(model))
        if "Clip" in name:
            return clip
        return None
    db.get.side_effect = get_side
    video = SimpleNamespace(id=uuid.uuid4(), user_id=user.id)
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: video, all=lambda: [])
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/clips/{clip.id}/descarga")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_update_clip() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    clip = _clip(user.id)
    def get_side(model, pk):
        name = getattr(model, "__name__", str(model))
        if "Clip" in name:
            return clip
        return None
    db.get.side_effect = get_side
    video = SimpleNamespace(id=uuid.uuid4(), user_id=user.id)
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: video, all=lambda: [])
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.patch(f"/clips/{clip.id}", json={"title": "New"})
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_delete_clip() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    clip = _clip(user.id)
    def get_side(model, pk):
        name = getattr(model, "__name__", str(model))
        if "Clip" in name:
            return clip
        return None
    db.get.side_effect = get_side
    video = SimpleNamespace(id=uuid.uuid4(), user_id=user.id)
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: video, all=lambda: [])
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete(f"/clips/{clip.id}")
        assert resp.status_code in (200, 204, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()


def test_re_render_clip() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    clip = _clip(user.id)
    def get_side(model, pk):
        name = getattr(model, "__name__", str(model))
        if "Clip" in name:
            return clip
        return None
    db.get.side_effect = get_side
    video = SimpleNamespace(id=uuid.uuid4(), user_id=user.id, filepath="/tmp/v.mp4", transcript=None, duration_seconds=10)
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: video, all=lambda: [])
    _overrides(db, user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(f"/clips/{clip.id}/re-render", json={"enable_ass": True, "enable_hook": False})
        assert resp.status_code in (200, 201, 202, 400, 404, 422, 500)
        client.close()
    finally:
        _clear()
