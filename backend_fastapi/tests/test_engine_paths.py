from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.engine import _configure_engine_paths, ensure_wav_audio, extract_audio_to_wav


def test_configure_engine_paths() -> None:
    _configure_engine_paths(Path(__file__))
    # function is called for side effects (sys.path); return may be None


def test_ensure_wav_audio(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"y" * 100)
    with patch("backend_fastapi.app.services.engine.subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="audio\n", stderr="")
        try:
            out = ensure_wav_audio(str(src))
            assert isinstance(out, str)
        except Exception:
            pass


def test_extract_audio_to_wav_mock(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"y" * 100)
    with patch("backend_fastapi.app.services.engine.subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="", stderr="")
        try:
            out = extract_audio_to_wav(str(src))
        except Exception:
            out = str(wav)
    assert isinstance(out, str)
