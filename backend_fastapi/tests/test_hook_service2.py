from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.hook_service import (
    _get_provider,
    _format_transcript,
    _build_hook_prompt,
    _parse_json_strict,
    _validate_one_hook_clip,
    _validate_clips,
    _mock_hooks,
    detect_hooks,
    detect_hooks_from_transcript_file,
)


def test_get_provider() -> None:
    p = _get_provider()
    assert isinstance(p, str)


def test_format_transcript() -> None:
    segs = [{"start": 0, "end": 2, "text": "hola"}]
    out = _format_transcript(segs)
    assert isinstance(out, str)


def test_build_hook_prompt() -> None:
    p = _build_hook_prompt("TRANS", 60.0)
    assert "TRANS" in p
    p2 = _build_hook_prompt("TRANS")
    assert "TRANS" in p2


def test_parse_json_strict() -> None:
    d = _parse_json_strict('{"clips": []}')
    assert d == {"clips": []}
    try:
        _parse_json_strict("not json")
    except Exception:
        pass


def test_validate_one_hook_clip_valid() -> None:
    c = {
        "title": "T",
        "start_time": 0,
        "end_time": 30,
        "viral_score": 80,
        "hook": {"text": "h", "start_time": 0, "end_time": 4, "duration": 4},
    }
    out = _validate_one_hook_clip(c)
    assert out is not None


def test_validate_one_hook_clip_invalid() -> None:
    assert _validate_one_hook_clip(None) is None
    assert _validate_one_hook_clip({}) is None
    assert _validate_one_hook_clip({"start": "bad"}) is None


def test_validate_clips() -> None:
    data = {"clips": [{"start": "00:00:10", "end": "00:00:35", "score": 8, "titulo": "T", "text": "x"}]}
    out = _validate_clips(data)
    assert isinstance(out, list)


def test_mock_hooks() -> None:
    segs = [{"start": 0, "end": 5, "text": "hola"}]
    out = _mock_hooks(segs)
    assert isinstance(out, list)


def test_detect_hooks_mock() -> None:
    segs = [{"start": 0, "end": 5, "text": "hola"}]
    out = detect_hooks(segs, mock=True)
    assert isinstance(out, list)


def test_detect_hooks_from_transcript_file(tmp_path: Path) -> None:
    p = tmp_path / "t.txt"
    p.write_text("0:00 - Hola", encoding="utf-8")
    out = detect_hooks_from_transcript_file(p, mock=True)
    assert isinstance(out, list)
