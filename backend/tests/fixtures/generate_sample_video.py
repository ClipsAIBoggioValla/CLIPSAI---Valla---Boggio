#!/usr/bin/env python3
"""Genera tests/fixtures/sample.mp4 de 10s para desarrollo del renderizador Track B sin depender de Track A."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).with_name("sample.mp4")
ALT_OUT = Path(__file__).parent.parent.parent / "backend" / "tests" / "fixtures" / "sample.mp4"


def via_ffmpeg(out: Path) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=1280x720:rate=30:duration=10",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=10:sample_rate=48000",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        "-vf",
        "drawtext=fontcolor=white:fontsize=48:text='CLIPSAI SAMPLE 10s':x=(w-text_w)/2:y=(h-text_h)/2",
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return out.exists()
    except Exception as e:
        print(f"ffmpeg failed: {e}", file=sys.stderr)
        return False


def via_moviepy(out: Path) -> bool:
    try:
        from moviepy.editor import ColorClip, AudioArrayClip  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return False
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        clip = ColorClip(size=(1280, 720), color=(11, 15, 23), duration=10)
        sr = 48000
        t = np.linspace(0, 10, int(sr * 10), endpoint=False)
        audio = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        stereo = np.column_stack([audio, audio])
        aclip = AudioArrayClip(stereo, fps=sr)
        clip = clip.set_audio(aclip)
        clip.write_videofile(str(out), fps=24, codec="libx264", audio_codec="aac", logger=None, verbose=False)
        return out.exists()
    except Exception as e:
        print(f"moviepy failed: {e}", file=sys.stderr)
        return False


def main() -> None:
    for out in (OUT, ALT_OUT):
        if out.exists():
            print(f"exists: {out}")
            continue
        ok = via_ffmpeg(out)
        if not ok:
            ok = via_moviepy(out)
        if ok:
            print(f"generated: {out} ({out.stat().st_size} bytes)")
        else:
            out.write_text("stub sample.mp4 placeholder - install ffmpeg or moviepy\n")
            print(f"stub created: {out}")


if __name__ == "__main__":
    main()
