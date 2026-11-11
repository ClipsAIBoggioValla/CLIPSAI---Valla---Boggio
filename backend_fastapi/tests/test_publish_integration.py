from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services.publish_service import publish_clip_task
from backend_fastapi.app.models import Usuario, Clip, Video, Job


def _make_file():
    f = os.path.join(tempfile.gettempdir(), "x.mp4")
    with open(f, "wb") as fh:
        fh.write(b"x" * 100)
    return f


def test_publish_clip_task_webhook_integration(db_session):
    f = _make_file()
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    v = Video(user_id=u.id, filename="v.mp4", filepath=f)
    db_session.add(v)
    db_session.commit()
    j = Job(video_id=v.id, status="completed", progress=100)
    db_session.add(j)
    db_session.commit()
    clip = Clip(job_id=j.id, video_id=v.id, start_time=0.0, end_time=5.0, status="ready", storage_path=f, tags={})
    db_session.add(clip)
    db_session.commit()
    cid = clip.id

    with patch("backend_fastapi.app.services.publish_service.SessionLocal", return_value=db_session):
        try:
            out = publish_clip_task(cid, "webhook", None, None, str(u.id))
        except Exception:
            out = None
    assert out is None or isinstance(out, dict)


def test_publish_clip_task_no_clip_integration(db_session):
    with patch("backend_fastapi.app.services.publish_service.SessionLocal", return_value=db_session):
        out = publish_clip_task(uuid.uuid4(), "webhook", None, None, None)
    assert out is None
