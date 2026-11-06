from __future__ import annotations

from backend_fastapi.app.services.claude_service import (
    _build_output_schema,
    _build_export_viral_clips_tool,
    _build_claude_prompt,
    _is_model_not_found_error,
    _has_strong_punctuation,
    _format_transcript,
    _format_sentence_map,
    _get_key,
    _validate_one_clip,
)


def test_build_output_schema() -> None:
    schema = _build_output_schema(["S_1", "S_2"])
    assert schema["required"] == ["clips"]
    clips = schema["properties"]["clips"]
    assert clips["type"] == "array"
    assert clips["maxItems"] == 3
    item = clips["items"]
    assert item["required"] == ["start_sentence_id", "end_sentence_id", "score", "title", "hook_candidates", "has_hook"]
    assert item["properties"]["score"]["minimum"] == 1
    assert item["properties"]["score"]["maximum"] == 10


def test_build_export_viral_clips_tool() -> None:
    tool = _build_export_viral_clips_tool(["S_1"])
    assert tool["name"] == "export_viral_clips"
    assert tool["input_schema"]["type"] == "object"


def test_build_claude_prompt() -> None:
    p1 = _build_claude_prompt("TRANS", ["S_1"], 60.5)
    assert "TRANS" in p1
    assert "60.5" in p1
    assert "S_1" in p1
    p2 = _build_claude_prompt("TRANS", ["S_1"])
    assert "desconocida" in p2.lower()


def test_is_model_not_found_error() -> None:
    class AnthropicNotFoundError(Exception):
        pass

    assert _is_model_not_found_error(AnthropicNotFoundError("boom")) is True
    assert _is_model_not_found_error(Exception("Model not found")) is True
    assert _is_model_not_found_error(Exception("model not found: x")) is True
    assert _is_model_not_found_error(Exception("something else")) is False


def test_has_strong_punctuation() -> None:
    assert _has_strong_punctuation("hola.") is True
    assert _has_strong_punctuation("hola") is False
    assert _has_strong_punctuation("hola!") is True


def test_get_key() -> None:
    assert isinstance(_get_key(), str)


def test_format_sentence_map() -> None:
    sm = [
        {
            "id": "S_1",
            "start": 0.0,
            "end": 2.0,
            "text": "Hola mundo.",
            "words": [
                {"start": 0, "end": 1, "text": "Hola"},
                {"start": 1, "end": 2, "text": "mundo."},
            ],
        }
    ]
    out = _format_sentence_map(sm)
    assert isinstance(out, str)
    assert "Hola" in out


def test_format_transcript_valid() -> None:
    segs = [
        {
            "start": 0,
            "end": 3,
            "text": "Hola mundo.",
            "words": [
                {"start": 0, "end": 1, "text": "Hola"},
                {"start": 1, "end": 2, "text": "mundo."},
            ],
        }
    ]
    out = _format_transcript(segs)
    assert isinstance(out, str)


def test_format_transcript_empty_raises() -> None:
    try:
        _format_transcript([])
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass


def test_validate_one_clip_valid() -> None:
    c = {
        "start_sentence_id": "S_1",
        "end_sentence_id": "S_2",
        "score": 8.0,
        "title": "Titulo",
        "hook_candidates": [
            {
                "start_sentence_id": "S_1",
                "end_sentence_id": "S_2",
                "curiosity_score": 9,
                "makes_sense_standalone": True,
            }
        ],
        "has_hook": True,
    }
    out = _validate_one_clip(c)
    assert out is not None
    assert out["score"] == 8.0
    assert out["has_hook"] is True
    assert len(out["hook_candidates"]) == 1


def test_validate_one_clip_with_times_returns_none() -> None:
    c = {
        "start": 0,
        "end": 5,
        "score": 8.0,
        "title": "Titulo",
        "hook_candidates": [],
        "has_hook": False,
    }
    assert _validate_one_clip(c) is None


def test_validate_one_clip_bad_title_returns_none() -> None:
    c = {
        "start_sentence_id": "S_1",
        "end_sentence_id": "S_2",
        "score": 8.0,
        "title": "   ",
        "hook_candidates": [],
        "has_hook": False,
    }
    assert _validate_one_clip(c) is None
