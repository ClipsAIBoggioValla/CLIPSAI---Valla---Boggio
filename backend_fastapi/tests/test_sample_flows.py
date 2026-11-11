from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from backend_fastapi.app.routers import sample as sample_router
from backend_fastapi.app.routers.sample import _get_sample_video_path, create_sample_job
from backend_fastapi.app.deps import get_current_user, get_db
from backend_fastapi.app.main import app
from backend_fastapi.app.models import Usuario, Video, Job, Clip


def test_get_sample_video_path_env(tmp_path):
    p = tmp_path / "sample.mp4"
    p.write_bytes(b"x" * 10)
    with patch.dict("os.environ", {"SAMPLE_VIDEO_PATH": str(p)}):
        assert _get_sample_video_path() == p


def test_get_sample_video_path_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMPLE_VIDEO_PATH", "")
    res = _get_sample_video_path()
    assert res is not None


def test_create_sample_job_missing(db_session, monkeypatch):
    monkeypatch.setenv("SAMPLE_VIDEO_PATH", "/tmp/definitely_missing_sample.mp4")
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
        resp = client.post("/videos/sample")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_create_sample_job_ok(db_session, monkeypatch, tmp_path):
    p = tmp_path / "sample.mp4"
    p.write_bytes(b"x" * 10)
    monkeypatch.setenv("SAMPLE_VIDEO_PATH", str(p))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

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
        with patch("backend_fastapi.app.routers.jobs.run_job_safely"):
            resp = client.post("/videos/sample")
        assert resp.status_code == 202
    finally:
        app.dependency_overrides.clear()
        client.close()
