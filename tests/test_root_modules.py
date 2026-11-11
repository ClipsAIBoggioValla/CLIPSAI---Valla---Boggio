from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import main as main_mod
import engine as engine_mod


def test_cargar_env(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("FOO_BAR=123\n# comment\nBADLINE\nKEY=\"val\"\n", encoding="utf-8")
    main_mod.cargar_env(str(env))
    assert os.environ.get("FOO_BAR") == "123" or "FOO_BAR" in os.environ


def test_validar_entradas_missing() -> None:
    err = engine_mod._validar_entradas("/tmp/nope.mp4", "/tmp/nope.txt")
    assert err is not None


def test_validar_entradas_ok(tmp_path: Path) -> None:
    v = tmp_path / "v.mp4"
    t = tmp_path / "t.txt"
    v.write_bytes(b"x")
    t.write_text("hi", encoding="utf-8")
    err = engine_mod._validar_entradas(str(v), str(t))
    assert err is None


def test_verificar_ffmpeg() -> None:
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(returncode=0)
        assert engine_mod._verificar_ffmpeg() is True
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert engine_mod._verificar_ffmpeg() is False
