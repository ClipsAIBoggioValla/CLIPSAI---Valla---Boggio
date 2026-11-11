from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.tasks import subtitle_pipeline as sp
from backend_fastapi.app.tasks.subtitle_pipeline import (
    _clip_segments_to_range,
    _get_clip_or_none,
    _resolve_video_path,
    _update_clip_status,
    run_subtitle_pipeline,
)


def test_run_subtitle_pipeline_invalid_id():
    with pytest.raises(ValueError):
        run_subtitle_pipeline("no-un-uuid")


def test_run_subtitle_pipeline_clip_not_found(db_session):
    with patch("backend_fastapi.app.tasks.subtitle_pipeline.SessionLocal", return_value=db_session):
        run_subtitle_pipeline(str(uuid.uuid4()))


def test_clip_segments_to_range_filters(db_session=None):
    clip = SimpleNamespace(start_time=0.0, end_time=10.0)
    segs = [{"start": 0, "end": 5, "text": "hola"}, {"start": 20, "end": 25, "text": "chau"}]
    out = _clip_segments_to_range(segs, clip)
    assert len(out) == 1
    assert out[0]["text"] == "hola"


def test_update_clip_status_error_log(db_session=None):
    clip = SimpleNamespace(status="ready", tags={}, error_log=None)
    _update_clip_status(None, clip, "FAILED", error_log="boom")
    assert clip.status == "FAILED"
    assert clip.error_log == "boom"


def test_update_clip_status_no_error_log_attr(db_session=None):
    clip = SimpleNamespace(status="ready", tags={})
    _update_clip_status(None, clip, "FAILED", error_log="boom")
    assert clip.status == "FAILED"
    assert clip.tags.get("_subtitle_error") == "boom"


def test_resolve_video_path_none(db_session=None):
    clip = SimpleNamespace(storage_path=None, file_path=None, video_id=None, job_id=None)
    assert _resolve_video_path(clip, None) is None


def test_run_subtitle_pipeline_success(db_session, tmp_path):
    u_id = uuid.uuid4()
    v = None
    from backend_fastapi.app.models import Usuario, Video, Job, Clip
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    v = Video(user_id=u.id, filename="v.mp4", filepath=str(tmp_path / "v.mp4"))
    db_session.add(v)
    db_session.commit()
    j = Job(video_id=v.id, status="completed", progress=100)
    db_session.add(j)
    db_session.commit()
    c = Clip(job_id=j.id, video_id=v.id, start_time=0.0, end_time=5.0, status="ready", storage_path="/tmp/c.mp4", tags={})
    db_session.add(c)
    db_session.commit()
    cid = c.id

    (tmp_path / "v.mp4").write_bytes(b"x" * 10)

    segments = [{"start": 0, "end": 5, "text": "hola mundo"}]
    with patch("backend_fastapi.app.tasks.subtitle_pipeline.SessionLocal", return_value=db_session), patch(
        "backend_fastapi.app.services.runpod_service.is_runpod_configured", return_value=False
    ), patch("backend_fastapi.app.services.whisper_service.extract_audio_wav"), patch(
        "backend_fastapi.app.services.whisper_service.transcribe_wav", return_value=segments
    ), patch("backend_fastapi.app.services.ass_generator.write_ass_file"), patch(
        "backend_fastapi.app.services.ffmpeg_service.burn_subtitles"
    ):
        run_subtitle_pipeline(str(cid))

    refreshed = db_session.get(Clip, cid)
    assert refreshed is not None
