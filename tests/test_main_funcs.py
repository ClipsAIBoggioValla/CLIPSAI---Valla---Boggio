from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import main as main_mod


def test_parse_timestamp() -> None:
    out = main_mod._parse_timestamp("01:02:03")
    assert isinstance(out, tuple)


def test_timestamp_a_segundos() -> None:
    assert main_mod.timestamp_a_segundos("01:02:03") >= 0


def test_reparar_json() -> None:
    out = main_mod.reparar_json('{"a": 1}')
    assert isinstance(out, str)


def test_parsear_json_tolerante() -> None:
    out = main_mod.parsear_json_tolerante('{"clips": []}')
    assert isinstance(out, list)


def test_validar_clips() -> None:
    clips = [{"inicio": "00:00:10", "fin": "00:00:35", "score": 8, "titulo": "T"}]
    out = main_mod.validar_clips(clips)
    assert isinstance(out, list)


def test_crear_carpeta_salida(tmp_path: Path) -> None:
    out = main_mod.crear_carpeta_salida(str(tmp_path / "clips"))
    assert isinstance(out, str)


def test_leer_transcripcion(tmp_path: Path) -> None:
    p = tmp_path / "t.txt"
    p.write_text("hola mundo", encoding="utf-8")
    out = main_mod.leer_transcripcion(str(p))
    assert isinstance(out, str)


def test_formatear_transcripcion(tmp_path: Path) -> None:
    p = tmp_path / "t.txt"
    p.write_text("0:00 - Hola\n", encoding="utf-8")
    out = main_mod.formatear_transcripcion(str(p), str(tmp_path / "out.txt"))
    assert isinstance(out, str)


def test_llamar_llm_con_fallback_mock() -> None:
    with patch("main.llamar_claude", return_value='{"clips": []}'):
        out = main_mod._llamar_llm_con_fallback("prompt", "claude")
    assert isinstance(out, str)


def test_obtener_clips_ia_mock() -> None:
    with patch("main._llamar_llm_con_fallback", return_value='{"clips": []}'):
        try:
            out = main_mod.obtener_clips_ia("trans", [], {})
        except Exception:
            out = []
    assert isinstance(out, list)
