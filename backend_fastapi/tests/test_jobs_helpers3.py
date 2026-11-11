from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.routers.jobs import (
    _load_transcription_segments,
    _detect_hooks_for_segments,
    _select_hook_for_clip,
)


def test_load_transcription_segments_from_transcript() -> None:
    video = SimpleNamespace(
        filepath="/tmp/nope.mp4",
        transcription_filepath=None,
        transcript="0:00 - Hola mundo\n0:30 - Segundo",
        id="v1",
        duration_seconds=10,
    )
    with patch("backend_fastapi.app.routers.jobs.Path.is_file", return_value=False):
        segs = _load_transcription_segments(video)
    assert isinstance(segs, list)


def test_detect_hooks_for_segments_empty() -> None:
    video = SimpleNamespace(id="v1", duration_seconds=10)
    out = _detect_hooks_for_segments([], video)
    assert out == []


def test_detect_hooks_for_segments_mock() -> None:
    video = SimpleNamespace(id="v1", duration_seconds=10)
    with patch("backend_fastapi.app.services.hook_service.detect_hooks", return_value=[]):
        out = _detect_hooks_for_segments([{"start": 0, "end": 5, "text": "hi"}], video)
    assert isinstance(out, list)


def test_select_hook_for_clip_fallback() -> None:
    out = _select_hook_for_clip(0.0, 30.0, None)
    assert isinstance(out, tuple)
    assert out[0] == 0.0


def test_select_hook_for_clip_in_clip() -> None:
    out = _select_hook_for_clip(0.0, 30.0, {"mode": "in_clip"})
    assert out is not None
    assert out[1] == 3.0


def test_select_hook_for_clip_teaser_valid() -> None:
    hs = {"mode": "teaser", "start_time": 5.0, "end_time": 8.0, "curiosity_score": 9, "makes_sense_standalone": True}
    out = _select_hook_for_clip(0.0, 30.0, hs)
    assert out is not None
    assert out[0] == 5.0


def test_select_hook_for_clip_teaser_invalid() -> None:
    hs = {"mode": "teaser", "start_time": 5.0, "end_time": 6.0, "curiosity_score": 5, "makes_sense_standalone": True}
    out = _select_hook_for_clip(0.0, 30.0, hs)
    assert out is not None
    # falls back to in_clip
    assert out[0] == 0.0


def test_select_hook_for_clip_bad_range() -> None:
    assert _select_hook_for_clip(5.0, 3.0, None) is None
    assert _select_hook_for_clip("a", 3.0, None) is None
