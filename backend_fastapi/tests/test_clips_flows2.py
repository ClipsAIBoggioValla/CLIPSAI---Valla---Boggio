from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend_fastapi.app.main import app
from backend_fastapi.app.deps import get_current_user, get_db
from backend_fastapi.app.models import Usuario, Video, Job, Clip
from backend_fastapi.app.routers import clips as clips_router


@pytest.fixture
def clip_client(db_session):
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    v = Video(user_id=u.id, filename="v.mp4", filepath="/tmp/v.mp4")
    db_session.add(v)
    db_session.commit()
    j = Job(video_id=v.id, status="completed", progress=100)
    db_session.add(j)
    db_session.commit()
    c = Clip(job_id=j.id, video_id=v.id, start_time=0.0, end_time=5.0, status="ready", storage_path="/tmp/c.mp4", tags={})
    db_session.add(c)
    db_session.commit()
    cid = c.id

    def _get_db():
        yield db_session

    def _get_user():
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    client = TestClient(app, raise_server_exceptions=False)
    yield client, u, c, cid
    app.dependency_overrides.clear()
    client.close()


def test_clip_helpers_basic():
    assert clips_router._clip_has_ass({}) is False
    assert clips_router._clip_has_ass({"has_ass": True}) is True
    assert clips_router._clip_has_hook({}) is False
    assert clips_router._clip_has_hook({"has_hook": True}) is True
    assert clips_router._clip_duration(0.0, 5.0) == 5.0
    assert clips_router._clip_duration(0.0, "bad") is None
    assert clips_router._clip_stream_url(uuid.uuid4()) is not None


def test_get_clip(clip_client):
    client, u, c, cid = clip_client
    resp = client.get(f"/clips/{cid}")
    assert resp.status_code == 200
    assert str(cid) in str(resp.json().get("id"))


def test_update_clip(clip_client):
    client, u, c, cid = clip_client
    resp = client.patch(f"/clips/{cid}", json={"title": "NuevoTitulo"})
    assert resp.status_code == 200
    assert resp.json().get("title") == "NuevoTitulo"


def test_delete_clip(clip_client):
    client, u, c, cid = clip_client
    resp = client.delete(f"/clips/{cid}")
    assert resp.status_code == 204


def test_re_render_clip(clip_client):
    client, u, c, cid = clip_client
    with patch("backend_fastapi.app.routers.clips._run_re_render") as rr:
        resp = client.post(f"/clips/{cid}/re-render", json={"enable_ass": True, "enable_hook": True})
    assert resp.status_code == 202
    assert resp.json().get("status") == "PROCESSING"


def test_re_render_clip_conflict(clip_client, db_session):
    client, u, c, cid = clip_client
    cc = db_session.get(Clip, cid)
    cc.status = "PROCESSING"
    db_session.commit()
    with patch("backend_fastapi.app.routers.clips._run_re_render"):
        resp = client.post(f"/clips/{cid}/re-render", json={"enable_ass": False, "enable_hook": False})
    assert resp.status_code == 409
