from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from backend_fastapi.app.services import claude_service as cs


class _ModelNotFoundError(Exception):
    pass


def test_is_model_not_found_error_variants():
    assert cs._is_model_not_found_error(_ModelNotFoundError("x")) is True
    assert cs._is_model_not_found_error(Exception("404 model not found")) is True
    assert cs._is_model_not_found_error(Exception("some other error")) is False


def test_call_anthropic_with_model_no_key():
    with patch.object(cs, "_get_key", return_value=""):
        with pytest.raises(RuntimeError) as ei:
            cs._call_anthropic_with_model("prompt", [str(uuid.uuid4())], "claude-x")
    assert "Error en API de Claude" in str(ei.value)


def test_parse_and_validate_invalid_json():
    with pytest.raises(RuntimeError) as ei:
        cs._parse_and_validate("not json at all")
    assert "Error en API de Claude" in str(ei.value)


def test_validate_one_clip_invalid():
    bad = {"start": 0, "end": 5, "score": 8}
    assert cs._validate_one_clip(bad) is None


def test_select_clips_via_claude_no_key():
    with patch.object(cs, "_get_key", return_value=""):
        with pytest.raises(RuntimeError) as ei:
            cs.select_clips_via_claude([{"start": 0, "end": 2, "text": "hola"}])
    assert "Error en API de Claude" in str(ei.value)


def test_select_clips_via_claude_no_segments():
    with patch.object(cs, "_get_key", return_value="k"):
        with pytest.raises(RuntimeError) as ei:
            cs.select_clips_via_claude([])
    assert "Error en API de Claude" in str(ei.value)
