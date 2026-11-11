from __future__ import annotations

import pytest

from backend_fastapi.app.services import editor as ed


def test_reframe_video_bad_aspect():
    with pytest.raises(RuntimeError) as ei:
        ed.reframe_video("/tmp/v.mp4", "/tmp/out.mp4", aspect_ratio="16:9")
    assert "Aspect ratio" in str(ei.value)


def test_reframe_video_missing_source(tmp_path):
    with pytest.raises(RuntimeError) as ei:
        ed.reframe_video(tmp_path / "no.mp4", tmp_path / "out.mp4")
    assert "No se puede aplicar crop" in str(ei.value)
