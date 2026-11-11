from __future__ import annotations

import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.routers.jobs import (
    _resolve_storage_dir,
    _ensure_clips_payload,
    _persist_transcription_diagnosis,
    _log_claude_config,
    _validate_job_video_and_transcription,
)


def test_resolve_storage_dir() -> None:
    d = _resolve_storage_dir()
    assert isinstance(d, Path)


def test_ensure_clips_payload_ok() -> None:
    assert _ensure_clips_payload([1], uuid.uuid4(), SimpleNamespace(id=1), 5) is None


def test_ensure_clips_payload_raises() -> None:
    import pytest
    with pytest.raises(RuntimeError):
        _ensure_clips_payload([], uuid.uuid4(), SimpleNamespace(id=1), 5)


def test_persist_transcription_diagnosis_with_transcript() -> None:
    db = MagicMock()
    job = SimpleNamespace(id=uuid.uuid4())
    db.get.return_value = job
    out = _persist_transcription_diagnosis(db, job, job.id, True, "/tmp/t.txt")
    assert out is not None


def test_persist_transcription_diagnosis_without_transcript() -> None:
    db = MagicMock()
    job = SimpleNamespace(id=uuid.uuid4())
    db.get.return_value = job
    out = _persist_transcription_diagnosis(db, job, job.id, False, "")
    assert out is not None


def test_log_claude_config() -> None:
    _log_claude_config()


def test_validate_job_video_and_transcription_ok(tmp_path: Path) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x" * 100)
    t = tmp_path / "t.txt"
    t.write_text("hi", encoding="utf-8")
    video = SimpleNamespace(
        filepath=str(f), transcription_filepath=str(t), transcript="hi there", id=uuid.uuid4()
    )
    vp, tp, has = _validate_job_video_and_transcription(video)
    assert vp == str(f)
    assert has is True


def test_validate_job_video_and_transcription_missing_video(tmp_path: Path) -> None:
    import pytest
    video = SimpleNamespace(filepath=str(tmp_path / "nope.mp4"), transcription_filepath="", transcript="", id=uuid.uuid4())
    with pytest.raises(FileNotFoundError):
        _validate_job_video_and_transcription(video)


def test_validate_job_video_and_transcription_empty_video(tmp_path: Path) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"")
    video = SimpleNamespace(filepath=str(f), transcription_filepath="", transcript="", id=uuid.uuid4())
    import pytest
    with pytest.raises((RuntimeError, FileNotFoundError)):
        _validate_job_video_and_transcription(video)
