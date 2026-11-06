from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import backend_fastapi.app.tasks.subtitle_pipeline as sp
from backend_fastapi.app.tasks.subtitle_pipeline import (
    _clip_segments_to_range,
    _update_clip_status,
    _resolve_video_path,
    run_subtitle_pipeline,
)


def _clip(start: float = 0.0, end: float = 10.0, tags=None, storage_path=None, video_id=None, job_id=None, status="COMPLETED") -> SimpleNamespace:
    return SimpleNamespace(
        start_time=start,
        end_time=end,
        tags=tags,
        storage_path=storage_path,
        file_path=None,
        video_id=video_id,
        job_id=job_id,
        status=status,
        id=uuid.uuid4(),
        title=None,
        error_log=None,
    )


def test_clip_segments_to_range_filters() -> None:
    segs = [
        {"start": 0.0, "end": 2.0, "text": "Hola"},
        {"start": 5.0, "end": 7.0, "text": "Mundo"},
        {"start": 20.0, "end": 25.0, "text": "Lejos"},
    ]
    out = _clip_segments_to_range(segs, _clip(start=0.0, end=10.0))
    assert len(out) == 2
    assert out[0]["text"] == "Hola"
    assert out[1]["text"] == "Mundo"


def test_clip_segments_to_range_empty_fallback() -> None:
    out = _clip_segments_to_range([], _clip(start=0.0, end=10.0))
    assert out == []


def test_update_clip_status_sets_fields() -> None:
    clip = SimpleNamespace(status="COMPLETED", tags=None, storage_path="/tmp/old.mp4")
    _update_clip_status(MagicMock(), clip, "PROCESSING", error_log="err")
    assert clip.status == "PROCESSING"
    assert clip.tags["error_log"] == "err"
    assert clip.tags["_subtitle_error"] == "err"
    _update_clip_status(MagicMock(), clip, "COMPLETED")
    assert clip.status == "COMPLETED"
    assert clip.tags["error_log"] == "err"  # sin error_log param y has_error_log False -> mantiene


def test_update_clip_status_output_path() -> None:
    clip = SimpleNamespace(status="PROCESSING", tags=None, storage_path="/tmp/old.mp4")
    _update_clip_status(MagicMock(), clip, "COMPLETED", output_path="/tmp/new.mp4")
    assert clip.storage_path == "/tmp/new.mp4"


def test_resolve_video_path_found(tmp_path: Path) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x" * 20)
    clip = _clip(storage_path=str(f))
    db = MagicMock()
    assert _resolve_video_path(clip, db) == str(f)


def test_resolve_video_path_none(tmp_path: Path) -> None:
    clip = _clip(storage_path=str(tmp_path / "nope.mp4"))
    db = MagicMock()
    assert _resolve_video_path(clip, db) is None


def test_run_subtitle_pipeline_invalid_id() -> None:
    try:
        run_subtitle_pipeline("no-un-uuid")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_run_subtitle_pipeline_clip_not_found() -> None:
    with patch.object(sp, "_get_clip_or_none", return_value=None), patch.object(sp, "SessionLocal") as SL:
        SL.return_value = MagicMock()
        run_subtitle_pipeline(uuid.uuid4())
        SL.return_value.close.assert_called()


def test_run_subtitle_pipeline_success(tmp_path: Path) -> None:
    cid = uuid.uuid4()
    clip = _clip(start=0.0, end=10.0, status="COMPLETED")
    db = MagicMock()
    db.get.return_value = clip
    video_path = str(tmp_path / "v.mp4")
    Path(video_path).write_bytes(b"x" * 30)

    with patch.object(sp, "_get_clip_or_none", return_value=clip), patch.object(sp, "_resolve_video_path", return_value=video_path), patch.object(sp, "SessionLocal", MagicMock()) as SL, patch(
        "backend_fastapi.app.services.runpod_service.is_runpod_configured", return_value=False
    ), patch("backend_fastapi.app.services.whisper_service.extract_audio_wav") as ext, patch(
        "backend_fastapi.app.services.whisper_service.transcribe_wav", return_value=[{"start": 0.0, "end": 2.0, "text": "Hola.", "words": [{"start": 0, "end": 1, "text": "Hola"}]}]
    ) as tr, patch("backend_fastapi.app.services.ass_generator.write_ass_file") as we, patch(
        "backend_fastapi.app.services.ffmpeg_service.burn_subtitles"
    ) as bs:
        ext.side_effect = lambda vp, wp: wp
        run_subtitle_pipeline(cid)
        assert tr.called
        assert we.called
        assert bs.called
