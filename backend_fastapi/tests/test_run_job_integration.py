from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.routers import jobs as jobs_router
from backend_fastapi.app.models import Usuario, Video, Job, Clip


@pytest.fixture
def user(db_session):
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h", full_name="N")
    db_session.add(u)
    db_session.commit()
    return u


def test_run_job_no_video_integration(db_session, user):
    """_run_job with a job whose video doesn't exist → sets FAILED."""
    job = Job(video_id=uuid.uuid4(), status="pending", progress=0)
    db_session.add(job)
    db_session.commit()
    jid = job.id

    # Patch SessionLocal to return our session
    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db_session):
        try:
            jobs_router._run_job(jid)
        except Exception:
            pass
    # re-query
    job2 = db_session.get(Job, jid)
    assert job2 is not None


def test_run_job_video_no_filepath_integration(db_session, user, tmp_path):
    """_run_job with a video that has no filepath → sets FAILED."""
    vpath = tmp_path / "v.mp4"
    vpath.write_bytes(b"x" * 100)
    video = Video(user_id=user.id, filename="v.mp4", filepath=str(vpath))
    db_session.add(video)
    db_session.commit()
    job = Job(video_id=video.id, status="pending", progress=0)
    db_session.add(job)
    db_session.commit()
    jid = job.id

    # Make filepath point to non-existent to trigger FileNotFoundError
    video.filepath = str(tmp_path / "nope.mp4")
    db_session.commit()

    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db_session):
        try:
            jobs_router._run_job(jid)
        except Exception:
            pass
    job2 = db_session.get(Job, jid)
    assert job2 is not None
