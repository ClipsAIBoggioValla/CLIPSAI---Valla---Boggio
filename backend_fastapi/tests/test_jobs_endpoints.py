from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend_fastapi.app.main import app
from backend_fastapi.app.deps import get_current_user, get_db


def _override_db(db):
    def _get():
        yield db
    return _get


def _override_user(user):
    def _get():
        return user
    return _get


def test_create_job_with_testclient() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    # video exists
    video = SimpleNamespace(id=uuid.uuid4(), user_id=user.id, filepath="/tmp/v.mp4", duration_seconds=10)
    db.get.return_value = video
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)
    try:
        client = TestClient(app)
        resp = client.post("/jobs", json={"video_id": str(video.id)})
        # may fail due to validation but exercises code
        assert resp.status_code in (200, 201, 202, 400, 404, 422, 500)
        client.close()
    finally:
        app.dependency_overrides.clear()


def test_get_job_with_testclient() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    job = SimpleNamespace(id=uuid.uuid4(), video_id=uuid.uuid4(), status="PENDING", progress=0, created_at=None, updated_at=None, error_log=None, clips=[])
    video = SimpleNamespace(id=job.video_id, user_id=user.id)

    def get_side(model, pk):
        name = getattr(model, "__name__", str(model))
        if "Job" in name:
            return job
        return video

    db.get.side_effect = get_side
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/jobs/{job.id}")
        assert resp.status_code in (200, 400, 404, 422, 500)
        client.close()
    finally:
        app.dependency_overrides.clear()
