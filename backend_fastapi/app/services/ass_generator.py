from __future__ import annotations

from pathlib import Path
from typing import TypedDict


class SubtitleSegment(TypedDict):
    start: float
    end: float
    text: str


ASS_STYLE_VERTICAL = (
    "Arial,70,&H00FFFFFF,&H00000000,&H00000000,&H80000000,"
    "1,0,0,0,100,100,0,0,1,4,2,2,40,40,280,1"
)


ASS_HEADER_TEMPLATE = (
    "[Script Info]\n"
    "Title: {title}\n"
    "ScriptType: v4.00+\n"
    "WrapStyle: 0\n"
    "ScaledBorderAndShadow: yes\n"
    "PlayResX: 1080\n"
    "PlayResY: 1920\n"
    "YCbCr Matrix: TV.709\n"
    "\n"
    "[V4+ Styles]\n"
    "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
    "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
    "Alignment,MarginL,MarginR,MarginV,Encoding\n"
    "Style: Default,{style}\n"
    "\n"
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)


def _format_ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _sanitize_text(text: str) -> str:
    t = (text or "").strip().upper()
    if not t:
        return ""
    t = t.replace("\\", "\\\\")
    t = t.replace("{", "\\{").replace("}", "\\}")
    t = t.replace("\n", " ").replace("\r", " ")
    t = " ".join(t.split())
    return t


def _wrap_text(text: str, max_chars: int = 28) -> str:
    words = text.split()
    if not words:
        return text
    lines: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for w in words:
        add = len(w) + (1 if cur else 0)
        if cur_len + add > max_chars and cur:
            lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += add
    if cur:
        lines.append(" ".join(cur))
    return "\\N".join(lines)


def generate_ass_content(
    segments: list[SubtitleSegment],
    title: str = "clipsai",
    style: str | None = None,
    max_chars_per_line: int = 28,
    min_duration: float = 0.8,
    max_duration: float = 6.0,
) -> str:
    style_str = style or ASS_STYLE_VERTICAL
    header = ASS_HEADER_TEMPLATE.format(title=title or "clipsai", style=style_str)
    lines: list[str] = []
    for seg in segments:
        try:
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            text_raw = str(seg.get("text", "") or "")
        except Exception:
            continue
        if end <= start:
            end = start + min_duration
        dur = end - start
        if dur < 0.15:
            continue
        if dur < min_duration:
            end = start + min_duration
        if dur > max_duration:
            end = start + max_duration
        text = _sanitize_text(text_raw)
        if not text:
            continue
        wrapped = _wrap_text(text, max_chars=max_chars_per_line)
        lines.append(f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,,{wrapped}")
    return header + "\n".join(lines)


def write_ass_file(
    segments: list[SubtitleSegment],
    output_path: str | Path,
    title: str = "clipsai",
    style: str | None = None,
) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    content = generate_ass_content(segments, title=title, style=style)
    out.write_text(content, encoding="utf-8")
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"No se pudo generar ASS en {out}")
    return str(out)


def segments_from_transcript_words(words: list[dict]) -> list[SubtitleSegment]:
    result: list[SubtitleSegment] = []
    for w in words:
        try:
            result.append(
                SubtitleSegment(
                    start=float(w["start"]),
                    end=float(w["end"]),
                    text=str(w["text"]),
                )
            )
        except Exception:
            continue
    return result


def generate_ass_for_clip(
    segments: list[SubtitleSegment],
    output_path: str | Path,
    clip_title: str | None = None,
) -> str:
    return write_ass_file(segments, output_path, title=clip_title or "clipsai")
