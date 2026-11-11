from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services.engine import run_clip_engine


def test_run_clip_engine_missing_video(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        run_clip_engine(str(tmp_path / "nope.mp4"), str(tmp_path / "t.txt"))


def test_run_clip_engine_missing_transcript(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    with pytest.raises(FileNotFoundError):
        run_clip_engine(str(src), str(tmp_path / "nope.txt"))


def test_run_clip_engine_runpod_path(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    tp = tmp_path / "t.txt"
    tp.write_text("hi", encoding="utf-8")
    with patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", return_value=True), patch(
        "backend_fastapi.app.services.runpod_service.process_local_video_via_runpod",
        return_value={"transcription_segments": [{"start": 0, "end": 1, "text": "hi"}]},
    ):
        out = run_clip_engine(str(src), str(tp), allow_runpod=True)
    assert isinstance(out, dict)
    assert out.get("engine") == "runpod"


def test_run_clip_engine_runpod_no_segments_raises(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    tp = tmp_path / "t.txt"
    tp.write_text("hi", encoding="utf-8")
    with patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", return_value=True), patch(
        "backend_fastapi.app.services.runpod_service.process_local_video_via_runpod",
        return_value={"transcription_segments": []},
    ):
        with pytest.raises(RuntimeError):
            run_clip_engine(str(src), str(tp), allow_runpod=True)
