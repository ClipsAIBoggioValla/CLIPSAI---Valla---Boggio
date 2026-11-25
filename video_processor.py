"""Procesamiento de clips verticales 9:16 con subtítulos y hook."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
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

# Zoom dinámico por picos RMS (issue #117): zoompan con `it`, fps fijo.
ZOOM_MAX_BODY = 1.12
ZOOM_RAMPA = 0.2               # 200ms de subida/bajada por pico
ZOOM_TOP_K = 10                # máx. picos por clip (expresión acotada)
ZOOM_FPS = 30                  # fps fijo: cero desfasaje A/V con nvenc

# ---- Hook Teaser unificado con backend (issue #116) --------------------------
TEASER_DURACION = 5.0          # teaser de video de 5s (mismo estándar que ffmpeg_service)
ZOOM_TEASER = 1.08             # zoom leve sobre la ventana del hook
VOLUMEN_SFX = 0.13             # whoosh ≤ -18 dB respecto al diálogo
SFX_DURACION = 0.9
SFX_LAVFI = "anoisesrc=color=pink:seed=20261122:amplitude=0.5"

# Teaser vertical: crop 9:16 → 1080x1920 → B&W → zoom 1.08 (crop al tamaño final).
FILTRO_TEASER_BW = (
    "crop=ih*9/16:ih,scale=1080:1920,eq=saturation=0,"
    "scale=trunc(1080*1.08/2)*2:trunc(1920*1.08/2)*2,crop=1080:1920,setsar=1"
)

# SFX por mood (issue #116): preset lavfi de fallback si /app/sfx/{mood}.wav
# no existe en la imagen. El mix aplica volume=0.13 (<= -18 dB) + adelay.
SFX_PRESETS_LAVFI = {
    "tension": "anoisesrc=color=brown:seed=117:r=48000:a=0.5,lowpass=f=600",
    "impact": "sine=f=55:r=48000",
    "transition": "anoisesrc=color=pink:seed=116:r=48000:a=0.6,lowpass=f=1200",
}
SFX_DIR = "/app/sfx"
MOOD_DEFAULT = "transition"
FACE_SAMPLE_SECONDS = 0.5
FACE_MAX_SAMPLES = 30
FACE_SMOOTH_ALPHA = 0.35
FACE_DEAD_ZONE = 0.015

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
        "text": txt,
        "emoji": s.get("emoji"),  # issue #117: emoji contextual (None si no hay)
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


def _texto_escapado_ass(texto: str) -> str:
    """Texto en mayúsculas con escape de ASS/ffmpeg."""
    text = str(texto).upper().replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return " ".join(text.split())


def _texto_con_emoji(texto: str, emoji: str | None) -> str:
    """Texto con override inline de Noto Color Emoji (issue #117); sin emoji = texto plano."""
    escapado = _texto_escapado_ass(texto)
    seguro = _emoji_seguro(emoji)
    if not seguro:
        return escapado
    return f"{{\\fnNoto Color Emoji}}{seguro}{{\\fnDejaVu Sans}} {escapado}"


def _emoji_seguro(emoji: str | None) -> str:
    """Emoji saneado para un override ASS; '' si es vacío, 'none' o inseguro."""
    limpio = str(emoji).strip()[:12]
    if any((not limpio, limpio.lower() == "none", not limpio.isprintable())):
        return ""
    return limpio.replace("{", "").replace("}", "").replace("\\", "")


def _evento_dialogue_ass(seg: dict) -> str:
    """Evento Dialogue de un segmento (escape ffmpeg + uppercase + emoji opcional)."""
    start_h = int(seg["start"] // 3600)
    start_m = int((seg["start"] % 3600) // 60)
    start_s = seg["start"] % 60
    end_h = int(seg["end"] // 3600)
    end_m = int((seg["end"] % 3600) // 60)
    end_s = seg["end"] % 60

    text = _texto_con_emoji(seg.get("text", ""), seg.get("emoji"))

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


def _construir_filtergraph(
    ass_file: str | None, picos_zoom: List[float] | None = None,
    trayectoria: list[tuple[float, float]] | None = None,
) -> list:
    """Filtergraph de crop + scale + zoompan (picos RMS) + setsar + ass opcional."""
    filters = []

    # 1. Crop-primero (evita frames gigantes de 3413px)
    filters.append(_filtro_crop_tracking(trayectoria) or "crop='if(gt(iw/ih,9/16),ih*9/16,iw)':'if(gt(iw/ih,9/16),ih,iw*16/9)'")

    # 2. Scale a 1080x1920
    filters.append("scale=1080:1920")

    # 2b. Zoom dinámico por picos RMS (issue #117): con `it` (tiempo de entrada
    # del zoompan) y fps=30 explícito para cero desfasaje A/V con nvenc.
    filtro_zoom = _filtro_zoompan(picos_zoom)
    if filtro_zoom:
        filters.append(filtro_zoom)

    filters.append("setsar=1")

    # 3. Quemar subtítulos ASS si existe
    if ass_file:
        filtro = _filtro_ass(ass_file)
        if filtro is not None:
            filters.append(filtro)

    return filters


def _detectar_trayectoria_rostros(video_path: str, panel: str | None = None) -> list[tuple[float, float]]:
    """Detecta centros faciales en keyframes bajos; [] activa el crop centrado."""
    try:
        import cv2
        import mediapipe as mp
        captura = cv2.VideoCapture(video_path)
        if not captura.isOpened():
            return []
        detector = mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)
        puntos = _leer_keyframes_rostro(captura, detector, cv2, panel)
        captura.release()
        return _suavizar_trayectoria(puntos)
    except Exception as exc:
        logger.info("[face_tracking] detección no disponible; crop centrado: %s", exc)
        return []


def _trayectorias_layout(video_path: str, layout: str) -> tuple[list, list, list]:
    """Ejecuta detección del single o de cada panel y devuelve trayectorias."""
    if layout == "single_9_16":
        return _detectar_trayectoria_rostros(video_path), [], []
    if layout == "podcast_split":
        return [], _detectar_trayectoria_rostros(video_path, "left"), _detectar_trayectoria_rostros(video_path, "right")
    return [], [], []


def _leer_keyframes_rostro(captura, detector, cv2, panel: str | None) -> list[tuple[float, float]]:
    """Lee hasta 30 keyframes repartidos en el clip (objetivo 2 fps)."""
    fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    duracion = frames / fps
    cuenta = min(int(duracion / FACE_SAMPLE_SECONDS) + 1, FACE_MAX_SAMPLES)
    indices = [round(i * (frames - 1) / max(cuenta - 1, 1)) for i in range(cuenta)]
    return [p for i in indices if (p := _detectar_frame(captura, detector, cv2, i, fps, panel))]


def _detectar_frame(captura, detector, cv2, frame_idx: int, fps: float, panel: str | None):
    """Devuelve el centro facial normalizado del frame, si lo hay."""
    captura.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = captura.read()
    if not ok:
        return None
    mitad = frame.shape[1] // 2
    frame = frame[:, :mitad] if panel == "left" else frame[:, mitad:] if panel == "right" else frame
    frame = cv2.resize(frame, (320, max(1, int(frame.shape[0] * 320 / frame.shape[1]))))
    resultado = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    detecciones = resultado.detections or []
    if not detecciones:
        return None
    box = max(detecciones, key=lambda d: d.location_data.relative_bounding_box.width)
    bbox = box.location_data.relative_bounding_box
    eje = bbox.ymin + bbox.height / 2 if panel else bbox.xmin + bbox.width / 2
    return (frame_idx / fps, eje)


def _suavizar_trayectoria(puntos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """EMA con dead-zone para bajar el jitter entre keyframes detectados."""
    salida = []
    for tiempo, x in sorted(puntos):
        if not salida:
            salida.append((tiempo, x))
            continue
        anterior = salida[-1][1]
        suavizado = anterior + FACE_SMOOTH_ALPHA * (x - anterior) if abs(x - anterior) > FACE_DEAD_ZONE else anterior
        salida.append((tiempo, suavizado))
    return salida


def _expresion_trayectoria(puntos: list[tuple[float, float]], variable: str = "t") -> str:
    """Genera expresión FFmpeg lineal por tramos, con valores acotados [0,1]."""
    expr = f"min(max({puntos[-1][1]:.5f},0),1)"
    for (t0, x0), (t1, x1) in reversed(list(zip(puntos, puntos[1:]))):
        pendiente = (x1 - x0) / max(t1 - t0, 0.001)
        tramo = f"min(max({x0:.5f}+({variable}-{t0:.3f})*{pendiente:.5f},0),1)"
        expr = f"if(lt({variable},{t1:.3f}),{tramo},{expr})"
    return expr


def _filtro_crop_tracking(trayectoria: list[tuple[float, float]] | None) -> str:
    """Crop 9:16 con centro X interpolado; cadena vacía si no hay detección."""
    if not trayectoria:
        return ""
    centro = _expresion_trayectoria(trayectoria)
    x = f"if(gt(iw/ih,9/16),min(max(({centro})*iw-ih*9/32,0),iw-ih*9/16),0)"
    return f"crop='if(gt(iw/ih,9/16),ih*9/16,iw)':'if(gt(iw/ih,9/16),ih,iw*16/9)':'{x}':0:eval=frame"


def _log_tracking_overhead(deteccion: float, render: float) -> float:
    """Registra el porcentaje real de detección respecto al encode del clip."""
    porcentaje = 100 * deteccion / max(render, 0.001)
    logger.info("[face_tracking] deteccion=%.3fs render=%.3fs overhead=%.2f%%", deteccion, render, porcentaje)
    return porcentaje


def _expresion_activo(ventanas: list[dict], panel: str) -> str:
    """Expresión temporal booleana para el panel activo del split."""
    intervalos = [(float(v["start"]), float(v["end"])) for v in ventanas if v.get("panel") == panel]
    expr = "0"
    for inicio, fin in reversed(intervalos):
        expr = f"if(between(t,{inicio:.3f},{fin:.3f}),1,{expr})"
    return expr


def _eventos_hablante(rostro_izq: list, rostro_der: list, rms_ventanas: list[dict] | None) -> list[dict]:
    """Cruza RMS estéreo con rostros de ambos paneles; cualquier fallo da neutro."""
    try:
        from audio_analyzer import cruzar_rostros_rms
        return cruzar_rostros_rms({"left": rostro_izq, "right": rostro_der}, rms_ventanas or [])
    except Exception:
        return []


def _filtro_podcast_split(
    rostro_izq: list[tuple[float, float]] | None,
    rostro_der: list[tuple[float, float]] | None,
    rms_ventanas: list[dict] | None = None,
    ass_file: str | None = None,
) -> str:
    """Filter_complex de dos paneles; center crop/highlight neutro como fallback."""
    if not rostro_izq or not rostro_der:
        logger.info("[face_tracking] podcast_split sin dos rostros; usando paneles centrados")
    eventos = _eventos_hablante(rostro_izq or [], rostro_der or [], rms_ventanas)
    y_izq = _y_crop_panel(rostro_izq)
    y_der = _y_crop_panel(rostro_der)
    brillo_izq = f"0.12*({_expresion_activo(eventos, 'left')})"
    brillo_der = f"0.12*({_expresion_activo(eventos, 'right')})"
    filtros = (
        f"[0:v]split=2[a][b];[a]crop=iw/2:iw*4/9:0:'{y_izq}',scale=1080:960,"
        f"eq=brightness='{brillo_izq}',setsar=1[va];"
        f"[b]crop=iw/2:iw*4/9:iw/2:'{y_der}',scale=1080:960,"
        f"eq=brightness='{brillo_der}',setsar=1[vb];[va][vb]vstack=inputs=2,setsar=1"
    )
    ass_filter = _filtro_ass(ass_file) if ass_file else None
    return filtros + (f",{ass_filter}" if ass_filter else "") + "[v]"


def _filtro_gameplay_split(ass_file: str | None = None) -> str:
    """Apila cámara (tercio superior) y juego (dos tercios inferiores)."""
    filtros = (
        "[0:v]split=2[cam][game];"
        "[cam]crop=iw/2:ih:0:0,scale=1080:640:force_original_aspect_ratio=increase,"
        "crop=1080:640,setsar=1[vcam];"
        "[game]crop=iw/2:ih:iw/2:0,scale=1080:1280:force_original_aspect_ratio=increase,"
        "crop=1080:1280,setsar=1[vgame];"
        "[vcam][vgame]vstack=inputs=2,setsar=1"
    )
    ass_filter = _filtro_ass(ass_file) if ass_file else None
    return filtros + (f",{ass_filter}" if ass_filter else "") + "[v]"


def _y_crop_panel(trayectoria: list[tuple[float, float]] | None) -> str:
    """Centro vertical interpolado para el crop de cada panel, o centro fijo."""
    centro = _expresion_trayectoria(trayectoria) if trayectoria else "0.5"
    return f"min(max(({centro})*ih-iw*2/9,0),ih-iw*4/9)"


def _ventana_pico(t_pico: float, rampa: float = ZOOM_RAMPA) -> str:
    """Término de zoom para un pico: sube 200ms, mantiene ~200ms, baja 200ms."""
    return (
        f"clip((it-{t_pico:.3f})/{rampa:.3f},0,1)"
        f"*clip(({t_pico + 2 * rampa:.3f}-it)/{rampa:.3f},0,1)"
    )


def _filtro_zoompan(picos: List[float] | None, fps: int = ZOOM_FPS, zoom_max: float = ZOOM_MAX_BODY) -> str:
    """zoompan guiado por picos RMS (issue #117): 1.0 -> 1.12 -> 1.0.

    Usa `it` (input time de zoompan; `t` no existe en vf_zoompan) y fps
    explícito con d=1 para que la duración nunca se altere respecto al audio.
    Sin picos devuelve "" -> filtergraph estático (fallback CA-4).
    """
    if not picos:
        return ""
    picos_acotados = sorted(picos)[:ZOOM_TOP_K]
    terminos = ",".join(_ventana_pico(p) for p in picos_acotados)
    return (
        f"fps={fps},zoompan=z='1+{(zoom_max - 1):.2f}*max({terminos},0)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps={fps}"
    )


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


def _comando_reframe(
    input_video: str, output_video: str, vf: str, codec_args: list,
    filter_complex: bool = False,
) -> list:
    """Comando ffmpeg del reframe 9:16 con filtergraph simple o split complejo."""
    comando = [
        FFMPEG_BIN,
        "-y",
        "-i", input_video,
        "-filter_complex" if filter_complex else "-vf", vf,
    ]
    if filter_complex:
        comando.extend(["-map", "[v]", "-map", "0:a?"])
    comando.extend([
        *codec_args,
        "-threads", "1",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_video
    ])
    return comando


def reframe_and_burn_subtitles(
    input_video: str,
    output_video: str,
    ass_file: str | None = None,
    hook_text: str | None = None,
    clip_start: float = 0.0,
    timeout_seconds: int = 300,
    picos_zoom: List[float] | None = None,
    trayectoria: list[tuple[float, float]] | None = None,
    trayectoria_izq: list[tuple[float, float]] | None = None,
    trayectoria_der: list[tuple[float, float]] | None = None,
    rms_ventanas: list[dict] | None = None,
    deteccion_seconds: float = 0.0,
    layout: str = "single_9_16",
) -> bool:
    """Reframe vertical 9:16 + quema subtítulos ASS + hook opcional.
    
    Args:
        input_video: Ruta del video horizontal de entrada
        output_video: Ruta del video vertical de salida
        ass_file: Ruta del archivo ASS (opcional) — ya incluye el hook como evento estilo "Hook"
        hook_text: Sin efecto en este filtro (se integra en el ASS); se mantiene por compatibilidad de firma
        clip_start: Inicio del clip en segundos (para hook timing)
        timeout_seconds: Timeout de ffmpeg
        picos_zoom: Picos RMS relativos al cuerpo (zoompan 1.0->1.12, issue #117)
    
    Returns:
        True si éxito, False si falla
    """
    # Construir filtergraph
    inicio_deteccion = time.perf_counter()
    if layout == "single_9_16" and trayectoria is None:
        trayectoria = _detectar_trayectoria_rostros(input_video)
        deteccion_seconds += time.perf_counter() - inicio_deteccion
    filter_complex = layout in ("podcast_split", "gameplay_split")
    if layout == "podcast_split":
        vf = _filtro_podcast_split(trayectoria_izq, trayectoria_der, rms_ventanas, ass_file)
    elif layout == "gameplay_split":
        vf = _filtro_gameplay_split(ass_file)
    else:
        filters = _construir_filtergraph(ass_file, picos_zoom=picos_zoom, trayectoria=trayectoria)
        vf = ",".join(filters)

    # NOTA: sin drawtext — el ffmpeg estático de RunPod no tiene libfreetype
    # ("No such filter: 'drawtext'", rc=8). El hook se QUEMA VÍA ASS:
    # generate_ass_from_segments lo agrega como primer evento con estilo "Hook"
    # (arriba, 0-3s). Este filtergraph usa crop+scale+zoompan+setsar+ass.

    # NVENC con fallback de runtime: si el encode GPU falla (driver sin
    # libnvidia-encode, driver viejo), se reintenta UNA vez con libx264.
    codec_args = _args_codec_video("20")
    command = _comando_reframe(input_video, output_video, vf, codec_args, filter_complex)

    logger.info("[video_processor] Reframe vertical + subs + hook...")
    logger.info("[video_processor] Filtros: %s...", vf[:200])
    logger.info("[video_processor] Comando ffmpeg COMPLETO: %s", " ".join(command))
    _log_filtergraph(vf)

    inicio_render = time.perf_counter()
    exito = _ejecutar_ffmpeg_reframe(command, timeout_seconds, output_video)
    _log_tracking_overhead(deteccion_seconds, time.perf_counter() - inicio_render)
    if not exito and "h264_nvenc" in codec_args:
        logger.warning("[video_processor] Encode NVENC falló — retry con libx264 (CPU)")
        fallback = _comando_reframe(input_video, output_video, vf, _args_codec_video_libx264("20"), filter_complex)
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


def _mood_valido(sfx_mood: str | None) -> str:
    """mood con whitelist; default 'transition' si falta o es inválido."""
    mood = str(sfx_mood or "").strip().lower()
    return mood if mood in SFX_PRESETS_LAVFI or mood == "none" else MOOD_DEFAULT


def _input_sfx(sfx_mood: str) -> list | None:
    """Args del input SFX según mood. None si mood='none' (sin SFX).

    Prefiere /app/sfx/{mood}.wav (generado en build); fallback al preset
    lavfi del mood; 'none' omite el SFX por completo.
    """
    if sfx_mood == "none":
        return None
    wav = os.path.join(SFX_DIR, f"{sfx_mood}.wav")
    if os.path.isfile(wav):
        return ["-i", wav]
    preset = SFX_PRESETS_LAVFI.get(sfx_mood, SFX_PRESETS_LAVFI[MOOD_DEFAULT])
    return ["-f", "lavfi", "-t", f"{SFX_DURACION:.3f}", "-i", preset]


def _filtro_teaser_cuerpo(con_sfx: bool) -> str:
    """filter_complex del ensamble teaser(B&W)+cuerpo; SFX whoosh solo si con_sfx."""
    fade = 0.1
    delay_ms = int(max(0.0, TEASER_DURACION - SFX_DURACION + 0.25) * 1000)
    base = (
        f"[0:v]fade=t=out:st={TEASER_DURACION - fade:.3f}:d={fade:.3f},setsar=1[v0];"
        f"[1:v]fade=t=in:st=0:d={fade:.3f},setsar=1[v1];"
        f"[0:a]afade=t=out:st={TEASER_DURACION - fade:.3f}:d={fade:.3f}[a0];"
        f"[1:a]afade=t=in:st=0:d={fade:.3f}[a1];"
    )
    if not con_sfx:
        return base + "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    return (
        base
        + "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a];"
        + f"[2:a]volume={VOLUMEN_SFX},afade=t=in:st=0:d=0.08,"
        + f"afade=t=out:st={SFX_DURACION - 0.25:.3f}:d=0.25,adelay={delay_ms}|all=1[sfx];"
        + "[v][a][sfx]amix=inputs=2:duration=first:normalize=0[aout]"
    )


def _maps_teaser_cuerpo(con_sfx: bool) -> list:
    """Maps del ensamble: [aout] con SFX mezclado, [a] sin SFX."""
    return ["-map", "[v]", "-map", "[aout]" if con_sfx else "[a]"]


def _ensamblar_teaser_cuerpo(
    teaser_path: str, body_path: str, output_path: str, sfx_mood: str = MOOD_DEFAULT
) -> bool:
    """Ensambla teaser(B&W 5s)+cuerpo a color con SFX del mood (espejo de ffmpeg_service)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sfx_input = _input_sfx(sfx_mood)
    con_sfx = sfx_input is not None
    cmd = [FFMPEG_BIN, "-y", "-i", teaser_path, "-i", body_path]
    if sfx_input:
        cmd.extend(sfx_input)
    cmd.extend([
        "-filter_complex", _filtro_teaser_cuerpo(con_sfx),
        *_maps_teaser_cuerpo(con_sfx),
        *_args_codec_video("20"),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if not _salida_ffmpeg_ok(result, output_path):
        logger.error("[video_processor] Ensamble teaser+cuerpo FAILED (rc=%s): %s", result.returncode, _stderr_de(result))
        return False
    return True


def _copiar_cuerpo_como_fallback(body_path: str, output_video: str) -> bool:
    """Fallback #116: el cuerpo a color es el output final (sin teaser)."""
    shutil.copyfile(body_path, output_video)
    return os.path.exists(output_video) and os.path.getsize(output_video) > 0


def _componer_teaser_worker(
    input_video: str, clip_start: float, body_path: str, output_video: str,
    sfx_mood: str = MOOD_DEFAULT, enable_hook_teaser: bool = True,
) -> bool:
    """Teaser B&W 5s + ensamble; fallback: devolver solo el cuerpo a color si falla."""
    if not enable_hook_teaser:
        logger.info("[video_processor] enable_hook_teaser=False — salida: solo cuerpo a color")
        return _copiar_cuerpo_como_fallback(body_path, output_video)
    with tempfile.TemporaryDirectory(prefix="teaser_worker_") as tdir:
        teaser_path = os.path.join(tdir, "teaser.mp4")
        if _generar_teaser_bw(input_video, clip_start, teaser_path):
            if _ensamblar_teaser_cuerpo(teaser_path, body_path, output_video, sfx_mood):
                return True
        logger.warning("[video_processor] Teaser/ensamble falló — devolviendo solo el cuerpo a color")
        return _copiar_cuerpo_como_fallback(body_path, output_video)


def process_clip_vertical(
    input_video: str,
    output_video: str,
    segments: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    hook_text: str | None = None,
    sfx_mood: str = MOOD_DEFAULT,
    enable_hook_teaser: bool = True,
    picos_zoom: List[float] | None = None,
    layout: str = "single_9_16",
    rms_ventanas: list[dict] | None = None,
) -> bool:
    """Procesa un clip completo: corta + reframe vertical + quema subs + hook.
    
    Args:
        input_video: Video fuente completo
        output_video: Output final vertical
        segments: Segmentos de transcripción
        clip_start: Inicio del clip en segundos
        clip_end: Fin del clip en segundos
        hook_text: Texto del hook (opcional)
        sfx_mood: Tono del SFX del teaser ('tension'|'impact'|'transition'|'none')
        enable_hook_teaser: False = cuerpo directo sin teaser ni shift (issue #116)
        picos_zoom: Picos RMS del cuerpo (tiempo relativo al cuerpo) para zoompan (issue #117)
    
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

        deteccion_inicio = time.perf_counter()
        trayectoria, trayectoria_izq, trayectoria_der = _trayectorias_layout(horizontal_clip, layout)
        deteccion_seconds = time.perf_counter() - deteccion_inicio

        # 2. ASS del cuerpo: subtítulos SOLO desde el cuerpo a color (issue #116).
        # hook_text=None: el teaser es video B&W re-reproducido; el evento
        # estilo Hook del ASS viejo (0-3s) queda solo para compatibilidad.
        generate_ass_from_segments(segments, clip_start, clip_end, ass_file, hook_text=None)

        # 3. Cuerpo vertical con subtítulos + zoompan por picos RMS (issue #117)
        body_path = os.path.join(tmpdir, "cuerpo.mp4")
        if not reframe_and_burn_subtitles(
            horizontal_clip,
            body_path,
            ass_file=ass_file,
            hook_text=None,
            clip_start=clip_start,
            picos_zoom=picos_zoom,
            trayectoria=trayectoria,
            trayectoria_izq=trayectoria_izq,
            trayectoria_der=trayectoria_der,
            rms_ventanas=rms_ventanas,
            deteccion_seconds=deteccion_seconds,
            layout=layout,
        ):
            return False

        # 4. Teaser B&W 5s + ensamble (unificación worker/backend, issue #116)
        return _componer_teaser_worker(
            input_video, clip_start, body_path, output_video,
            sfx_mood=_mood_valido(sfx_mood), enable_hook_teaser=enable_hook_teaser,
        )
