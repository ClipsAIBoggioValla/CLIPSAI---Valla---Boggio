from __future__ import annotations

from pathlib import Path

from backend_fastapi.app.services.engine import (
    _ends_with_strong_punctuation,
    _validate_video_source,
    _resolve_sentence_timestamps,
    _resolve_hook_candidate_window,
    _hook_has_disallowed_lead,
    _select_clip_hook,
    _parse_transcript_native,
)
from backend_fastapi.app.services.claude_service import build_sentence_map


def _sentence_map() -> list[dict]:
    return build_sentence_map(
        [
            {
                "start": 0,
                "end": 3,
                "text": "Hola mundo.",
                "words": [
                    {"start": 0, "end": 1, "text": "Hola"},
                    {"start": 1, "end": 2, "text": "mundo."},
                ],
            },
            {
                "start": 2,
                "end": 5,
                "text": "Esto es genial.",
                "words": [
                    {"start": 2, "end": 3, "text": "Esto"},
                    {"start": 3, "end": 4, "text": "es"},
                    {"start": 4, "end": 5, "text": "genial."},
                ],
            },
        ]
    )


def test_ends_with_strong_punctuation() -> None:
    assert _ends_with_strong_punctuation("hola.") is True
    assert _ends_with_strong_punctuation("hola") is False
    assert _ends_with_strong_punctuation("hola!") is True
    assert _ends_with_strong_punctuation("hola?") is True
    assert _ends_with_strong_punctuation('"hola.")') is True


def test_hook_has_disallowed_lead() -> None:
    assert _hook_has_disallowed_lead("y entonces vamos") is True
    assert _hook_has_disallowed_lead("Bueno que tal") is True
    assert _hook_has_disallowed_lead("hola que tal") is False
    assert _hook_has_disallowed_lead("") is False


def test_validate_video_source_ok(tmp_path: Path) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    p = _validate_video_source(f)
    assert p == f


def test_validate_video_source_empty(tmp_path: Path) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"")
    try:
        _validate_video_source(f)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_validate_video_source_missing() -> None:
    try:
        _validate_video_source("/tmp/definitely_missing_file_xyz.mp4")
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_resolve_sentence_timestamps_valid() -> None:
    sm = _sentence_map()
    start_t, end_t = _resolve_sentence_timestamps("S_1", "S_1", sm)
    assert start_t == 0.0
    assert end_t == 2.35


def test_resolve_sentence_timestamps_unknown_ids() -> None:
    sm = _sentence_map()
    try:
        _resolve_sentence_timestamps("S_9", "S_1", sm)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_resolve_hook_candidate_window_valid() -> None:
    sm = _sentence_map()
    cand = {
        "start_sentence_id": "S_1",
        "end_sentence_id": "S_2",
        "curiosity_score": 9,
        "makes_sense_standalone": True,
    }
    w = _resolve_hook_candidate_window(cand, sm)
    assert w is not None
    assert w["start_time"] == 0.0
    assert w["end_time"] == 5.0
    assert w["duration"] == 5.0
    assert w["text"]


def test_resolve_hook_candidate_window_unknown() -> None:
    sm = _sentence_map()
    w = _resolve_hook_candidate_window({"start_sentence_id": "S_X", "end_sentence_id": "S_Y"}, sm)
    assert w is None


def test_select_clip_hook_in_clip_fallback() -> None:
    sm = _sentence_map()
    clip = {"has_hook": True, "hook_candidates": []}
    selected = _select_clip_hook(clip, sm, 0.0, 10.0)
    assert selected is not None
    assert selected["mode"] == "in_clip"
    assert selected["source"] == "in_clip_fallback"


def test_select_clip_hook_in_clip_teaser() -> None:
    sm = _sentence_map()
    clip = {
        "has_hook": True,
        "hook_candidates": [
            {
                "start_sentence_id": "S_1",
                "end_sentence_id": "S_2",
                "curiosity_score": 9,
                "makes_sense_standalone": True,
            }
        ],
    }
    selected = _select_clip_hook(clip, sm, 3.0, 12.0)
    assert selected is not None
    assert selected["mode"] == "teaser"


def test_select_clip_hook_in_clip_fallback_mode() -> None:
    sm = _sentence_map()
    clip = {"has_hook": True, "hook_candidates": []}
    selected = _select_clip_hook(clip, sm, 0.0, 10.0)
    assert selected is not None
    assert selected["mode"] == "in_clip"
    assert selected["source"] == "in_clip_fallback"
