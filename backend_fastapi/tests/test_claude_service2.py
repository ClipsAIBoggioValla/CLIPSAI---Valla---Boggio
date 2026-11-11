from __future__ import annotations

from unittest.mock import patch

from backend_fastapi.app.services.claude_service import select_clips_via_claude, _parse_and_validate


def _segs():
    return [
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


def test_select_clips_via_claude_empty_raises() -> None:
    import pytest
    with pytest.raises(RuntimeError):
        select_clips_via_claude([])


def test_select_clips_via_claude_no_key_raises() -> None:
    import pytest
    with patch("backend_fastapi.app.services.claude_service._get_key", return_value=""):
        with pytest.raises(RuntimeError):
            select_clips_via_claude(_segs())


def test_select_clips_via_claude_ok() -> None:
    raw = '{"clips": [{"start_sentence_id":"S_1","end_sentence_id":"S_2","score":8.0,"title":"T","hook_candidates":[],"has_hook":false}]}'
    with patch("backend_fastapi.app.services.claude_service._get_key", return_value="k"), patch(
        "backend_fastapi.app.services.claude_service._call_anthropic", return_value=raw
    ):
        out = select_clips_via_claude(_segs())
    assert isinstance(out, list)
    assert len(out) == 1


def test_parse_and_validate_ok() -> None:
    raw = '{"clips": [{"start_sentence_id":"S_1","end_sentence_id":"S_2","score":8.0,"title":"T","hook_candidates":[],"has_hook":false}]}'
    out = _parse_and_validate(raw)
    assert isinstance(out, list)
    assert len(out) == 1
