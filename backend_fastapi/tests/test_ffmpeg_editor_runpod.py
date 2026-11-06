from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services.ffmpeg_service import burn_subtitles, burn_subtitles_simple, probe_duration, concat_videos
from backend_fastapi.app.services.editor import reframe_video
from backend_fastapi.app.services.runpod_service import is_runpod_configured, _settings, RunPodError


def test_burn_subtitles(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    ass = tmp_path / "v.ass"
    ass.write_text("x", encoding="utf-8")
    out = tmp_path / "out.mp4"
    out.write_bytes(b"y" * 100)
    with patch("backend_fastapi.app.services.ffmpeg_service._check_ffmpeg"), patch(
        "backend_fastapi.app.services.ffmpeg_service.subprocess.run"
    ) as m:
        m.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = burn_subtitles(src, ass, out)
    assert isinstance(res, str)


def test_burn_subtitles_missing_src(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        burn_subtitles(tmp_path / "nope.mp4", tmp_path / "no.ass", tmp_path / "out.mp4")


def test_burn_subtitles_simple(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    ass = tmp_path / "v.ass"
    ass.write_text("x", encoding="utf-8")
    out = tmp_path / "out.mp4"
    out.write_bytes(b"y" * 100)
    with patch("backend_fastapi.app.services.ffmpeg_service._check_ffmpeg"), patch(
        "backend_fastapi.app.services.ffmpeg_service.subprocess.run"
    ) as m:
        m.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = burn_subtitles_simple(src, ass, out)
    assert isinstance(res, str)


def test_probe_duration_mock(tmp_path: Path) -> None:
    with patch("backend_fastapi.app.services.ffmpeg_service.subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="1080x1920", stderr="")
        d = probe_duration(tmp_path / "v.mp4")
    assert d is None or isinstance(d, float)


def test_reframe_video(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x" * 100)
    out = tmp_path / "out.mp4"
    out.write_bytes(b"y" * 100)
    with patch("backend_fastapi.app.services.editor.subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = reframe_video(src, out)
    assert isinstance(res, str)


def test_reframe_video_bad_aspect(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        reframe_video(tmp_path / "v.mp4", tmp_path / "out.mp4", aspect_ratio="16:9")


def test_reframe_video_missing_src(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        reframe_video(tmp_path / "nope.mp4", tmp_path / "out.mp4")


def test_is_runpod_configured() -> None:
    assert isinstance(is_runpod_configured(), bool)


def test_settings_missing() -> None:
    import os
    with patch.dict(os.environ, {"RUNPOD_API_KEY": "", "RUNPOD_ENDPOINT_ID": ""}, clear=False):
        with pytest.raises(RunPodError):
            _settings()


def test_settings_ok() -> None:
    import os
    env = {
        "RUNPOD_API_KEY": "k",
        "RUNPOD_ENDPOINT_ID": "e",
        "RUNPOD_REQUEST_TIMEOUT_SECONDS": "30",
        "RUNPOD_TIMEOUT_SECONDS": "60",
        "RUNPOD_POLL_INTERVAL_SECONDS": "1",
    }
    with patch.dict(os.environ, env, clear=False):
        out = _settings()
    assert len(out) == 6
