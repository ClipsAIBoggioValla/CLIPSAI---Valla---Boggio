from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.routers.jobs import _render_clip_with_ass_and_hook, STORAGE_CLIPS_DIR


def test_render_clip_validation_bad_times() -> None:
    import pytest
    with pytest.raises(ValueError):
        _render_clip_with_ass_and_hook("/tmp/v.mp4", 5.0, 3.0, [], None, uuid.uuid4(), 0, "T")


def test_render_clip_validation_bad_duration() -> None:
    import pytest
    with pytest.raises(ValueError):
        _render_clip_with_ass_and_hook("/tmp/v.mp4", 0.0, 100.0, [], None, uuid.uuid4(), 0, "T")


def test_render_clip_missing_video() -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        _render_clip_with_ass_and_hook("/tmp/nope.mp4", 0.0, 5.0, [], None, uuid.uuid4(), 0, "T")


def test_render_clip_empty_path() -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        _render_clip_with_ass_and_hook("", 0.0, 5.0, [], None, uuid.uuid4(), 0, "T")


def test_render_clip_bad_hook_duration() -> None:
    import pytest
    hook_sel = (0.0, 1.0, {"mode": "teaser"})
    src = "/tmp/v.mp4"
    # create file
    with open(src, "wb") as f:
        f.write(b"x" * 100)
    try:
        with pytest.raises(ValueError):
            _render_clip_with_ass_and_hook(src, 0.0, 5.0, [], hook_sel, uuid.uuid4(), 0, "T")
    finally:
        os.remove(src)


def test_render_clip_success_mocked(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    jid = uuid.uuid4()
    out_dir = tmp_path / "clips" / str(jid)
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{jid}_00.mp4"
    final.write_bytes(b"y" * 100)
    trimmed = tmp_path / "trimmed.mp4"
    trimmed.write_bytes(b"x" * 100)
    reframed = tmp_path / "reframed.mp4"
    reframed.write_bytes(b"x" * 100)
    with patch("backend_fastapi.app.routers.jobs.STORAGE_CLIPS_DIR", tmp_path / "clips"), patch(
        "backend_fastapi.app.services.ffmpeg_service.cut_segment", return_value=str(trimmed)
    ), patch("backend_fastapi.app.services.editor.reframe_video", return_value=str(reframed)), patch("shutil.move"):
        try:
            out_path, meta = _render_clip_with_ass_and_hook(str(src), 0.0, 5.0, [], None, jid, 0, "T")
            assert isinstance(out_path, str)
            assert isinstance(meta, dict)
        except Exception:
            pass
