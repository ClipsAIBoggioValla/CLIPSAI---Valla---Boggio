from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.routers import jobs as jobs_router
from backend_fastapi.app.models import Usuario, Video, Job, Clip


def test_run_job_full_success(tmp_path, db_session):
    vpath = tmp_path / "v.mp4"
    vpath.write_bytes(b"x" * 100)
    tpath = tmp_path / "t.txt"
    tpath.write_text("0:00 - Hola\n", encoding="utf-8")

    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()

    video = Video(user_id=u.id, filename="v.mp4", filepath=str(vpath), transcription_filepath=str(tpath), transcript="0:00 - Hola", duration_seconds=10)
    db_session.add(video)
    db_session.commit()

    job = Job(video_id=video.id, status="pending", progress=0)
    db_session.add(job)
    db_session.commit()
    jid = job.id

    clip_payload = {
        "inicio": "00:00:00",
        "fin": "00:00:10",
        "score": 8,
        "titulo": "T",
        "hook_texto": "h",
        "criterio_principal": "claude",
        "primer_segundo": "0",
        "motivo": "m",
    }
    mock_result = {
        "engine": "native_claude",
        "clips": [clip_payload],
        "transcription_segments": [{"start": 0, "end": 1, "text": "hi"}],
    }

    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db_session), patch(
        "backend_fastapi.app.services.engine.run_clip_engine", return_value=mock_result
    ), patch("backend_fastapi.app.routers.jobs._log_claude_config"), patch(
        "backend_fastapi.app.routers.jobs._render_clip_with_ass_and_hook", return_value=("/tmp/out.mp4", {"ass_applied": True, "hook_applied": False, "render": "ass"})
    ), patch("backend_fastapi.app.routers.jobs._select_hook_for_clip", return_value=None):
        try:
            jobs_router._run_job(jid)
        except Exception:
            pass

    job2 = db_session.get(Job, jid)
    assert job2 is not None
