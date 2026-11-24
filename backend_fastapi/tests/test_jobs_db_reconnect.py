"""Regression test for a dropped PostgreSQL connection during RunPod polling."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from _fixtures import FakeSession, make_job, make_usuario, make_video
from backend_fastapi.app.routers import jobs as jobs_router


class _ProgressDisconnectSession(FakeSession):
    def __init__(self) -> None:
        super().__init__()
        self.progress_disconnects = 0
        self.rollback_calls = 0

    def commit(self) -> None:
        job = next((obj for (name, _), obj in self.store.items() if name == "Job"), None)
        if job is not None and job.progress == 50 and not self.progress_disconnects:
            self.progress_disconnects += 1
            raise OperationalError(
                "UPDATE jobs SET progress=%(progress)s WHERE jobs.id=%(jobs_id)s::UUID",
                {"progress": 50},
                Exception("SSL connection has been closed unexpectedly"),
            )
        super().commit()

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_run_job_persists_r2_clips_after_progress_ssl_disconnect(tmp_path: Path) -> None:
    user = make_usuario()
    video = make_video(user.id)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    video.filepath = str(source)
    video.transcription_filepath = None
    job = make_job(video.id, status="pending", progress=0)
    db = _ProgressDisconnectSession()
    db.seed(job, video)
    result = {
        "engine": "real",
        "clips": [{"title": "Clip R2", "inicio": 1, "fin": 8, "score": 9, "url_r2": "https://r2.example/clip.mp4"}],
    }

    def _runpod_poll(*args: Any, progress_callback: Any, **kwargs: Any) -> dict[str, Any]:
        progress_callback(pct=50)
        return result

    with (
        patch.object(jobs_router, "SessionLocal", lambda: db),
        patch("backend_fastapi.app.services.engine.run_clip_engine", side_effect=_runpod_poll),
        patch.object(jobs_router, "_limpiar_storage_post_job"),
    ):
        jobs_router._run_job(job.id)

    assert db.progress_disconnects == 1
    assert db.rollback_calls >= 1
    assert job.status == "completed"
    assert len(db.added) == 1
    assert db.added[0].video_id == video.id
    assert db.added[0].storage_path == "https://r2.example/clip.mp4"
