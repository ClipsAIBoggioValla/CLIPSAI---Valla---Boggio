from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend_fastapi.app.main import app
from backend_fastapi.app.deps import get_current_user, get_db
from backend_fastapi.app.models import Usuario, Video, Clip, Job


def _mk_env(db_session):
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
    return u, c


@pytest.fixture
def pub_client(db_session):
    u, c = _mk_env(db_session)

    def _get_db():
        yield db_session

    def _get_user():
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    client = TestClient(app, raise_server_exceptions=False)
    yield client, u, c
    app.dependency_overrides.clear()
    client.close()


def test_publish_clip_invalid_platform(pub_client):
    client, u, c = pub_client
    resp = client.post(f"/clips/{c.id}/publicar", json={"platform": "facebook", "caption": "x"})
    assert resp.status_code == 422
    assert "platform debe ser" in resp.json().get("detail", "")


def test_publish_clip_not_found(db_session):
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()

    def _get_db():
        yield db_session

    def _get_user():
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    client = TestClient(app, raise_server_exceptions=False)
    try:
        resp = client.post(f"/clips/{uuid.uuid4()}/publicar", json={"platform": "tiktok", "caption": "x"})
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_publish_clip_valid(pub_client):
    client, u, c = pub_client
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "backend_fastapi.app.services.publish_service.publish_clip_task"
    ) as mp:
        resp = client.post(f"/clips/{c.id}/publicar", json={"platform": "tiktok", "caption": "hola"})
    assert resp.status_code == 202
    body = resp.json()
    assert body.get("status") == "PUBLISHING"
    assert body.get("platform") == "tiktok"
