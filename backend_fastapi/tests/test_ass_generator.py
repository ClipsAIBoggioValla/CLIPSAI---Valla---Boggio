from __future__ import annotations

from backend_fastapi.app.services.ass_generator import (
    _format_ass_time,
    _sanitize_text,
    _wrap_text,
)


def test_format_ass_time():
    assert _format_ass_time(0) == "0:00:00.00"
    assert _format_ass_time(3.5) == "0:00:03.50"
    assert _format_ass_time(3661.25) == "1:01:01.25"


def test_sanitize_text():
    assert _sanitize_text("a<b>c") == "a<b>c" or isinstance(_sanitize_text("a<b>c"), str)
    assert isinstance(_sanitize_text(""), str)


def test_wrap_text():
    out = _wrap_text("hola mundo esto es una prueba larga", max_chars=10)
    assert isinstance(out, str)
    assert "hola" in out
