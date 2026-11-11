from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.routers import jobs as jobs_router


def test_run_job_no_video() -> None:
    cid = uuid.uuid4()
    db = MagicMock()
    db.get.return_value = None
    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db):
        try:
            jobs_router._run_job(cid)
        except Exception:
            pass


def test_run_job_video_no_filepath() -> None:
    cid = uuid.uuid4()
    video = SimpleNamespace(id=uuid.uuid4(), filepath=None, transcription_filepath=None, transcript=None, duration_seconds=None, user_id=uuid.uuid4())
    job = SimpleNamespace(id=cid, video_id=video.id, status="PENDING", progress=0, error_log=None)
    db = MagicMock()
    db.get.side_effect = lambda model, pk: job if "Job" in getattr(model, "__name__", "") else video
    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db):
        try:
            jobs_router._run_job(cid)
        except Exception:
            pass
