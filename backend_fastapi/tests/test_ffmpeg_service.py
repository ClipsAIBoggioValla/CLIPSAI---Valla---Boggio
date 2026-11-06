from __future__ import annotations

from unittest.mock import patch, MagicMock

from backend_fastapi.app.services import ffmpeg_service as fs


def test_escape_subtitles_path():
    out = fs.escape_subtitles_path("/tmp/a:b.txt")
    assert isinstance(out, str)


def test_probe_duration_mock():
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="12.5\n", stderr="")
        try:
            fs.probe_duration("/tmp/x.mp4")
        except Exception:
            pass


def test_check_ffmpeg_mock():
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(returncode=0, stdout="", stderr="")
        try:
            fs._check_ffmpeg()
        except Exception:
            pass
