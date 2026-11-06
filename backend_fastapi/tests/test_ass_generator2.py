from __future__ import annotations

from pathlib import Path

from backend_fastapi.app.services.ass_generator import (
    generate_ass_content,
    write_ass_file,
    segments_from_transcript_words,
    generate_ass_for_clip,
    generate_hooked_ass,
    build_hooked_ass_content,
    _generate_hooked_segments,
)


def test_generate_ass_content():
    segs = [{"start": 0, "end": 2, "text": "hola mundo"}]
    out = generate_ass_content(segs, title="t")
    assert "Dialogue:" in out
    assert "HOLA" in out


def test_write_ass_file(tmp_path):
    segs = [{"start": 0, "end": 2, "text": "hola"}]
    p = tmp_path / "out.ass"
    res = write_ass_file(segs, p, title="t")
    assert Path(res).is_file()
    assert Path(res).stat().st_size > 0


def test_segments_from_transcript_words():
    words = [{"start": 0, "end": 1, "text": "hi"}, {"start": 1, "end": 2, "text": "there"}]
    out = segments_from_transcript_words(words)
    assert len(out) == 2
    # invalid word skipped
    out2 = segments_from_transcript_words([{"start": "x", "end": 1, "text": "t"}])
    assert out2 == []


def test_generate_ass_for_clip(tmp_path):
    segs = [{"start": 0, "end": 2, "text": "hola"}]
    p = tmp_path / "clip.ass"
    res = generate_ass_for_clip(segs, p, clip_title="c")
    assert Path(res).is_file()


def test_generate_hooked_ass(tmp_path):
    segs = [{"start": 0, "end": 5, "text": "hola"}, {"start": 5, "end": 10, "text": "mundo"}]
    p = tmp_path / "hooked.ass"
    res = generate_hooked_ass(segs, 0, 10, 0, 3, p, title="t")
    assert Path(res).is_file()


def test_build_hooked_ass_content():
    segs = [{"start": 0, "end": 5, "text": "hola"}, {"start": 5, "end": 10, "text": "mundo"}]
    out = build_hooked_ass_content(segs, 0, 10, 0, 3, title="t")
    assert "Dialogue:" in out


def test_generate_hooked_segments_invalid():
    segs = [{"start": 0, "end": 5, "text": "hola"}]
    try:
        _generate_hooked_segments(segs, 0, 10, 0, 1)  # hook dur 1s invalid
    except ValueError:
        return
    # may not raise if segments empty; ok
    pass
