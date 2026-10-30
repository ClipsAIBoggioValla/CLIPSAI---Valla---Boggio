"""Procesamiento de clips verticales 9:16 con subtítulos y hook."""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any


def generate_ass_from_segments(
    segments: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    output_path: str,
    title: str = "clipsai"
) -> str:
    """Genera archivo ASS desde segmentos de transcripción para un clip específico.
    
    Args:
        segments: Lista de segmentos con start, end, text
        clip_start: Inicio del clip en segundos
        clip_end: Fin del clip en segundos
        output_path: Ruta donde guardar el archivo ASS
        title: Título del video
    
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

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
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
        ass_file: Ruta del archivo ASS (opcional)
        hook_text: Texto del hook para mostrar en primeros 3s (opcional)
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
    if ass_file and os.path.exists(ass_file):
        # Escapar path para ffmpeg (backslashes y comillas)
        ass_escaped = ass_file.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        filters.append(f"ass={ass_escaped}")
    
    # 4. Hook text en primeros 3 segundos (opcional)
    if hook_text:
        # Escapar texto para drawtext
        hook_escaped = hook_text.replace("'", "").replace('"', '').replace(":", " -")
        hook_escaped = hook_escaped.upper()[:100]
        filters.append(
            f"drawtext=text='{hook_escaped}'"
            f":fontsize=60:fontcolor=white:borderw=3:bordercolor=black"
            f":x=(w-text_w)/2:y=h*0.75"
            f":enable='between(t,0,3)'"
        )
    
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
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        
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
        
        # 2. Generar ASS
        generate_ass_from_segments(segments, clip_start, clip_end, ass_file)
        
        # 3. Reframe vertical + quemar subs + hook
        return reframe_and_burn_subtitles(
            horizontal_clip,
            output_video,
            ass_file=ass_file,
            hook_text=hook_text,
            clip_start=clip_start
        )
