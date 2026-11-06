from __future__ import annotations

from unittest.mock import patch

from backend_fastapi.app.services.hook_service import detect_hooks, _validate_clips, _parse_json_strict


def test_validate_clips_empty():
    assert _validate_clips({"clips": []}) == []


def test_parse_json_strict():
    import json
    raw = '{"clips": []}'
    assert _parse_json_strict(raw) == {"clips": []}


def test_detect_hooks_mock():
    segs = [{"start": 0, "end": 5, "text": "hola"}]
    # mock provider none -> raises RuntimeError (no fallback)
    try:
        detect_hooks(segs, mock=True)
    except Exception:
        pass
    # mock=True returns mock hooks
    res = detect_hooks(segs, mock=True)
    assert isinstance(res, list)
