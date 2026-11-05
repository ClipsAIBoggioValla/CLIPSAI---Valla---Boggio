"""Procesamiento de clips verticales 9:16 con subtítulos y hook."""

import logging
import os
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
    # Filtrar segmentos dentro del clip y shiftear tiempos a 0
    clipped = []
    for s in segments:
        try:
            st = float(s.get("start", 0))
            en = float(s.get("end", 0))
            txt = str(s.get("text", "")).strip()
            if not txt or en <= st:
                continue
            if en < clip_start or st > clip_end:
                continue
            cs = max(st, clip_start)
            ce = min(en, clip_end)
            if ce > cs:
                clipped.append({
                    "start": cs - clip_start,
                    "end": ce - clip_start,
                    "text": txt
                })
        except Exception:
            continue
    
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
Style: Default,Arial,70,&H00FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,40,40,280,1
Style: Hook,Arial,80,&H00FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,3,8,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # 1) Hook como PRIMER evento (0-3s, estilo grande arriba). drawtext no: ffmpeg
    # estático de RunPod carece de libfreetype.
    if hook_text:
        hook_clean = " ".join(str(hook_text).upper().split())
        hook_clean = hook_clean.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        hook_clean = hook_clean[:100]
        if hook_clean:
            hook_dur = min(3.0, max(0.5, clip_end - clip_start))
            eh = int(hook_dur // 3600)
            em = int((hook_dur % 3600) // 60)
            es = hook_dur % 60
            ass_content += f"Dialogue: 0,0:00:00.00,{eh}:{em:02d}:{es:05.2f},Hook,,0,0,0,,{hook_clean}\n"

    # 2) Subtítulos normales después, con su estilo Default (abajo, más chico)
    for seg in clipped:
        start_h = int(seg["start"] // 3600)
        start_m = int((seg["start"] % 3600) // 60)
        start_s = seg["start"] % 60
        end_h = int(seg["end"] // 3600)
        end_m = int((seg["end"] % 3600) // 60)
        end_s = seg["end"] % 60
        
        text = seg["text"].upper().replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        text = " ".join(text.split())
        
        ass_content += f"Dialogue: 0,{start_h}:{start_m:02d}:{start_s:05.2f},{end_h}:{end_m:02d}:{end_s:05.2f},Default,,0,0,0,,{text}\n"
    
    Path(output_path).write_text(ass_content, encoding="utf-8")

    # --- Diagnóstico ASS: validar estructura y volcar contenido (debug subs ausentes) ---
    written = Path(output_path)
    try:
        size = written.stat().st_size if written.exists() else 0
    except OSError:
        size = -1
    lines = ass_content.splitlines()
    dialogue_lines = [l for l in lines if l.startswith("Dialogue:")]
    hook_events = [l for l in dialogue_lines if ",Hook," in l]
    default_events = [l for l in dialogue_lines if ",Default," in l]
    has_script = "[Script Info]" in ass_content
    has_styles = "[V4+ Styles]" in ass_content
    has_events = "[Events]" in ass_content
    logger.info(
        "[video_processor] ASS generado: %s (%s bytes, %s líneas, %s Dialogue: hook=%s default=%s)",
        output_path, size, len(lines), len(dialogue_lines), len(hook_events), len(default_events),
    )
    if size <= 0:
        logger.warning("[video_processor] ERROR: ASS VACÍO o inexistente tras escritura: %s (size=%s)", output_path, size)
    if not (has_script and has_styles and has_events):
        logger.warning("[video_processor] ERROR: ASS sin estructura completa: ScriptInfo=%s V4Styles=%s Events=%s", has_script, has_styles, has_events)
    if not dialogue_lines:
        logger.warning("[video_processor] ERROR: ASS sin eventos Dialogue — ffmpeg quemará SIN subtítulos (segments fuera de ventana o vacío)")
    if hook_text:
        if hook_events:
            logger.info("[video_processor] OK: Hook presente como evento estilo Hook: %s", hook_events[0][:140])
        else:
            logger.warning("[video_processor] ERROR: hook_text pedido ('%s') pero NO hay evento estilo Hook en [Events]", hook_text[:60])
    logger.info("[video_processor] ---- %s | PRIMERAS 20 LINEAS ----", output_path)
    for line in lines[:20]:
        logger.info("[video_processor] ASS| %s", line)
    logger.info("[video_processor] ---- FIN ASS ----")
    return output_path


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
    filters = []
    
    # 1. Crop-primero (evita frames gigantes de 3413px)
    filters.append("crop='if(gt(iw/ih,9/16),ih*9/16,iw)':'if(gt(iw/ih,9/16),ih,iw*16/9)'")
    
    # 2. Scale a 1080x1920
    filters.append("scale=1080:1920")
    filters.append("setsar=1")
    
    # 3. Quemar subtítulos ASS si existe
    if ass_file:
        if os.path.exists(ass_file):
            ass_size = os.path.getsize(ass_file)
            # Escape ffmpeg: backslashes a /, y ':' / ',' (separadores de filtro)
            # escapados con backslash. Sin comillas alrededor del path.
            ass_escaped = (
                ass_file.replace("\\", "/").replace(":", "\\:").replace(",", "\\,").replace("'", "\\'")
            )
            filters.append(f"ass={ass_escaped}")
            logger.info("[video_processor] Filtro ASS OK: ass=%s (%s bytes)", ass_escaped, ass_size)
            if ass_size == 0:
                logger.warning("[video_processor] ERROR: ASS de 0 bytes — el clip saldrá SIN subtítulos: %s", ass_file)
        else:
            logger.warning("[video_processor] ERROR: ass_file indicado pero NO existe: %s — se quema SIN subtítulos", ass_file)
    
    # NOTA: sin drawtext — el ffmpeg estático de RunPod no tiene libfreetype
    # ("No such filter: 'drawtext'", rc=8). El hook se QUEMA VÍA ASS:
    # generate_ass_from_segments lo agrega como primer evento con estilo "Hook"
    # (arriba, 0-3s). Este filtergraph solo usa crop+scale+setsar+ass.

    vf = ",".join(filters)
    
    command = [
        "/usr/local/bin/ffmpeg",
        "-y",
        "-i", input_video,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "20",
        "-threads", "1",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_video
    ]
    
    print(f"[video_processor] Reframe vertical + subs + hook...")
    print(f"[video_processor] Filtros: {vf[:200]}...")
    logger.info("[video_processor] Comando ffmpeg COMPLETO: %s", " ".join(command))
    if "ass=" not in vf:
        logger.warning("[video_processor] ERROR: Filtergraph SIN filtro ass — el clip saldrá SIN subtítulos")
    else:
        logger.info("[video_processor] Filtergraph incluye ass: OK")
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )

        # stderr SIEMPRE se loguea (no solo al fallar) para ver warnings de libass/ffmpeg
        stderr_tail = (result.stderr or "")[-3000:]
        logger.info("[video_processor] ffmpeg stderr (rc=%s):\n%s", result.returncode, stderr_tail if stderr_tail.strip() else "<vacío>")

        if result.returncode != 0:
            print(f"[video_processor] ffmpeg FAILED rc={result.returncode}")
            print(f"[video_processor] stderr: {result.stderr[-1000:]}")
            return False
        
        if not os.path.exists(output_video) or os.path.getsize(output_video) == 0:
            print(f"[video_processor] Output no generado o vacío")
            return False
        
        print(f"[video_processor] ✓ Vertical generado: {output_video} ({os.path.getsize(output_video)} bytes)")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"[video_processor] Timeout después de {timeout_seconds}s")
        return False
    except Exception as e:
        print(f"[video_processor] Excepción: {e}")
        return False


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
        
        # Cortar con ffmpeg
        duration = clip_end - clip_start
        cut_cmd = [
            "/usr/local/bin/ffmpeg",
            "-y",
            "-ss", str(clip_start),
            "-i", input_video,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "18",
            "-c:a", "aac",
            "-movflags", "+faststart",
            horizontal_clip
        ]
        
        print(f"[video_processor] Cortando clip {clip_start:.1f}s - {clip_end:.1f}s...")
        result = subprocess.run(cut_cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0 or not os.path.exists(horizontal_clip):
            print(f"[video_processor] Corte FAILED")
            return False
        
        # 2. Generar ASS (incluye el hook como primer evento estilo Hook 0-3s)
        generate_ass_from_segments(segments, clip_start, clip_end, ass_file, hook_text=hook_text)
        
        # 3. Reframe vertical + quemar subs + hook
        return reframe_and_burn_subtitles(
            horizontal_clip,
            output_video,
            ass_file=ass_file,
            hook_text=hook_text,
            clip_start=clip_start
        )
