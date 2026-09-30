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
    timeout_seconds: int = 300,
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


def cut_segment(
    input_video: str | Path,
    start_time: float,
    end_time: float,
    output_path: str | Path,
    crf: int = 18,
    preset: str = "ultrafast",
) -> str:
    src = Path(input_video)
    out = Path(output_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video no encontrado: {src}")
    if end_time <= start_time:
        raise ValueError(f"end_time {end_time} debe ser > start_time {start_time}")
    duration = end_time - start_time
    if not (2.0 <= duration <= 90.0):
        raise ValueError(f"Duracion {duration:.1f}s fuera de rango 2-90s")
    out.parent.mkdir(parents=True, exist_ok=True)
    _check_ffmpeg()
    cmd: list[str] = [
        "ffmpeg", "-y",
        "-ss", f"{start_time:.3f}",
        "-i", str(src),
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ]
    print(f"[ffmpeg] cut {start_time:.1f}->{end_time:.1f} ({duration:.1f}s) cmd: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
    if result.returncode != 0:
        err = result.stderr.decode(errors="ignore")[-2000:] if result.stderr else "sin stderr"
        raise RuntimeError(f"cut_segment fallo code={result.returncode}: {err}")
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"cut_segment no produjo {out}")
    return str(out)


def concat_videos(
    video_paths: list[str | Path],
    output_path: str | Path,
    crf: int = 18,
    preset: str = "ultrafast",
) -> str:
    if len(video_paths) < 2:
        raise ValueError("concat_videos requiere >=2 videos")
    for p in video_paths:
        if not Path(p).is_file():
            raise FileNotFoundError(f"Video para concat no encontrado: {p}")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _check_ffmpeg()
    import tempfile

    list_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    try:
        for p in video_paths:
            pp = Path(p).resolve().as_posix()
            esc = pp.replace("'", "'\\''")
            list_file.write(f"file '{esc}'\n")
        list_file.close()
        cmd: list[str] = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file.name,
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out),
        ]
        print(f"[ffmpeg] concat {len(video_paths)} segments cmd: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
        if result.returncode != 0:
            err = result.stderr.decode(errors="ignore")[-2500:] if result.stderr else "sin stderr"
            raise RuntimeError(f"concat_videos fallo code={result.returncode}: {err}")
        if not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError(f"concat no produjo {out}")
        return str(out)
    finally:
        try:
            Path(list_file.name).unlink(missing_ok=True)
        except Exception:
            pass


def build_hook_clip(
    input_video: str | Path,
    clip_start: float,
    clip_end: float,
    hook_start: float,
    hook_end: float,
    output_path: str | Path,
    transition_seconds: float = 0.2,
) -> str:
    src = Path(input_video)
    out = Path(output_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video no encontrado: {src}")
    hook_dur = hook_end - hook_start
    clip_dur = clip_end - clip_start
    if not (2.5 < hook_dur < 5.5):
        raise ValueError(f"Hook duracion {hook_dur:.3f}s debe estar estrictamente entre 2.5 y 5.5s")
    if not (15.0 <= clip_dur <= 60.0):
        raise ValueError(f"Clip duracion {clip_dur:.1f}s debe ser 15-60s")
    if not (0.0 <= hook_start < hook_end):
        raise ValueError(f"Rango de hook invalido: [{hook_start},{hook_end}]")
    source_duration = probe_duration(src)
    if source_duration is None or hook_end > source_duration + 0.05:
        raise ValueError(
            f"Hook [{hook_start:.3f},{hook_end:.3f}] fuera de duración de video "
            f"({source_duration if source_duration is not None else 'desconocida'}s)"
        )
    if not (0.0 < transition_seconds <= 0.2):
        raise ValueError("transition_seconds debe estar entre 0 y 0.2 segundos")
    import tempfile

    tmpdir = Path(tempfile.mkdtemp(prefix="hook_"))
    hook_tmp = tmpdir / "hook.mp4"
    clip_tmp = tmpdir / "clip.mp4"
    try:
        cut_segment(src, hook_start, hook_end, hook_tmp)
        cut_segment(src, clip_start, clip_end, clip_tmp)
        audio_probe = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=index", "-of", "csv=p=0", str(src),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if audio_probe.returncode != 0:
            raise RuntimeError(f"No se pudo verificar audio para transición hook: {audio_probe.stderr[-1000:]}")
        has_audio = bool(audio_probe.stdout.strip())

        # Atenúa 100ms al final del teaser y 100ms al inicio del cuerpo: transición total 200ms.
        fade_edge = min(transition_seconds / 2.0, hook_dur / 2.0, clip_dur / 2.0)
        hook_fade_start = max(0.0, hook_dur - fade_edge)
        if has_audio:
            filter_graph = (
                f"[0:v]fade=t=out:st={hook_fade_start:.3f}:d={fade_edge:.3f},setsar=1[v0];"
                f"[1:v]fade=t=in:st=0:d={fade_edge:.3f},setsar=1[v1];"
                f"[0:a]afade=t=out:st={hook_fade_start:.3f}:d={fade_edge:.3f}[a0];"
                f"[1:a]afade=t=in:st=0:d={fade_edge:.3f}[a1];"
                "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
            )
            maps = ["-map", "[v]", "-map", "[a]"]
        else:
            filter_graph = (
                f"[0:v]fade=t=out:st={hook_fade_start:.3f}:d={fade_edge:.3f},setsar=1[v0];"
                f"[1:v]fade=t=in:st=0:d={fade_edge:.3f},setsar=1[v1];"
                "[v0][v1]concat=n=2:v=1:a=0[v]"
            )
            maps = ["-map", "[v]"]

        out.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg", "-y", "-i", str(hook_tmp), "-i", str(clip_tmp),
            "-filter_complex", filter_graph, *maps,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        ]
        if has_audio:
            command.extend(["-c:a", "aac", "-b:a", "192k"])
        command.extend(["-movflags", "+faststart", str(out)])
        result = subprocess.run(command, capture_output=True, check=False, timeout=300)
        if result.returncode != 0:
            err = result.stderr.decode(errors="ignore")[-2500:] if result.stderr else "sin stderr"
            raise RuntimeError(f"FFmpeg falló al ensamblar teaser + cuerpo con transición: {err}")
        if not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError(f"FFmpeg no produjo el clip ensamblado: {out}")
        print(
            f"[ffmpeg] teaser split hook={hook_start:.3f}-{hook_end:.3f} "
            f"({hook_dur:.3f}s) + cuerpo={clip_start:.3f}-{clip_end:.3f} "
            f"({clip_dur:.3f}s), fade total={transition_seconds:.3f}s -> {out}"
        )
        return str(out)
    finally:
        for p in (hook_tmp, clip_tmp):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            tmpdir.rmdir()
        except Exception:
            pass
