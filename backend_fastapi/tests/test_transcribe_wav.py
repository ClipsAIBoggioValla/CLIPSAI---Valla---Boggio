from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services.whisper_service import transcribe_wav


def test_transcribe_wav_mock(tmp_path: Path) -> None:
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
        segs = transcribe_wav(str(wav), language="es", model_name="small")
    assert len(segs) == 1
    assert segs[0]["text"] == "Hola mundo."


def test_transcribe_wav_missing_file() -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        transcribe_wav("/tmp/nope.wav")
