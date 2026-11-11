from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services import engine as eng


def test_validate_video_source_missing():
    with pytest.raises(FileNotFoundError):
        eng._validate_video_source("/tmp/definitely_missing_v.mp4")


def test_ends_with_strong_punctuation():
    assert eng._ends_with_strong_punctuation("hola.") is True
    assert eng._ends_with_strong_punctuation("hola") is False


def test_resolve_hook_candidate_window_none():
    out = eng._resolve_hook_candidate_window({"start_sentence_id": "s1", "end_sentence_id": "s2"}, [])
    assert out is None
    out2 = eng._resolve_hook_candidate_window({"start_sentence_id": "s1", "end_sentence_id": "s2"}, [{"id": "s1", "words": []}, {"id": "s2", "words": []}])
    assert out2 is None


def test_hook_has_disallowed_lead():
    assert eng._hook_has_disallowed_lead("Y entonces empezamos") is True
    assert eng._hook_has_disallowed_lead("Hola mundo") is False


def test_parse_transcript_native_simple():
    segs = eng._parse_transcript_native("0:00 - Hola mundo. 0:05 - Chau.")
    assert isinstance(segs, list)
    assert len(segs) >= 0


def test_extract_audio_to_wav_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        eng.extract_audio_to_wav("/tmp/definitely_missing_v2.mp4")


def test_extract_audio_to_wav_no_audio(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 10)
    with patch.object(eng, "_validate_video_source", return_value=src), patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="video\n")
        with pytest.raises(ValueError):
            eng.extract_audio_to_wav(str(src))


def test_ensure_wav_audio_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        eng.ensure_wav_audio("/tmp/definitely_missing_v3.mp4")


def test_run_clip_engine_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        eng.run_clip_engine("/tmp/definitely_missing_v4.mp4", "")
