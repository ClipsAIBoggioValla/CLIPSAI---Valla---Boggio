from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services.ffmpeg_service import (
    cut_segment,
    concat_videos,
    _build_hook_filter_graph,
    build_hook_clip,
)


def test_build_hook_filter_graph_audio() -> None:
    fg, maps, hfs = _build_hook_filter_graph(4.0, 0.3, True)
    assert "concat=n=2:v=1:a=1" in fg
    assert maps
    assert hfs >= 0


def test_build_hook_filter_graph_no_audio() -> None:
    fg, maps, hfs = _build_hook_filter_graph(4.0, 0.3, False)
    assert "concat=n=2:v=1:a=0" in fg
    assert maps


def test_cut_segment(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    out = tmp_path / "out.mp4"
    out.write_bytes(b"y" * 100)
    with patch("backend_fastapi.app.services.ffmpeg_service._check_ffmpeg"), patch(
        "backend_fastapi.app.services.ffmpeg_service.subprocess.run"
    ) as m:
        m.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = cut_segment(src, 0.0, 5.0, out)
    assert isinstance(res, str)


def test_cut_segment_missing_src() -> None:
    with pytest.raises(FileNotFoundError):
        cut_segment("/tmp/nope.mp4", 0.0, 5.0, "/tmp/out.mp4")


def test_cut_segment_bad_duration(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    with pytest.raises(ValueError):
        cut_segment(src, 0.0, 0.5, tmp_path / "out.mp4")


def test_concat_videos(tmp_path: Path) -> None:
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    a.write_bytes(b"x" * 100)
    b.write_bytes(b"x" * 100)
    out = tmp_path / "out.mp4"
    out.write_bytes(b"y" * 100)
    with patch("backend_fastapi.app.services.ffmpeg_service._check_ffmpeg"), patch(
        "backend_fastapi.app.services.ffmpeg_service.subprocess.run"
    ) as m:
        m.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = concat_videos([a, b], out)
    assert isinstance(res, str)


def test_concat_videos_too_few() -> None:
    with pytest.raises(ValueError):
        concat_videos(["/tmp/a.mp4"], "/tmp/out.mp4")


def test_concat_videos_missing() -> None:
    with pytest.raises(FileNotFoundError):
        concat_videos(["/tmp/a.mp4", "/tmp/b.mp4"], "/tmp/out.mp4")


def test_build_hook_clip_bad_hook_dur(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    with pytest.raises(ValueError):
        build_hook_clip(src, 0.0, 30.0, 0.0, 1.0, tmp_path / "out.mp4")


def test_build_hook_clip_missing_src(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_hook_clip(tmp_path / "nope.mp4", 0.0, 30.0, 0.0, 4.0, tmp_path / "out.mp4")
