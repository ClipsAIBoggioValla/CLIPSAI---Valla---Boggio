from __future__ import annotations

from pathlib import Path

from backend.core.schemas import TranscriptData


STYLE_MAP = {
    "karaoke_yellow": "FontName=Plus Jakarta Sans,FontSize=22,PrimaryColour=&H00F1F105,OutlineColour=&H80000000,BorderStyle=3,Outline=2",
    "neon_green": "FontName=Plus Jakarta Sans,FontSize=22,PrimaryColour=&H0000FF00,OutlineColour=&H80000000,BorderStyle=3,Outline=2",
    "minimal_white": "FontName=Plus Jakarta Sans,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3,Outline=1",
}


def words_to_ass(transcript: TranscriptData, style: str = "karaoke_yellow") -> str:
    header = f"[Script Info]\nTitle: {transcript.video_id}\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BorderStyle,Outline,Shadow,Alignment,MarginV\nStyle: Default,{STYLE_MAP.get(style, STYLE_MAP['karaoke_yellow'])},0,10,2,0,2,10\n\n[Events]\nFormat: Layer, Start, End, Style, Text\n"
    lines = []
    for w in transcript.words:
        s = f"{int(w.start//3600):02}:{int((w.start%3600)//60):02}:{w.start%60:05.2f}"
        e = f"{int(w.end//3600):02}:{int((w.end%3600)//60):02}:{w.end%60:05.2f}"
        lines.append(f"Dialogue: 0,{s},{e},Default,{w.word}")
    return header + "\n".join(lines)


def write_ass(transcript: TranscriptData, out_path: str, style: str = "karaoke_yellow") -> str:
    Path(out_path).write_text(words_to_ass(transcript, style), encoding="utf-8")
    return out_path
