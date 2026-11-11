from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services import whisper_service as ws


def test_check_ffmpeg_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError) as ei:
            ws._check_ffmpeg()
    assert "FFmpeg" in str(ei.value)


def test_check_ffmpeg_called_process_error():
    with patch("subprocess.run", side_effect=__import__("subprocess").CalledProcessError(1, "ffmpeg", output=b"")):
        with pytest.raises(RuntimeError) as ei:
            ws._check_ffmpeg()
    assert "FFmpeg" in str(ei.value)


def test_has_audio_track_missing():
    assert ws._has_audio_track("/tmp/definitely_missing_v_whisper.mp4") is False


def test_has_audio_track_no_audio(tmp_path):
    p = tmp_path / "v.mp4"
    p.write_bytes(b"x" * 10)
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="video\n")
        assert ws._has_audio_track(str(p)) is False
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stdout="")
        assert ws._has_audio_track(str(p)) is False


def test_validate_video_source_empty(tmp_path):
    p = tmp_path / "v.mp4"
    p.write_bytes(b"")
    with pytest.raises(ValueError):
        ws._validate_video_source(str(p))


def test_extract_audio_wav_no_audio(tmp_path):
    p = tmp_path / "v.mp4"
    p.write_bytes(b"x" * 10)
    with patch.object(ws, "_has_audio_track", return_value=False):
        with pytest.raises(ValueError):
            ws.extract_audio_wav(str(p))


def test_transcribe_wav_missing():
    with pytest.raises(FileNotFoundError):
        ws.transcribe_wav("/tmp/definitely_missing_x.wav")


def test_transcribe_wav_model_error(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"z" * 20000)
    with patch("backend_fastapi.app.services.whisper_service._detect_device_and_compute", return_value=("cpu", "int8")), patch(
        "faster_whisper.WhisperModel", side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError) as ei:
            ws.transcribe_wav(str(wav), language="es", model_name="small")
    assert "Whisper" in str(ei.value)
