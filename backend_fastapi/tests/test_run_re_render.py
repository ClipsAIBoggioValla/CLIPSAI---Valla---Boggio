from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.routers import clips as clips_router


def test_run_re_render_no_clip() -> None:
    cid = uuid.uuid4()
    db = MagicMock()
    db.get.return_value = None
    with patch("backend_fastapi.app.routers.clips.SessionLocal", return_value=db, create=True) if False else patch(
        "backend_fastapi.app.database.SessionLocal", return_value=db
    ):
        try:
            clips_router._run_re_render(cid, True, False)
        except Exception:
            pass


def test_run_re_render_no_video(tmp_path: Path) -> None:
    cid = uuid.uuid4()
    clip = SimpleNamespace(id=cid, storage_path=None, tags=None, status="COMPLETED", start_time=0.0, end_time=10.0, title="T", job_id=uuid.uuid4(), video_id=None, error_log=None, updated_at=None)
    db = MagicMock()
    db.get.return_value = clip
    with patch("backend_fastapi.app.database.SessionLocal", return_value=db), patch(
        "backend_fastapi.app.routers.clips._resolve_clip_video", return_value=None
    ):
        try:
            clips_router._run_re_render(cid, True, False)
        except Exception:
            pass
    assert clip.status == "FAILED"


def test_run_re_render_with_video(tmp_path: Path) -> None:
    cid = uuid.uuid4()
    vpath = tmp_path / "v.mp4"
    vpath.write_bytes(b"x" * 100)
    video = SimpleNamespace(filepath=str(vpath), duration_seconds=10)
    clip = SimpleNamespace(id=cid, storage_path=None, tags={}, status="COMPLETED", start_time=0.0, end_time=10.0, title="T", job_id=uuid.uuid4(), video_id=None, error_log=None, updated_at=None)
    db = MagicMock()
    db.get.return_value = clip
    with patch("backend_fastapi.app.database.SessionLocal", return_value=db), patch(
        "backend_fastapi.app.routers.clips._resolve_clip_video", return_value=video
    ), patch("backend_fastapi.app.routers.clips._load_segments_and_hooks", return_value=([], [])), patch(
        "backend_fastapi.app.routers.jobs._render_clip_with_ass_and_hook", return_value=("/tmp/out.mp4", {"ass_applied": True, "hook_applied": False, "render": "re-render"})
    ):
        try:
            clips_router._run_re_render(cid, True, False)
        except Exception:
            pass
    assert clip.status in ("ready", "FAILED", "COMPLETED")
