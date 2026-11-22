"""Procesamiento de clips verticales 9:16 con subtítulos y hook."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("video_processor")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

FFMPEG_BIN = "/usr/local/bin/ffmpeg"

# ---- Hook Teaser unificado con backend (issue #116) --------------------------
TEASER_DURACION = 5.0          # teaser de video de 5s (mismo estándar que ffmpeg_service)
ZOOM_TEASER = 1.08             # zoom leve sobre la ventana del hook
VOLUMEN_SFX = 0.13             # whoosh ≤ -18 dB respecto al diálogo
SFX_DURACION = 0.9
SFX_LAVFI = "anoisesrc=color=pink:seed=20261122:amplitude=0.5"

# Teaser vertical: crop 9:16 → 1080x1920 → B&W → zoom 1.08 (crop al tamaño final).
FILTRO_TEASER_BW = (
    "crop=ih*9/16:ih,scale=1080:1920,eq=saturation=0,"
    "scale=1166:2074,crop=1080:1920,setsar=1"
)

# Sondeo de NVENC memoizado: se corre `ffmpeg -encoders` UNA vez por proceso
# solo si RUNPOD_GPU está activo (issue: render GPU). Sin GPU env -> libx264
# directo, sin subprocess extra (local y tests quedan byte-a-byte iguales).
_probe_nvenc_cache: bool | None = None

_GPU_ENV_ACTIVO = ("1", "true", "yes")


def _sondear_nvenc() -> bool:
    """True si el binario ffmpeg lista el encoder h264_nvenc (sin driver en build)."""
    if os.environ.get("RUNPOD_GPU", "").lower() not in _GPU_ENV_ACTIVO:
        return False
    try:
        result = subprocess.run(
            [FFMPEG_BIN, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=15,
        )
        return "h264_nvenc" in (result.stdout or "")
    except Exception as exc:
        logger.warning("[video_processor] Sondeo NVENC falló: %s", exc)
        return False


def _nvenc_disponible() -> bool:
    """Resultado memoizado del sondeo NVENC (1 probe por proceso)."""
    global _probe_nvenc_cache
    if _probe_nvenc_cache is None:
        _probe_nvenc_cache = _sondear_nvenc()
        estado = "h264_nvenc (GPU)" if _probe_nvenc_cache else "libx264 (CPU)"
        logger.info("[video_processor] Encoder de video seleccionado: %s", estado)
    return _probe_nvenc_cache


def _args_codec_video(quality: str) -> list:
    """Args del codec de video: nvenc (-preset p4 -cq) con GPU; libx264 ultrafast sin GPU."""
    if _nvenc_disponible():
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", quality, "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", quality]


def generate_ass_from_segments(
    segments: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    output_path: str,
    title: str = "clipsai",
    hook_text: str | None = None
) -> str:
    """Genera archivo ASS desde segmentos de transcripción para un clip específico.

    El hook se integra como PRIMER evento con estilo "Hook" (texto grande arriba,
    primeros 3s) — evita drawtext, que no existe en el ffmpeg estático de RunPod.

    Args:
        segments: Lista de segmentos con start, end, text
        clip_start: Inicio del clip en segundos
        clip_end: Fin del clip en segundos
        output_path: Ruta donde guardar el archivo ASS
        title: Título del video
        hook_text: Texto del hook para los primeros 3 segundos (opcional)

    Returns:
        Ruta del archivo ASS generado
    """
    clipped = _recortar_segmentos_ass(segments, clip_start, clip_end)

    # Generar contenido ASS
    ass_content = f"""[Script Info]
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,70,&H00FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,40,40,280,1
Style: Hook,DejaVu Sans,80,&H00FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,3,8,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # 1) Hook como PRIMER evento (0-3s, estilo grande arriba)
    if hook_text:
        ass_content += _evento_hook_ass(hook_text, clip_start, clip_end)

    # 2) Subtítulos normales después, con su estilo Default (abajo, más chico)
    for seg in clipped:
        ass_content += _evento_dialogue_ass(seg)

    Path(output_path).write_text(ass_content, encoding="utf-8")
    _diagnosticar_ass(output_path, ass_content, hook_text)
    return output_path


def _recortar_segmentos_ass(segments: List[Dict[str, Any]], clip_start: float, clip_end: float) -> list[dict]:
    """Filtra segmentos dentro del clip y shiftea tiempos a 0."""
    clipped = []
    for s in segments:
        recorte = _segmento_recortado(s, clip_start, clip_end)
        if recorte is not None:
            clipped.append(recorte)
    return clipped


def _valores_segmento(s: Dict[str, Any]) -> tuple | None:
    """(start, end, text) crudos del segmento. None si no se pueden convertir."""
    try:
        st = float(s.get("start", 0))
        en = float(s.get("end", 0))
        txt = str(s.get("text", "")).strip()
    except Exception:
        return None
    return st, en, txt


def _segmento_util(st: float, en: float, txt: str) -> bool:
    """True si el segmento tiene texto y duración positiva."""
    return bool(txt) and en > st


def _fuera_de_ventana(st: float, en: float, clip_start: float, clip_end: float) -> bool:
    """True si el segmento queda fuera de la ventana del clip."""
    return en < clip_start or st > clip_end


def _segmento_aplicable(st: float, en: float, txt: str, clip_start: float, clip_end: float) -> bool:
    """True si el segmento debe aparecer en el ASS del clip."""
    return _segmento_util(st, en, txt) and not _fuera_de_ventana(st, en, clip_start, clip_end)


def _rango_recortado(st: float, en: float, clip_start: float, clip_end: float) -> tuple | None:
    """(cs, ce) recortado a la ventana del clip. None si queda vacío."""
    cs = max(st, clip_start)
    ce = min(en, clip_end)
    if ce > cs:
        return cs, ce
    return None


def _segmento_recortado(s: Dict[str, Any], clip_start: float, clip_end: float) -> dict | None:
    """Segmento shifteado a 0 dentro del clip. None si no aplica."""
    valores = _valores_segmento(s)
    if valores is None:
        return None
    st, en, txt = valores
    if not _segmento_aplicable(st, en, txt, clip_start, clip_end):
        return None
    rango = _rango_recortado(st, en, clip_start, clip_end)
    if rango is None:
        return None
    cs, ce = rango
    return {
        "start": cs - clip_start,
        "end": ce - clip_start,
        "text": txt
    }


def _evento_hook_ass(hook_text: str, clip_start: float, clip_end: float) -> str:
    """Hook como PRIMER evento (0-3s, estilo grande arriba). drawtext no: ffmpeg
    estático de RunPod carece de libfreetype."""
    hook_clean = " ".join(str(hook_text).upper().split())
    hook_clean = hook_clean.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    hook_clean = hook_clean[:100]
    if not hook_clean:
        return ""
    hook_dur = min(3.0, max(0.5, clip_end - clip_start))
    eh = int(hook_dur // 3600)
    em = int((hook_dur % 3600) // 60)
    es = hook_dur % 60
    return f"Dialogue: 0,0:00:00.00,{eh}:{em:02d}:{es:05.2f},Hook,,0,0,0,,{hook_clean}\n"


def _evento_dialogue_ass(seg: dict) -> str:
    """Evento Dialogue de un segmento (escape ffmpeg + uppercase)."""
    start_h = int(seg["start"] // 3600)
    start_m = int((seg["start"] % 3600) // 60)
    start_s = seg["start"] % 60
    end_h = int(seg["end"] // 3600)
    end_m = int((seg["end"] % 3600) // 60)
    end_s = seg["end"] % 60

    text = seg["text"].upper().replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    text = " ".join(text.split())

    return f"Dialogue: 0,{start_h}:{start_m:02d}:{start_s:05.2f},{end_h}:{end_m:02d}:{end_s:05.2f},Default,,0,0,0,,{text}\n"


def _tamano_ass(written: Path) -> int:
    """Tamaño del archivo ASS escrito; -1 si la lectura falla, 0 si no existe."""
    try:
        return written.stat().st_size if written.exists() else 0
    except OSError:
        return -1


def _dialogues(lines: list) -> list:
    """Líneas de eventos Dialogue del ASS."""
    return [l for l in lines if l.startswith("Dialogue:")]


def _eventos_estilo(dialogue_lines: list, estilo: str) -> list:
    """Eventos Dialogue de un estilo dado (p.ej. 'Hook' o 'Default')."""
    return [l for l in dialogue_lines if f",{estilo}," in l]


def _conteo_dialogues(lines: list) -> tuple:
    """Cuenta los eventos Dialogue totales, de estilo Hook y de estilo Default."""
    dialogue_lines = _dialogues(lines)
    return dialogue_lines, _eventos_estilo(dialogue_lines, "Hook"), _eventos_estilo(dialogue_lines, "Default")


def _estructura_ass(ass_content: str) -> tuple:
    """(completa, script, styles, events) según las secciones presentes."""
    has_script = "[Script Info]" in ass_content
    has_styles = "[V4+ Styles]" in ass_content
    has_events = "[Events]" in ass_content
    return (has_script and has_styles and has_events, has_script, has_styles, has_events)


def _log_estructura(ass_content: str) -> None:
    """Avisa si el ASS no tiene las tres secciones completas."""
    completa, has_script, has_styles, has_events = _estructura_ass(ass_content)
    if not completa:
        logger.warning("[video_processor] ERROR: ASS sin estructura completa: ScriptInfo=%s V4Styles=%s Events=%s", has_script, has_styles, has_events)


def _log_dialogues_vacios(dialogue_lines: list) -> None:
    """Avisa si el ASS no tiene ningún evento Dialogue."""
    if not dialogue_lines:
        logger.warning("[video_processor] ERROR: ASS sin eventos Dialogue — ffmpeg quemará SIN subtítulos (segments fuera de ventana o vacío)")


def _log_hook_evento(hook_text: str | None, hook_events: list) -> None:
    """Confirma o avisa la ausencia del evento estilo Hook."""
    if hook_text:
        if hook_events:
            logger.info("[video_processor] OK: Hook presente como evento estilo Hook: %s", hook_events[0][:140])
        else:
            logger.warning("[video_processor] ERROR: hook_text pedido ('%s') pero NO hay evento estilo Hook en [Events]", hook_text[:60])


def _log_primeras_lineas(output_path: str, lines: list) -> None:
    """Vuelca al log las primeras 20 líneas del ASS generado."""
    logger.info("[video_processor] ---- %s | PRIMERAS 20 LINEAS ----", output_path)
    for line in lines[:20]:
        logger.info("[video_processor] ASS| %s", line)
    logger.info("[video_processor] ---- FIN ASS ----")


def _diagnosticar_ass(output_path: str, ass_content: str, hook_text: str | None) -> None:
    """Diagnóstico ASS: validar estructura y volcar contenido (debug subs ausentes)."""
    written = Path(output_path)
    size = _tamano_ass(written)
    lines = ass_content.splitlines()
    dialogue_lines, hook_events, default_events = _conteo_dialogues(lines)
    logger.info(
        "[video_processor] ASS generado: %s (%s bytes, %s líneas, %s Dialogue: hook=%s default=%s)",
        output_path, size, len(lines), len(dialogue_lines), len(hook_events), len(default_events),
    )
    if size <= 0:
        logger.warning("[video_processor] ERROR: ASS VACÍO o inexistente tras escritura: %s (size=%s)", output_path, size)
    _log_estructura(ass_content)
    _log_dialogues_vacios(dialogue_lines)
    _log_hook_evento(hook_text, hook_events)
    _log_primeras_lineas(output_path, lines)


def _filtro_ass(ass_file: str) -> str | None:
    """Filtro 'ass=' escapado para ffmpeg. None si el archivo no existe."""
    if os.path.exists(ass_file):
        ass_size = os.path.getsize(ass_file)
        # Escape ffmpeg: backslashes a /, y ':' / ',' (separadores de filtro)
        # escapados con backslash. Sin comillas alrededor del path.
        ass_escaped = (
            ass_file.replace("\\", "/").replace(":", "\\:").replace(",", "\\,").replace("'", "\\'")
        )
        logger.info("[video_processor] Filtro ASS OK: ass=%s (%s bytes)", ass_escaped, ass_size)
        if ass_size == 0:
            logger.warning("[video_processor] ERROR: ASS de 0 bytes — el clip saldrá SIN subtítulos: %s", ass_file)
        return f"ass={ass_escaped}"
    logger.warning("[video_processor] ERROR: ass_file indicado pero NO existe: %s — se quema SIN subtítulos", ass_file)
    return None


def _construir_filtergraph(ass_file: str | None) -> list:
    """Filtergraph de crop + scale + setsar + ass opcional."""
    filters = []

    # 1. Crop-primero (evita frames gigantes de 3413px)
    filters.append("crop='if(gt(iw/ih,9/16),ih*9/16,iw)':'if(gt(iw/ih,9/16),ih,iw*16/9)'")

    # 2. Scale a 1080x1920
    filters.append("scale=1080:1920")
    filters.append("setsar=1")

    # 3. Quemar subtítulos ASS si existe
    if ass_file:
        filtro = _filtro_ass(ass_file)
        if filtro is not None:
            filters.append(filtro)

    return filters


def _log_filtergraph(vf: str) -> None:
    """Avisa si el filtergraph final no incluye el filtro de subtítulos."""
    if "ass=" not in vf:
        logger.warning("[video_processor] ERROR: Filtergraph SIN filtro ass — el clip saldrá SIN subtítulos")
    else:
        logger.info("[video_processor] Filtergraph incluye ass: OK")


def _verificar_salida_reframe(result, output_video: str) -> bool:
    """Valida el returncode y la existencia del output del reframe."""
    if result.returncode != 0:
        logger.error("[video_processor] ffmpeg FAILED rc=%s", result.returncode)
        logger.error("[video_processor] stderr: %s", result.stderr[-1000:])
        return False

    if not os.path.exists(output_video) or os.path.getsize(output_video) == 0:
        logger.error("[video_processor] Output no generado o vacío")
        return False

    logger.info("[video_processor] ✓ Vertical generado: %s (%s bytes)", output_video, os.path.getsize(output_video))
    return True


def _stderr_tail(result) -> str:
    """Cola del stderr de ffmpeg para logging (hasta 3000 chars)."""
    return (result.stderr or "")[-3000:]


def _ejecutar_ffmpeg_reframe(command: list, timeout_seconds: int, output_video: str) -> bool:
    """Corre ffmpeg y loguea stderr completo; valida el output generado."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )

        # stderr SIEMPRE se loguea (no solo al fallar) para ver warnings de libass/ffmpeg
        stderr_tail = _stderr_tail(result)
        logger.info("[video_processor] ffmpeg stderr (rc=%s):\n%s", result.returncode, stderr_tail if stderr_tail.strip() else "<vacío>")

        return _verificar_salida_reframe(result, output_video)

    except subprocess.TimeoutExpired:
        logger.error("[video_processor] Timeout después de %ss", timeout_seconds)
        return False
    except Exception as e:
        logger.error("[video_processor] Excepción: %s", e)
        return False


def _comando_reframe(input_video: str, output_video: str, vf: str, codec_args: list) -> list:
    """Comando ffmpeg completo del reframe 9:16 con los codec args dados."""
    return [
        FFMPEG_BIN,
        "-y",
        "-i", input_video,
        "-vf", vf,
        *codec_args,
        "-threads", "1",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_video
    ]


def reframe_and_burn_subtitles(
    input_video: str,
    output_video: str,
    ass_file: str | None = None,
    hook_text: str | None = None,
    clip_start: float = 0.0,
    timeout_seconds: int = 300
) -> bool:
    """Reframe vertical 9:16 + quema subtítulos ASS + hook opcional.
    
    Args:
        input_video: Ruta del video horizontal de entrada
        output_video: Ruta del video vertical de salida
        ass_file: Ruta del archivo ASS (opcional) — ya incluye el hook como evento estilo "Hook"
        hook_text: Sin efecto en este filtro (se integra en el ASS); se mantiene por compatibilidad de firma
        clip_start: Inicio del clip en segundos (para hook timing)
        timeout_seconds: Timeout de ffmpeg
    
    Returns:
        True si éxito, False si falla
    """
    # Construir filtergraph
    filters = _construir_filtergraph(ass_file)

    # NOTA: sin drawtext — el ffmpeg estático de RunPod no tiene libfreetype
    # ("No such filter: 'drawtext'", rc=8). El hook se QUEMA VÍA ASS:
    # generate_ass_from_segments lo agrega como primer evento con estilo "Hook"
    # (arriba, 0-3s). Este filtergraph solo usa crop+scale+setsar+ass.

    vf = ",".join(filters)

    # NVENC con fallback de runtime: si el encode GPU falla (driver sin
    # libnvidia-encode, driver viejo), se reintenta UNA vez con libx264.
    codec_args = _args_codec_video("20")
    command = _comando_reframe(input_video, output_video, vf, codec_args)

    logger.info("[video_processor] Reframe vertical + subs + hook...")
    logger.info("[video_processor] Filtros: %s...", vf[:200])
    logger.info("[video_processor] Comando ffmpeg COMPLETO: %s", " ".join(command))
    _log_filtergraph(vf)

    exito = _ejecutar_ffmpeg_reframe(command, timeout_seconds, output_video)
    if not exito and "h264_nvenc" in codec_args:
        logger.warning("[video_processor] Encode NVENC falló — retry con libx264 (CPU)")
        fallback = _comando_reframe(input_video, output_video, vf, _args_codec_video_libx264("20"))
        exito = _ejecutar_ffmpeg_reframe(fallback, timeout_seconds, output_video)
    return exito


def _args_codec_video_libx264(quality: str) -> list:
    """Args libx264 explícitos para el fallback (sin depender del probe)."""
    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", quality]


def _corte_ok(returncode: int, horizontal_clip: str) -> bool:
    """Corte exitoso: rc=0 y archivo intermedio presente."""
    return returncode == 0 and os.path.exists(horizontal_clip)


def _cortar_clip_horizontal(input_video: str, horizontal_clip: str, clip_start: float, duration: float) -> bool:
    """Corta el clip horizontal intermedio; nvenc con retry único a libx264.

    -threads 2 acota el CPU por ffmpeg para no saturar la máquina cuando el
    handler renderiza 3 clips en paralelo.
    """
    intentos = [_args_codec_video("18")]
    if "h264_nvenc" in intentos[0]:
        intentos.append(_args_codec_video_libx264("18"))
    for codec_args in intentos:
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-ss", str(clip_start),
            "-i", input_video,
            "-t", str(duration),
            *codec_args,
            "-threads", "2",
            "-c:a", "aac",
            "-movflags", "+faststart",
            horizontal_clip
        ]
        logger.info("[video_processor] Cortando clip %.1fs (+%.1fs)...", clip_start, duration)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if _corte_ok(result.returncode, horizontal_clip):
            return True
        logger.error("[video_processor] Corte FAILED (rc=%s)", result.returncode)
    return False


def _comando_teaser_bw(input_video: str, clip_start: float, teaser_path: str) -> list:
    """ffmpeg: 5s del inicio del clip re-reproducidos en B&W con zoom 1.08 (9:16)."""
    return [
        FFMPEG_BIN, "-y",
        "-ss", f"{clip_start:.3f}", "-i", input_video,
        "-t", f"{TEASER_DURACION:.3f}",
        "-vf", FILTRO_TEASER_BW,
        *_args_codec_video("20"),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        teaser_path,
    ]


def _stderr_de(result) -> str:
    """Cola del stderr de ffmpeg para logging (hasta 800 chars)."""
    return (result.stderr or "")[-800:]


def _salida_ffmpeg_ok(result, path: str) -> bool:
    """ffmpeg exitoso: rc=0 y archivo generado no vacío."""
    return result.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0


def _generar_teaser_bw(input_video: str, clip_start: float, teaser_path: str) -> bool:
    """Genera el teaser vertical B&W de 5s; False si ffmpeg falla o no produce archivo."""
    result = subprocess.run(
        _comando_teaser_bw(input_video, clip_start, teaser_path),
        capture_output=True, text=True, timeout=300,
    )
    if not _salida_ffmpeg_ok(result, teaser_path):
        logger.error("[video_processor] Teaser B&W FAILED (rc=%s): %s", result.returncode, _stderr_de(result))
        return False
    return True


def _filtro_teaser_cuerpo() -> str:
    """filter_complex del ensamble teaser(B&W)+cuerpo con SFX whoosh en la transición."""
    fade = 0.1
    delay_ms = int(max(0.0, TEASER_DURACION - SFX_DURACION + 0.25) * 1000)
    return (
        f"[0:v]fade=t=out:st={TEASER_DURACION - fade:.3f}:d={fade:.3f},setsar=1[v0];"
        f"[1:v]fade=t=in:st=0:d={fade:.3f},setsar=1[v1];"
        f"[0:a]afade=t=out:st={TEASER_DURACION - fade:.3f}:d={fade:.3f}[a0];"
        f"[1:a]afade=t=in:st=0:d={fade:.3f}[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a];"
        f"[2:a]volume={VOLUMEN_SFX},afade=t=in:st=0:d=0.08,"
        f"afade=t=out:st={SFX_DURACION - 0.25:.3f}:d=0.25,adelay={delay_ms}|all=1[sfx];"
        "[v][a][sfx]amix=inputs=2:duration=first:normalize=0[aout]"
    )


def _ensamblar_teaser_cuerpo(teaser_path: str, body_path: str, output_path: str) -> bool:
    """Ensambla teaser(B&W 5s)+cuerpo a color con SFX whoosh (espejo de ffmpeg_service)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", teaser_path, "-i", body_path,
        "-f", "lavfi", "-t", f"{SFX_DURACION:.3f}", "-i", SFX_LAVFI,
        "-filter_complex", _filtro_teaser_cuerpo(),
        "-map", "[v]", "-map", "[aout]",
        *_args_codec_video("20"),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if not _salida_ffmpeg_ok(result, output_path):
        logger.error("[video_processor] Ensamble teaser+cuerpo FAILED (rc=%s): %s", result.returncode, _stderr_de(result))
        return False
    return True


def _componer_teaser_worker(input_video: str, clip_start: float, body_path: str, output_video: str) -> bool:
    """Teaser B&W 5s + ensamble; fallback: devolver solo el cuerpo a color si falla."""
    with tempfile.TemporaryDirectory(prefix="teaser_worker_") as tdir:
        teaser_path = os.path.join(tdir, "teaser.mp4")
        if _generar_teaser_bw(input_video, clip_start, teaser_path):
            if _ensamblar_teaser_cuerpo(teaser_path, body_path, output_video):
                return True
        logger.warning("[video_processor] Teaser/ensamble falló — devolviendo solo el cuerpo a color")
        shutil.copyfile(body_path, output_video)
        return os.path.exists(output_video) and os.path.getsize(output_video) > 0


def process_clip_vertical(
    input_video: str,
    output_video: str,
    segments: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    hook_text: str | None = None
) -> bool:
    """Procesa un clip completo: corta + reframe vertical + quema subs + hook.
    
    Args:
        input_video: Video fuente completo
        output_video: Output final vertical
        segments: Segmentos de transcripción
        clip_start: Inicio del clip en segundos
        clip_end: Fin del clip en segundos
        hook_text: Texto del hook (opcional)
    
    Returns:
        True si éxito, False si falla
    """
    # 1. Cortar clip horizontal temporal
    with tempfile.TemporaryDirectory() as tmpdir:
        horizontal_clip = os.path.join(tmpdir, "horizontal.mp4")
        ass_file = os.path.join(tmpdir, "subtitles.ass")

        # Cortar con ffmpeg (codec seleccionado + retry; sin re-encode CPU si hay GPU)
        duration = clip_end - clip_start
        if not _cortar_clip_horizontal(input_video, horizontal_clip, clip_start, duration):
            return False

        # 2. ASS del cuerpo: subtítulos SOLO desde el cuerpo a color (issue #116).
        # hook_text=None: el teaser es video B&W re-reproducido; el evento
        # estilo Hook del ASS viejo (0-3s) queda solo para compatibilidad.
        generate_ass_from_segments(segments, clip_start, clip_end, ass_file, hook_text=None)

        # 3. Cuerpo vertical con subtítulos
        body_path = os.path.join(tmpdir, "cuerpo.mp4")
        if not reframe_and_burn_subtitles(
            horizontal_clip,
            body_path,
            ass_file=ass_file,
            hook_text=None,
            clip_start=clip_start
        ):
            return False

        # 4. Teaser B&W 5s + ensamble (unificación worker/backend, issue #116)
        return _componer_teaser_worker(input_video, clip_start, body_path, output_video)
