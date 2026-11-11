from __future__ import annotations

import uuid

import pytest

from backend_fastapi.app.services import engine as eng
from backend_fastapi.app.services import editor as ed


def _sentence_map():
    return [
        {"id": "S_0", "start": 0.0, "end": 2.0, "text": "Hola mundo", "words": [{"start": 0.0, "end": 1.0, "text": "Hola"}]},
        {"id": "S_1", "start": 2.0, "end": 4.0, "text": "Chau", "words": [{"start": 2.0, "end": 3.0, "text": "Chau"}]},
    ]


def test_select_clip_hook_no_candidates():
    clip = {"has_hook": False, "hook_candidates": []}
    sel = eng._select_clip_hook(clip, _sentence_map(), 0.0, 10.0)
    assert isinstance(sel, dict) or sel is None


def test_run_clip_engine_transcription_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        eng.run_clip_engine(str(tmp_path / "v.mp4"), str(tmp_path / "no.txt"))


def test_editor_reframe_bad_aspect():
    with pytest.raises(RuntimeError):
        ed.reframe_video("/tmp/v.mp4", "/tmp/out.mp4", aspect_ratio="16:9")
