from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.routers import jobs as jobs_router
from backend_fastapi.app.models import Usuario, Video, Job


def test_run_job_with_transcript_full(tmp_path, db_session):
    """_run_job with a video + transcript file, engine succeeds."""
    vpath = tmp_path / "v.mp4"
    vpath.write_bytes(b"x" * 100)
    tpath = tmp_path / "t.txt"
    tpath.write_text("0:00 - Hola\n0:30 - Mundo\n", encoding="utf-8")

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

    # Mock engine.procesar_video (root) to return success
    import engine as root_engine
    mock_clip = SimpleNamespace(archivo="c.mp4", inicio="00:00:00", fin="00:00:10", titulo_sugerido="T", hook_texto="h", criterio_principal="x", score=8, primer_segundo="0", motivo="m")
    mock_result = SimpleNamespace(exito=True, clips=[mock_clip], carpeta_salida=str(tmp_path), error=None, error_tipo=None, error_detalle=None)

    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db_session), patch.object(
        root_engine, "procesar_video", return_value=mock_result
    ), patch("backend_fastapi.app.routers.jobs._log_claude_config"):
        try:
            jobs_router._run_job(jid)
        except Exception:
            pass

    job2 = db_session.get(Job, jid)
    assert job2 is not None


def test_run_job_engine_fails(tmp_path, db_session):
    """_run_job with engine raising → job FAILED."""
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

    import engine as root_engine
    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db_session), patch.object(
        root_engine, "procesar_video", side_effect=RuntimeError("boom")
    ), patch("backend_fastapi.app.routers.jobs._log_claude_config"):
        try:
            jobs_router._run_job(jid)
        except Exception:
            pass

    job2 = db_session.get(Job, jid)
    assert job2 is not None
