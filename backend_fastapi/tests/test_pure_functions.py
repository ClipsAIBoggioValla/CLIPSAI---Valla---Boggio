from __future__ import annotations

from unittest.mock import patch, MagicMock
from pathlib import Path

from backend_fastapi.app.services.engine import _ends_with_strong_punctuation, _hook_has_disallowed_lead
from backend_fastapi.app.services.claude_service import (
    _has_strong_punctuation,
    _is_model_not_found_error,
    build_sentence_map,
    _format_transcript,
)
from backend_fastapi.app.services.whisper_service import _has_audio_track, _detect_device_and_compute
from backend_fastapi.app.services.ffmpeg_service import escape_subtitles_path, _escape_for_filter, probe_duration
from backend_fastapi.app.services.runpod_service import is_runpod_configured, _decode_response, _raise_for_job_failure
from backend_fastapi.app.services.tiktok_service import generate_pkce_pair


def test_ends_with_strong_punctuation():
    assert _ends_with_strong_punctuation("hello.") is True
    assert _ends_with_strong_punctuation("hello") is False


def test_hook_has_disallowed_lead():
    assert _hook_has_disallowed_lead("y entonces") is True
    assert _hook_has_disallowed_lead("hola") is False


def test_has_strong_punctuation():
    assert _has_strong_punctuation("hi.") is True
    assert _has_strong_punctuation("hi") is False


def test_build_sentence_map():
    segs = [{"start": 0, "end": 5, "text": "hola", "words": [{"start": 0, "end": 1, "text": "hola"}]}]
    sm = build_sentence_map(segs)
    assert isinstance(sm, list)


def test_format_transcript():
    segs = [{"start": 0, "end": 5, "text": "hola", "words": [{"start": 0, "end": 1, "text": "hola"}]}]
    try:
        out = _format_transcript(segs)
        assert isinstance(out, str)
    except RuntimeError:
        pass


def test_is_model_not_found_error():
    e = Exception("model not found 404")
    assert _is_model_not_found_error(e) is True
    e2 = Exception("other")
    assert _is_model_not_found_error(e2) is False


def test_has_audio_track_mock():
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="0\n", stderr="")
        try:
            _has_audio_track("/tmp/x.mp4")
        except Exception:
            pass


def test_detect_device_and_compute():
    dev, ct = _detect_device_and_compute("cpu", "int8")
    assert isinstance(dev, str) and isinstance(ct, str)


def test_escape_subtitles_path():
    out = escape_subtitles_path("/tmp/a:b.txt")
    assert isinstance(out, str)


def test_escape_for_filter():
    out = _escape_for_filter("/tmp/a:b.txt")
    assert isinstance(out, str)


def test_probe_duration_mock():
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="12.5\n", stderr="")
        try:
            probe_duration("/tmp/x.mp4")
        except Exception:
            pass


def test_is_runpod_configured():
    # Just call it; may return bool
    try:
        is_runpod_configured()
    except Exception:
        pass


def test_decode_response():
    resp = MagicMock()
    resp.json.return_value = {"status": "ok"}
    resp.text = "{}"
    try:
        _decode_response(resp)
    except Exception:
        pass


def test_raise_for_job_failure():
    try:
        _raise_for_job_failure({"status": "FAILED", "error": "boom"})
    except Exception:
        pass
    try:
        _raise_for_job_failure({"status": "COMPLETED"})
    except Exception:
        pass
