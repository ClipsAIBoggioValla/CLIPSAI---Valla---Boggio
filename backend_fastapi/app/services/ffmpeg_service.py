from __future__ import annotations

import subprocess
from pathlib import Path

# ---- Hook Teaser estandarizado (issue #116) ---------------------------------
HOOK_TEASER_DURACION = 5.0      # objetivo: teaser de video de 5s en ambos caminos
HOOK_TEASER_MIN = 4.5           # banda válida del teaser efectivo
HOOK_TEASER_MAX = 5.5
ZOOM_TEASER = 1.08              # zoom leve sobre la ventana del hook
VOLUMEN_SFX = 0.13              # whoosh ≤ -18 dB respecto al diálogo
SFX_DURACION = 0.9              # duración del whoosh generado con lavfi
SFX_LAVFI = "anoisesrc=color=pink:seed=20261122:amplitude=0.5"
SFX_DIR = "/app/sfx"
SFX_PRESETS_LAVFI = {
    "tension": "anoisesrc=color=brown:seed=117:r=48000:a=0.5,lowpass=f=600",
    "impact": "sine=f=55:r=48000",
    "transition": "anoisesrc=color=pink:seed=116:r=48000:a=0.6,lowpass=f=1200",
}
MOOD_DEFAULT = "transition"
_SFX_MOODS = ("tension", "impact", "transition", "none")

# B&W + zoom: desatura el teaser y hace zoom-in 1.08 recortando al tamaño original.
FILTRO_TEASER_BW = (
    f"eq=saturation=0,scale=trunc(iw*{ZOOM_TEASER}/2)*2:trunc(ih*{ZOOM_TEASER}/2)*2,crop=iw:ih"
)

# Zoom dinámico por picos RMS (issue #117) — espejo exacto de video_processor.py.
ZOOM_MAX_BODY = 1.12
ZOOM_RAMPA = 0.2               # 200ms de subida/bajada por pico
ZOOM_TOP_K = 10                # máx. picos por clip (expresión acotada)
ZOOM_FPS = 30                  # fps fijo: cero desfasaje A/V con nvenc


def _ventana_pico(t_pico: float, rampa: float = ZOOM_RAMPA) -> str:
    """Término de zoom para un pico: sube 200ms, mantiene ~200ms, baja 200ms."""
    return (
        f"clip((it-{t_pico:.3f})/{rampa:.3f},0,1)"
        f"*clip(({t_pico + 2 * rampa:.3f}-it)/{rampa:.3f},0,1)"
    )


def _filtro_zoompan(picos: list[float], fps: int = ZOOM_FPS, zoom_max: float = ZOOM_MAX_BODY) -> str:
    """zoompan guiado por picos RMS (issue #117): 1.0 -> 1.12 -> 1.0.

    Usa `it` (tiempo de entrada; `t` no existe en vf_zoompan) y fps explícito
    con d=1 para que la duración nunca se altere respecto al audio.
    Sin picos devuelve \"\" -> filtergraph estático (fallback CA-4).
    """
    if not picos:
        return ""
    picos_acotados = sorted(picos)[:ZOOM_TOP_K]
    terminos = ",".join(_ventana_pico(p) for p in picos_acotados)
    return (
        f"fps={fps},zoompan=z='1+{(zoom_max - 1):.2f}*max({terminos},0)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps={fps}"
    )


def _normalizar_ventana_hook(
    hook_start: float, hook_end: float, clip_start: float, clip_end: float
) -> tuple[float, float]:
    """Estandariza el teaser a `HOOK_TEASER_DURACION` recortado a la ventana del clip.

    El hook del LLM puede durar 3-6s; el teaser de video siempre se renderiza a
    ~5s (issue #116) empezando en hook_start (o lo más cerca posible del final
    del clip si no hay lugar). El shift del ASS usa la MISMA ventana, así que
    subtítulos y teaser quedan alineados.
    """
    dur = min(HOOK_TEASER_DURACION, max(0.0, clip_end - clip_start))
    inicio = min(max(hook_start, clip_start), max(clip_start, clip_end - dur))
    return round(inicio, 3), round(inicio + dur, 3)


def _check_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=5)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg no instalado o no en PATH") from exc
    except Exception as exc:
        raise RuntimeError(f"FFmpeg no disponible: {exc}") from exc


def _es_ruta_windows(posix: str) -> bool:
    """True si la ruta posix parece de Windows (segundo carácter ':')."""
    return ":" in posix and posix[1] == ":"


def _duplicar_escape_unidad(escaped: str, posix: str) -> str:
    """Duplica el escape del separador de unidad (C\\:) en rutas Windows."""
    if escaped.startswith(("C\\:", "D\\:", "E\\:")):
        return escaped.replace("\\:", "\\\\:", 1)
    if "\\:" in escaped and _es_ruta_windows(posix):
        return escaped.replace("\\:", "\\\\:", 1)
    return escaped


def escape_subtitles_path(path: str | Path) -> str:
    p = Path(path).resolve()
    posix = p.as_posix()
    escaped = posix.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,").replace("[", "\\[").replace("]", "\\]")
    return _duplicar_escape_unidad(escaped, posix)


def _escape_for_filter(path: str | Path) -> str:
    return escape_subtitles_path(path)


def _stderr_de_resultado(result, defecto: str) -> str:
    """stderr decodificado del resultado de subprocess (o el texto por defecto)."""
    if result.stderr:
        return result.stderr.decode(errors="ignore")
    return defecto


def _auditar_ass(ass: Path) -> None:
    """Auditoría silenciosa de las primeras líneas del ASS."""
    try:
        ass_lines = Path(ass).read_text(encoding="utf-8").splitlines()[:5]
        for idx, line in enumerate(ass_lines, 1):
            pass
    except Exception as exc:
        pass


def _verificar_dimensiones_probe(probe) -> None:
    """Chequeo silencioso de dimensiones 9:16 conocidas."""
    if probe.returncode == 0 and probe.stdout.strip():
        wh = probe.stdout.strip()
        if wh not in ("1080x1920", "720x1280"):
            pass


def _auditar_dimensiones(src: Path) -> None:
    """Auditoría silenciosa de las dimensiones del video fuente."""
    try:
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(src)], capture_output=True, text=True, timeout=10)
        _verificar_dimensiones_probe(probe)
    except Exception as exc:
        pass


def _ejecutar_ffmpeg_burn(cmd: list[str], src: Path, timeout_seconds: int):
    """Ejecuta el burn de subtítulos; RuntimeError ante instalación/timeout."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"FFmpeg no instalado: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"FFmpeg timeout {timeout_seconds}s para {src.name}") from exc


def _exigir_codigo_burn(result, vf: str) -> None:
    """RuntimeError si ffmpeg devolvió código != 0."""
    if result.returncode != 0:
        raw = _stderr_de_resultado(result, "sin stderr")
        err = raw[-2500:] if len(raw) > 2500 else raw
        raise RuntimeError(f"FFmpeg burned-in falló (vf={vf}, code={result.returncode}): {err}")


def _exigir_archivo_burn(out: Path, result) -> None:
    """RuntimeError si el burn no produjo un archivo válido."""
    if not out.is_file() or out.stat().st_size == 0:
        err = _stderr_de_resultado(result, "")[:800]
        raise RuntimeError(f"FFmpeg no produjo archivo valido en {out}. stderr: {err}")


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
    _auditar_ass(ass)
    _auditar_dimensiones(src)
    result = _ejecutar_ffmpeg_burn(cmd, src, timeout_seconds)
    _exigir_codigo_burn(result, vf)
    _exigir_archivo_burn(out, result)
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


def _exigir_rango_cut(start_time: float, end_time: float) -> float:
    """Duración del corte validada (2-90s); ValueError si el rango es inválido."""
    if end_time <= start_time:
        raise ValueError(f"end_time {end_time} debe ser > start_time {start_time}")
    duration = end_time - start_time
    if not (2.0 <= duration <= 90.0):
        raise ValueError(f"Duracion {duration:.1f}s fuera de rango 2-90s")
    return duration


def _exigir_salida_cut(out: Path, result) -> None:
    """RuntimeError si el cut falló o no produjo archivo."""
    if result.returncode != 0:
        err = _stderr_de_resultado(result, "sin stderr")[-2000:]
        raise RuntimeError(f"cut_segment fallo code={result.returncode}: {err}")
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"cut_segment no produjo {out}")


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
    duration = _exigir_rango_cut(start_time, end_time)
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
    result = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
    _exigir_salida_cut(out, result)
    return str(out)


def _filtro_teaser_bw() -> str:
    """Filtergraph -vf del teaser: B&W + zoom 1.08 (issue #116)."""
    return FILTRO_TEASER_BW


def _cortar_teaser_bw(
    input_video: str | Path,
    hook_start: float,
    hook_end: float,
    output_path: str | Path,
) -> str:
    """Corta el teaser del hook aplicando B&W (eq=saturation=0) y zoom 1.08."""
    src = Path(input_video)
    out = Path(output_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video no encontrado: {src}")
    duration = _exigir_rango_cut(hook_start, hook_end)
    out.parent.mkdir(parents=True, exist_ok=True)
    _check_ffmpeg()
    cmd: list[str] = [
        "ffmpeg", "-y",
        "-ss", f"{hook_start:.3f}",
        "-i", str(src),
        "-t", f"{duration:.3f}",
        "-vf", _filtro_teaser_bw(),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
    _exigir_salida_cut(out, result)
    return str(out)


def _exigir_videos_concat(video_paths: list[str | Path]) -> None:
    """ValueError/FileNotFoundError si la lista de videos no es válida para concat."""
    if len(video_paths) < 2:
        raise ValueError("concat_videos requiere >=2 videos")
    for p in video_paths:
        if not Path(p).is_file():
            raise FileNotFoundError(f"Video para concat no encontrado: {p}")


def _escribir_lista_concat(list_file, video_paths: list[str | Path]) -> None:
    """Escribe el archivo de lista para el demuxer concat."""
    for p in video_paths:
        pp = Path(p).resolve().as_posix()
        esc = pp.replace("'", "'\\''")
        list_file.write(f"file '{esc}'\n")
    list_file.close()


def _exigir_salida_concat(out: Path, result) -> None:
    """RuntimeError si el concat falló o no produjo archivo."""
    if result.returncode != 0:
        err = _stderr_de_resultado(result, "sin stderr")[-2500:]
        raise RuntimeError(f"concat_videos fallo code={result.returncode}: {err}")
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"concat no produjo {out}")


def _ejecutar_concat(list_file, out: Path, crf: int, preset: str) -> None:
    """Corre ffmpeg concat y valida la salida."""
    cmd: list[str] = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file.name,
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
    _exigir_salida_concat(out, result)


def _borrar_lista_concat(list_file) -> None:
    """Borra el archivo de lista temporal (silencioso)."""
    try:
        Path(list_file.name).unlink(missing_ok=True)
    except Exception:
        pass


def concat_videos(
    video_paths: list[str | Path],
    output_path: str | Path,
    crf: int = 18,
    preset: str = "ultrafast",
) -> str:
    _exigir_videos_concat(video_paths)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _check_ffmpeg()
    import tempfile

    list_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    try:
        _escribir_lista_concat(list_file, video_paths)
        _ejecutar_concat(list_file, out, crf, preset)
        return str(out)
    finally:
        _borrar_lista_concat(list_file)


def _exigir_rangos_hook(hook_dur: float, clip_dur: float, hook_start: float, hook_end: float) -> None:
    """Valida duraciones y rangos del hook/clip; ValueError si no aplican.

    Teaser estandarizado a ~5s (issue #116): la ventana efectiva sale de
    `_normalizar_ventana_hook`, así que 4.5-5.5s es la banda válida.
    """
    if not (HOOK_TEASER_MIN < hook_dur < HOOK_TEASER_MAX):
        raise ValueError(f"Hook duracion {hook_dur:.3f}s debe estar estrictamente entre {HOOK_TEASER_MIN} y {HOOK_TEASER_MAX}s")
    if not (15.0 <= clip_dur <= 60.0):
        raise ValueError(f"Clip duracion {clip_dur:.1f}s debe ser 15-60s")
    if not (0.0 <= hook_start < hook_end):
        raise ValueError(f"Rango de hook invalido: [{hook_start},{hook_end}]")


def _exigir_hook_en_fuente(hook_start: float, hook_end: float, source_duration) -> None:
    """ValueError si el hook se sale de la duración del video fuente."""
    if source_duration is None or hook_end > source_duration + 0.05:
        raise ValueError(
            f"Hook [{hook_start:.3f},{hook_end:.3f}] fuera de duración de video "
            f"({source_duration if source_duration is not None else 'desconocida'}s)"
        )


def _tiene_pista_audio(src: Path) -> bool:
    """True si el ffprobe del stream a:0 devuelve índice (con audio)."""
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
    return bool(audio_probe.stdout.strip())


def _mood_valido(sfx_mood: str | None) -> str:
    """mood con whitelist; default 'transition' si falta o es inválido."""
    mood = str(sfx_mood or "").strip().lower()
    return mood if mood in _SFX_MOODS else MOOD_DEFAULT


def _input_sfx(sfx_mood: str) -> list | None:
    """Args del input SFX según mood; None si mood='none' (sin SFX)."""
    if sfx_mood == "none":
        return None
    wav = Path(SFX_DIR) / f"{sfx_mood}.wav"
    if wav.is_file():
        return ["-i", str(wav)]
    preset = SFX_PRESETS_LAVFI.get(sfx_mood, SFX_PRESETS_LAVFI[MOOD_DEFAULT])
    return ["-f", "lavfi", "-t", f"{SFX_DURACION:.3f}", "-i", preset]


def _filtro_sfx_whoosh(hook_dur: float) -> str:
    """Cadena del SFX whoosh para la transición teaser→cuerpo.

    Nivel ≤ -18 dB respecto al diálogo (`volume=0.13`), fades de 80/250 ms y
    arranque ~250 ms antes del corte entre segmentos (criterio #116).
    """
    delay_ms = int(max(0.0, hook_dur - SFX_DURACION + 0.25) * 1000)
    return (
        f"[2:a]volume={VOLUMEN_SFX},afade=t=in:st=0:d=0.08,"
        f"afade=t=out:st={SFX_DURACION - 0.25:.3f}:d=0.25,adelay={delay_ms}|all=1[sfx]"
    )


def _filtro_y_maps(
    transition_seconds: float, hook_dur: float, clip_dur: float, has_audio: bool, con_sfx: bool = True
) -> tuple[str, list[str]]:
    """filter_complex y maps del ensamble hook+cuerpo (con o sin audio).

    Atenúa 100ms al final del teaser y 100ms al inicio del cuerpo (transición
    total 200ms) y, con audio + con_sfx, mezcla un SFX whoosh sutil en la
    transición.
    """
    fade_edge = min(transition_seconds / 2.0, hook_dur / 2.0, clip_dur / 2.0)
    hook_fade_start = max(0.0, hook_dur - fade_edge)
    video = (
        f"[0:v]fade=t=out:st={hook_fade_start:.3f}:d={fade_edge:.3f},setsar=1[v0];"
        f"[1:v]fade=t=in:st=0:d={fade_edge:.3f},setsar=1[v1];"
    )
    if not has_audio:
        return video + "[v0][v1]concat=n=2:v=1:a=0[v]", ["-map", "[v]"]
    audio = (
        f"[0:a]afade=t=out:st={hook_fade_start:.3f}:d={fade_edge:.3f}[a0];"
        f"[1:a]afade=t=in:st=0:d={fade_edge:.3f}[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a];"
    )
    if not con_sfx:
        return video + audio, ["-map", "[v]", "-map", "[a]"]
    return (
        video + audio
        + f"{_filtro_sfx_whoosh(hook_dur)};"
        + "[v][a][sfx]amix=inputs=2:duration=first:normalize=0[aout]",
        ["-map", "[v]", "-map", "[aout]"],
    )


def _exigir_archivo_ensamble(out: Path) -> None:
    """RuntimeError si el ensamble no produjo el archivo final."""
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg no produjo el clip ensamblado: {out}")


def _exigir_salida_ensamble(out: Path, result) -> None:
    """RuntimeError si el ensamble falló o no produjo archivo."""
    if result.returncode != 0:
        err = _stderr_de_resultado(result, "sin stderr")[-2500:]
        raise RuntimeError(f"FFmpeg falló al ensamblar teaser + cuerpo con transición: {err}")
    _exigir_archivo_ensamble(out)


def _ensamblar_hook(
    hook_tmp: Path, clip_tmp: Path, out: Path, filter_graph: str, maps: list[str],
    has_audio: bool, sfx_input: list | None = None,
) -> None:
    """Corre ffmpeg para ensamblar teaser+cuerpo (input SFX según mood) y valida la salida."""
    out.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-y", "-i", str(hook_tmp), "-i", str(clip_tmp)]
    if sfx_input:
        command.extend(sfx_input)
    command.extend(["-filter_complex", filter_graph, *maps])
    command.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18"])
    if has_audio:
        command.extend(["-c:a", "aac", "-b:a", "192k"])
    command.extend(["-movflags", "+faststart", str(out)])
    result = subprocess.run(command, capture_output=True, check=False, timeout=300)
    _exigir_salida_ensamble(out, result)


def _limpiar_tmpdir_hook(tmpdir: Path, hook_tmp: Path, clip_tmp: Path) -> None:
    """Borra los MP4 temporales del hook y el directorio (silencioso)."""
    for p in (hook_tmp, clip_tmp):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
    try:
        tmpdir.rmdir()
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
    sfx_mood: str = MOOD_DEFAULT,
) -> str:
    src = Path(input_video)
    out = Path(output_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video no encontrado: {src}")
    # Teaser estandarizado a ~5s (issue #116): la ventana del LLM se normaliza
    # ANTES de validar, así que ass_generator y el render usan la misma ventana.
    hook_start, hook_end = _normalizar_ventana_hook(hook_start, hook_end, clip_start, clip_end)
    hook_dur = hook_end - hook_start
    clip_dur = clip_end - clip_start
    _exigir_rangos_hook(hook_dur, clip_dur, hook_start, hook_end)
    source_duration = probe_duration(src)
    _exigir_hook_en_fuente(hook_start, hook_end, source_duration)
    if not (0.0 < transition_seconds <= 0.2):
        raise ValueError("transition_seconds debe estar entre 0 y 0.2 segundos")
    import tempfile

    sfx_input = _input_sfx(_mood_valido(sfx_mood))
    tmpdir = Path(tempfile.mkdtemp(prefix="hook_"))
    hook_tmp = tmpdir / "hook.mp4"
    clip_tmp = tmpdir / "clip.mp4"
    try:
        _cortar_teaser_bw(src, hook_start, hook_end, hook_tmp)
        cut_segment(src, clip_start, clip_end, clip_tmp)
        has_audio = _tiene_pista_audio(src)
        filter_graph, maps = _filtro_y_maps(
            transition_seconds, hook_dur, clip_dur, has_audio, con_sfx=sfx_input is not None
        )
        _ensamblar_hook(hook_tmp, clip_tmp, out, filter_graph, maps, has_audio, sfx_input)
        return str(out)
    finally:
        _limpiar_tmpdir_hook(tmpdir, hook_tmp, clip_tmp)
