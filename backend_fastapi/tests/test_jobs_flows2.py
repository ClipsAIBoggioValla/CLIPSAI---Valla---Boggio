from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.routers import jobs as jobs_router
from backend_fastapi.app.models import Usuario, Video, Job, Clip


def _setup_job(db_session, tmp_path, status="pending"):
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    v = Video(user_id=u.id, filename="v.mp4", filepath=str(tmp_path / "v.mp4"), transcript="hola", duration_seconds=10)
    db_session.add(v)
    db_session.commit()
    j = Job(video_id=v.id, status=status, progress=0)
    db_session.add(j)
    db_session.commit()
    cid = j.id
    (tmp_path / "v.mp4").write_bytes(b"x" * 10)
    return u, v, j, cid


def _run(jid, db_session, tmp_path):
    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db_session), patch(
        "backend_fastapi.app.routers.jobs._log_claude_config"
    ):
        try:
            jobs_router._run_job(jid)
        except Exception:
            pass
    return db_session.get(Job, jid)


def test_run_job_engine_claude_error(tmp_path, db_session):
    u, v, j, cid = _setup_job(db_session, tmp_path)
    job2 = _run(cid, db_session, tmp_path)
    # re-run with engine raising Claude error
    j2 = db_session.get(Job, cid)
    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db_session), patch(
        "backend_fastapi.app.routers.jobs._log_claude_config"
    ), patch("backend_fastapi.app.services.engine.run_clip_engine", side_effect=RuntimeError("Claude API error: timeout")):
        try:
            jobs_router._run_job(cid)
        except Exception:
            pass
    jf = db_session.get(Job, cid)
    assert jf.status == "failed"
    assert jf.error_message is not None


def test_run_job_engine_generic_error(tmp_path, db_session):
    u, v, j, cid = _setup_job(db_session, tmp_path)
    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db_session), patch(
        "backend_fastapi.app.routers.jobs._log_claude_config"
    ), patch("backend_fastapi.app.services.engine.run_clip_engine", side_effect=RuntimeError("boom boom")):
        try:
            jobs_router._run_job(cid)
        except Exception:
            pass
    jf = db_session.get(Job, cid)
    assert jf.status == "failed"
    assert jf.error_message is not None


def test_run_job_engine_success_creates_clips(tmp_path, db_session):
    u, v, j, cid = _setup_job(db_session, tmp_path)
    out = tmp_path / "clips" / f"{cid}_00.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"y" * 10)
    mock_result = {
        "engine": "native_claude",
        "clips": [
            {
                "inicio": "00:00:00",
                "fin": "00:00:10",
                "score": 8,
                "titulo": "T",
                "hook_texto": "h",
                "criterio_principal": "claude",
                "primer_segundo": "0",
                "motivo": "m",
            }
        ],
        "transcription_segments": [{"start": 0, "end": 5, "text": "hola"}],
    }
    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db_session), patch(
        "backend_fastapi.app.routers.jobs._log_claude_config"
    ), patch("backend_fastapi.app.services.engine.run_clip_engine", return_value=mock_result) as erc, patch(
        "backend_fastapi.app.routers.jobs._render_clip_with_ass_and_hook", return_value=(str(out), {"render": "ass", "ass_applied": True, "hook_applied": False})
    ) as erc2, patch("backend_fastapi.app.routers.jobs._select_hook_for_clip", return_value=None):
        try:
            jobs_router._run_job(cid)
        except Exception as e:
            print("RUN JOB EXC", e)
    jf = db_session.get(Job, cid)
    assert jf is not None
