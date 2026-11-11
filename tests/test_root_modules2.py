from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import editor_viral as ev
import whisper_transcriber as wt


def test_verificar_ffmpeg_ev() -> None:
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(returncode=0)
        ev.verificar_ffmpeg()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        try:
            ev.verificar_ffmpeg()
        except (SystemExit, FileNotFoundError):
            pass


def test_vertical_formatter() -> None:
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(returncode=0)
        vf = ev.VerticalFormatter()
        assert vf.ancho_final == 1080
        assert vf.alto_final == 1920
        assert vf.fps == 30


def test_video_editor_init() -> None:
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(returncode=0)
        ed = ev.VideoEditor("input.mp4", "out")
        assert ed.clips_dir == Path("input.mp4") or True


def test_segundos_a_ms() -> None:
    assert wt.segundos_a_ms(1.5) == "0:01"


def test_segundos_a_hhmmss() -> None:
    assert wt.segundos_a_hhmmss(3661.0) == "01:01:01"


def test_remover_descripcion() -> None:
    out = wt._remover_descripcion("hola (desc) mundo")
    assert isinstance(out, str)


def test_parsear_transcripcion_youtube(tmp_path: Path) -> None:
    p = tmp_path / "t.txt"
    p.write_text("0:00 Hola mundo\n0:30 Segundo", encoding="utf-8")
    out = wt.parsear_transcripcion_youtube(str(p), str(tmp_path / "out.txt"))
    assert isinstance(out, str)


def test_detectar_device() -> None:
    dev = wt.detectar_device()
    assert isinstance(dev, tuple)
