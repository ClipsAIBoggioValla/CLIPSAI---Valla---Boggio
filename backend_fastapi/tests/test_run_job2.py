from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.routers import jobs as jobs_router


def test_run_job_with_transcript(tmp_path: Path) -> None:
    cid = uuid.uuid4()
    vpath = tmp_path / "v.mp4"
    vpath.write_bytes(b"x" * 100)
    tpath = tmp_path / "t.txt"
    tpath.write_text("0:00 - Hola\n", encoding="utf-8")
    video = SimpleNamespace(
        id=uuid.uuid4(),
        filepath=str(vpath),
        transcription_filepath=str(tpath),
        transcript="0:00 - Hola",
        duration_seconds=10,
        user_id=uuid.uuid4(),
    )
    job = SimpleNamespace(id=cid, video_id=video.id, status="PENDING", progress=0, error_log=None, clips=[])
    db = MagicMock()

    def get_side(model, pk):
        name = getattr(model, "__name__", str(model))
        if "Job" in name:
            return job
        if "Video" in name:
            return video
        return None

    db.get.side_effect = get_side
    db.execute.return_value = MagicMock(all=lambda: [], scalar_one_or_none=lambda: None)

    # Mock engine.procesar_video (root)
    import engine as root_engine
    mock_result = SimpleNamespace(exito=True, clips=[], carpeta_salida=str(tmp_path), error=None, error_tipo=None, error_detalle=None, transcription_segments=[])
    with patch("backend_fastapi.app.routers.jobs.SessionLocal", return_value=db), patch.object(
        root_engine, "procesar_video", return_value=mock_result
    ), patch("backend_fastapi.app.routers.jobs._validate_job_video_and_transcription", return_value=(str(vpath), str(tpath), True)), patch(
        "backend_fastapi.app.routers.jobs._persist_transcription_diagnosis", return_value=job
    ), patch("backend_fastapi.app.routers.jobs._ensure_clips_payload", side_effect=RuntimeError("no clips")):
        try:
            jobs_router._run_job(cid)
        except Exception:
            pass
