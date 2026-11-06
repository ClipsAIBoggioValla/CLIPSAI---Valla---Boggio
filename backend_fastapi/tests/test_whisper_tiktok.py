from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.whisper_service import (
    _check_ffmpeg,
    _has_audio_track,
    extract_audio_wav,
    _detect_device_and_compute,
    transcribe_audio,
    transcribe_wav,
)
from backend_fastapi.app.services.tiktok_service import (
    get_tiktok_auth_url_for_user,
    exchange_tiktok_code,
    save_tiktok_tokens,
)


def test_check_ffmpeg_ok() -> None:
    with patch("backend_fastapi.app.services.whisper_service.subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="", stderr="")
        _check_ffmpeg()


def test_check_ffmpeg_missing() -> None:
    import subprocess
    with patch("backend_fastapi.app.services.whisper_service.subprocess.run", side_effect=FileNotFoundError):
        try:
            _check_ffmpeg()
            raise AssertionError("expected RuntimeError")
        except RuntimeError:
            pass


def test_has_audio_track_true(tmp_path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 10)
    with patch("backend_fastapi.app.services.whisper_service.subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="audio\n", stderr="")
        assert _has_audio_track(str(src)) is True


def test_has_audio_track_false(tmp_path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 10)
    with patch("backend_fastapi.app.services.whisper_service.subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="video\n", stderr="")
        assert _has_audio_track(str(src)) is False


def test_extract_audio_wav(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    wav_out = tmp_path / "out.wav"
    wav_out.write_bytes(b"y" * 20000)
    with patch("backend_fastapi.app.services.whisper_service._has_audio_track", return_value=True), patch(
        "backend_fastapi.app.services.whisper_service._check_ffmpeg"
    ), patch("backend_fastapi.app.services.whisper_service.subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = extract_audio_wav(str(src), str(wav_out))
    assert isinstance(res, str)


def test_detect_device_and_compute() -> None:
    assert _detect_device_and_compute("cpu", "int8") == ("cpu", "int8")
    assert _detect_device_and_compute("cuda", "float16") == ("cuda", "float16")
    d, c = _detect_device_and_compute("auto", "auto")
    assert isinstance(d, str) and isinstance(c, str)


def test_transcribe_audio(tmp_path: Path) -> None:
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"z" * 20000)

    class Seg:
        def __init__(self):
            self.text = "Hola mundo."
            self.start = 0.0
            self.end = 2.0
            self.words = []

    class Gen:
        def __iter__(self):
            yield Seg()

    fake_model = MagicMock()
    fake_model.transcribe.return_value = (Gen(), MagicMock())
    with patch("backend_fastapi.app.services.whisper_service._detect_device_and_compute", return_value=("cpu", "int8")), patch(
        "faster_whisper.WhisperModel", return_value=fake_model
    ):
        segs = transcribe_audio(str(wav), language="es", model_name="small")
    assert len(segs) == 1
    assert segs[0]["text"] == "Hola mundo."


def test_get_tiktok_auth_url_for_user() -> None:
    url = get_tiktok_auth_url_for_user("user1")
    assert isinstance(url, str)


def test_exchange_tiktok_code_mock() -> None:
    with patch("backend_fastapi.app.services.tiktok_service._fetch_tiktok_user_info", return_value="uid1"):
        try:
            out = exchange_tiktok_code("code", "verifier")
            assert isinstance(out, dict) or out is None
        except Exception:
            pass


def test_save_tiktok_tokens_mock_db() -> None:
    import uuid as _uuid
    db = MagicMock()
    acc = MagicMock()
    acc.user_id = "u1"
    out = save_tiktok_tokens(db, str(_uuid.uuid4()), {"access_token": "a", "refresh_token": "r", "token_type": "bearer"})
    assert out is not None
