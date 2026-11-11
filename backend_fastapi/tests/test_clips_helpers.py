from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from backend_fastapi.app.routers.clips import _load_segments_and_hooks


def test_load_segments_and_hooks_disabled() -> None:
    v = SimpleNamespace(filepath="/tmp/nope.mp4", transcript=None, transcription_filepath=None, duration_seconds=None)
    segs, hooks = _load_segments_and_hooks(v, False, False)
    assert segs == [] and hooks == []


def test_load_segments_and_hooks_from_transcript() -> None:
    v = SimpleNamespace(
        filepath="/tmp/nope.mp4",
        transcript="0:00 - Hola mundo\n0:30 - Segundo segmento",
        transcription_filepath=None,
        duration_seconds=60,
    )
    with patch("backend_fastapi.app.services.whisper_service.transcribe_video", side_effect=Exception("no whisper")):
        segs, hooks = _load_segments_and_hooks(v, True, False)
    assert len(segs) > 0
    assert hooks == []


def test_load_segments_and_hooks_hook_mock() -> None:
    v = SimpleNamespace(
        filepath="/tmp/nope.mp4",
        transcript="0:00 - Hola mundo\n0:30 - Segundo segmento",
        transcription_filepath=None,
        duration_seconds=60,
    )
    with patch("backend_fastapi.app.services.whisper_service.transcribe_video", side_effect=Exception("no whisper")), patch(
        "backend_fastapi.app.services.hook_service.detect_hooks", return_value=[]
    ):
        segs, hooks = _load_segments_and_hooks(v, True, True)
    assert len(segs) > 0
    assert hooks == []
