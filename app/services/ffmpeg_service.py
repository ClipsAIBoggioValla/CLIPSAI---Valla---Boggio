from __future__ import annotations

import subprocess
from pathlib import Path


def _check_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=5)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg no instalado o no en PATH") from exc
    except Exception as exc:
        raise RuntimeError(f"FFmpeg no disponible: {exc}") from exc


def escape_subtitles_path(path: str | Path) -> str:
    p = Path(path).resolve()
    posix = p.as_posix()
    escaped = posix.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,").replace("[", "\\[").replace("]", "\\]")
    if escaped.startswith("C\\:") or escaped.startswith("D\\:") or escaped.startswith("E\\:"):
        escaped = escaped.replace("\\:", "\\\\:", 1)
    elif "\\:" in escaped and ":" in posix and posix[1] == ":":
        escaped = escaped.replace("\\:", "\\\\:", 1)
    return escaped


def _escape_for_filter(path: str | Path) -> str:
    return escape_subtitles_path(path)


def burn_subtitles(
    input_video: str | Path,
    ass_path: str | Path,
    output_path: str | Path,
    crf: int = 18,
    preset: str = "ultrafast",
    audio_bitrate: str = "192k",
    timeout_seconds: int = 180,
) -> str:
    src = Path(input_video)
    ass = Path(ass_path)
    out = Path(output_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video de entrada no encontrado: {src}")
    if not ass.is_file():
        raise FileNotFoundError(f"ASS no encontrado: {ass}")
    _check_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    escaped_ass = _escape_for_filter(ass)
    vf = f"ass={escaped_ass}"
    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-b:a",
        audio_bitrate,
        "-movflags",
        "+faststart",
        str(out),
    ]
    try:
        ass_lines = Path(ass).read_text(encoding="utf-8").splitlines()[:5]
        print(f"[ffmpeg] ASS preview ({ass}):")
        for idx, line in enumerate(ass_lines, 1):
            print(f"  {idx}: {line}")
    except Exception as exc:
        print(f"[ffmpeg] WARN no se pudo leer ASS preview: {exc}")
    try:
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(src)], capture_output=True, text=True, timeout=10)
        if probe.returncode == 0 and probe.stdout.strip():
            wh = probe.stdout.strip()
            print(f"[ffmpeg] video dims: {wh} vs ASS PlayRes 1080x1920")
            if wh not in ("1080x1920", "720x1280"):
                print(f"[ffmpeg] WARN descalce PlayRes vs video - se hara scaling (ScaledBorderAndShadow: yes)")
    except Exception as exc:
        print(f"[ffmpeg] WARN probe dims fallo: {exc}")
    print(f"[ffmpeg] cmd: {' '.join(cmd)}")
    print(f"[ffmpeg] vf: {vf} (re-encode libx264, no copy)")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"FFmpeg no instalado: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"FFmpeg timeout {timeout_seconds}s para {src.name}") from exc
    if result.returncode != 0:
        raw = result.stderr.decode(errors="ignore") if result.stderr else "sin stderr"
        err = raw[-2500:] if len(raw) > 2500 else raw
        raise RuntimeError(f"FFmpeg burned-in falló (vf={vf}, code={result.returncode}): {err}")
    if not out.is_file() or out.stat().st_size == 0:
        err = result.stderr.decode(errors="ignore")[:800] if result.stderr else ""
        raise RuntimeError(f"FFmpeg no produjo archivo valido en {out}. stderr: {err}")
    return str(out)


def burn_subtitles_simple(
    input_video: str,
    ass_path: str,
    output_path: str,
) -> str:
    return burn_subtitles(input_video, ass_path, output_path)


def probe_duration(video_path: str | Path) -> float | None:
    src = Path(video_path)
    if not src.is_file():
        return None
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(src)],
            capture_output=True,
            check=True,
            timeout=10,
        )
        return float(result.stdout.decode().strip())
    except Exception:
        return None
