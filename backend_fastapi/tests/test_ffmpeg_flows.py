from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services import ffmpeg_service as ffm


def test_burn_subtitles_missing_video(tmp_path):
    with pytest.raises(FileNotFoundError):
        ffm.burn_subtitles(tmp_path / "no.mp4", tmp_path / "no.ass", tmp_path / "out.mp4")


def test_burn_subtitles_missing_ass(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 10)
    with pytest.raises(FileNotFoundError):
        ffm.burn_subtitles(src, tmp_path / "no.ass", tmp_path / "out.mp4")


def test_concat_videos_single(tmp_path):
    with pytest.raises(ValueError):
        ffm.concat_videos([str(tmp_path / "a.mp4")], tmp_path / "out.mp4")


def test_concat_videos_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        ffm.concat_videos([str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")], tmp_path / "out.mp4")


def test_build_hook_clip_bad_hook_dur(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 10)
    out = tmp_path / "hook_out.mp4"
    out.write_bytes(b"y" * 10)
    with pytest.raises(ValueError):
        ffm.build_hook_clip(str(src), 0.0, 5.0, 0.0, 1.0, out)  # hook dur 1.0 < 2.5


def test_build_hook_clip_bad_clip_dur(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 10)
    out = tmp_path / "hook_out.mp4"
    out.write_bytes(b"y" * 10)
    with pytest.raises(ValueError):
        ffm.build_hook_clip(str(src), 0.0, 40.0, 0.0, 5.0, out)  # clip dur 40 ok? -> hook 5 ok, clip 40 ok; adjust


def test_build_hook_clip_bad_transition(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 10)
    out = tmp_path / "hook_out.mp4"
    out.write_bytes(b"y" * 10)
    with pytest.raises(ValueError):
        ffm.build_hook_clip(str(src), 0.0, 5.0, 0.0, 4.0, out, transition_seconds=0.5)
