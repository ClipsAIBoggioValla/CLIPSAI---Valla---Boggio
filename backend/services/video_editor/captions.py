from __future__ import annotations

from pathlib import Path

from backend.core.schemas import TranscriptData

STYLE_MAP = {
    "karaoke_yellow": "FontName=Plus Jakarta Sans,FontSize=28,PrimaryColour=&H00F1F105,OutlineColour=&H80000000,BorderStyle=3,Outline=3,Shadow=1,Alignment=2,MarginV=140",
    "neon_green": "FontName=Plus Jakarta Sans,FontSize=28,PrimaryColour=&H0000FF7F,OutlineColour=&H80000000,BorderStyle=3,Outline=3,Shadow=1,Alignment=2,MarginV=140",
    "minimal_white": "FontName=Plus Jakarta Sans,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3,Outline=2,Shadow=0,Alignment=2,MarginV=140",
}


def words_to_ass(transcript: TranscriptData, style: str = "karaoke_yellow") -> str:
    s = STYLE_MAP.get(style, STYLE_MAP["karaoke_yellow"])
    header = (
        "[Script Info]\n"
        f"Title: {transcript.video_id}\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\nPlayResY: 1920\n"
        "WrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,{s},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,10,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    def _fmt(t: float) -> str:
        h = int(t // 3600); m = int((t % 3600) // 60); s_ = t % 60
        return f"{h}:{m:02d}:{s_:05.2f}"
    lines = []
    for w in transcript.words:
        lines.append(f"Dialogue: 0,{_fmt(w.start)},{_fmt(w.end)},Default,,0,0,0,,{w.word}")
    return header + "\n".join(lines)


def write_ass(transcript: TranscriptData, out_path: str, style: str = "karaoke_yellow") -> str:
    Path(out_path).write_text(words_to_ass(transcript, style), encoding="utf-8")
    return out_path
