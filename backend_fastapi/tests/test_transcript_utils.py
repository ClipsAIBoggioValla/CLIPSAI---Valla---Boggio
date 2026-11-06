from __future__ import annotations

from backend_fastapi.app.services.transcript_utils import parse_transcript_text_to_segments


def test_empty_text_returns_empty():
    assert parse_transcript_text_to_segments("") == []
    assert parse_transcript_text_to_segments("   ") == []


def test_none_handled():
    assert parse_transcript_text_to_segments(None) == []  # type: ignore[arg-type]


def test_bracket_format():
    txt = "[0 - 3] hola\n[3 - 6] mundo"
    segs = parse_transcript_text_to_segments(txt)
    assert len(segs) == 2
    assert segs[0] == {"start": 0.0, "end": 3.0, "text": "hola"}
    assert segs[1] == {"start": 3.0, "end": 6.0, "text": "mundo"}


def test_timestamp_mm_ss():
    txt = "0:00 - hola\n0:05 - mundo"
    segs = parse_transcript_text_to_segments(txt)
    assert len(segs) == 2
    assert segs[0]["start"] == 0.0
    assert segs[0]["text"] == "hola"
    assert segs[1]["start"] == 5.0
    assert segs[1]["text"] == "mundo"


def test_timestamp_hh_mm_ss():
    txt = "01:02:03 - hola"
    segs = parse_transcript_text_to_segments(txt)
    assert len(segs) == 1
    assert segs[0]["start"] == 3723.0


def test_no_timestamp_synthetic_window():
    txt = "linea uno\nlinea dos"
    segs = parse_transcript_text_to_segments(txt)
    assert len(segs) == 2
    assert segs[0]["start"] == 0.0 and segs[0]["end"] == 3.0
    assert segs[1]["start"] == 3.0 and segs[1]["end"] == 6.0


def test_bracket_invalid_skipped_to_text():
    txt = "[a - b] x"
    segs = parse_transcript_text_to_segments(txt)
    assert len(segs) == 1
    assert segs[0]["text"] == "[a - b] x"
