from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services.whisper_service import transcribe_video


def test_transcribe_video_runpod_path(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    with patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", return_value=True), patch(
        "backend_fastapi.app.services.runpod_service.process_local_video_via_runpod",
        return_value={"transcription_segments": [{"start": 0, "end": 1, "text": "hi"}]},
    ):
        out = transcribe_video(str(src))
    assert len(out) == 1


def test_transcribe_video_runpod_no_segments(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    with patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", return_value=True), patch(
        "backend_fastapi.app.services.runpod_service.process_local_video_via_runpod",
        return_value={"transcription_segments": []},
    ):
        with pytest.raises(RuntimeError):
            transcribe_video(str(src))


def test_transcribe_video_local_no_audio(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    with patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", return_value=False), patch(
        "backend_fastapi.app.services.whisper_service._has_audio_track", return_value=False
    ):
        with pytest.raises(ValueError):
            transcribe_video(str(src))


def test_transcribe_video_local_ok(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"y" * 100)
    with patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", return_value=False), patch(
        "backend_fastapi.app.services.whisper_service._has_audio_track", return_value=True
    ), patch("backend_fastapi.app.services.whisper_service.extract_audio_wav", return_value=str(wav)), patch(
        "backend_fastapi.app.services.whisper_service.transcribe_wav",
        return_value=[{"start": 0.0, "end": 1.0, "text": "hi", "words": []}],
    ):
        out = transcribe_video(str(src))
    assert len(out) == 1
