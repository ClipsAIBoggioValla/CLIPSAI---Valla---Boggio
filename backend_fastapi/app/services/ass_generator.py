from __future__ import annotations

import logging
from pathlib import Path
from typing import NotRequired, TypedDict

# Banda del teaser estandarizado (issue #116) — misma constante que ffmpeg_service.
HOOK_TEASER_MIN = 4.5
HOOK_TEASER_MAX = 5.5
TEASER_DURACION = 5.0

logger = logging.getLogger(__name__)


class SubtitleSegment(TypedDict):
    start: float
    end: float
    text: str
    emoji: NotRequired[str | None]  # issue #117: emoji contextual del grupo


ASS_STYLE_VERTICAL = (
    "Arial,70,&H00FFFFFF,&H00000000,&H00000000,&H80000000,"
    "1,0,0,0,100,100,0,0,1,4,2,2,40,40,280,1"
)

# Plantillas de subtítulos soportadas por RenderConfig.caption_style (Issue #121).
# El valor es la fila completa de estilo ASS (V4+ Styles).
ASS_STYLE_PRESETS = {
    "karaoke_yellow": ASS_STYLE_VERTICAL,
    "neon_green": (
        "Arial,70,&H0000FF00,&H00000000,&H00000000,&H80000000,"
        "1,0,0,0,100,100,0,0,1,4,2,2,40,40,280,1"
    ),
    "minimal_white": (
        "Arial,58,&H00FFFFFF,&H00000000,&H00000000,&H80000000,"
        "0,0,0,0,100,100,0,0,1,2,0,2,48,48,240,1"
    ),
}
CAPTION_STYLES = tuple(ASS_STYLE_PRESETS)


def ass_style_for(caption_style: str | None) -> str:
    """Fila ASS de la plantilla pedida; cae en la vertical por defecto."""
    return ASS_STYLE_PRESETS.get(caption_style or "", ASS_STYLE_VERTICAL)


ASS_HEADER_TEMPLATE = (
    "[Script Info]\n"
    "Title: {title}\n"
    "ScriptType: v4.00+\n"
    "WrapStyle: 0\n"
    "ScaledBorderAndShadow: yes\n"
    "PlayResX: 1080\n"
    "PlayResY: 1920\n"
    "YCbCr Matrix: TV.709\n"
    "\n"
    "[V4+ Styles]\n"
    "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
    "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
    "Alignment,MarginL,MarginR,MarginV,Encoding\n"
    "Style: Default,{style}\n"
    "\n"
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)


def _format_ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _sanitize_text(text: str) -> str:
    t = (text or "").strip().upper()
    if not t:
        return ""
    t = t.replace("\\", "\\\\")
    t = t.replace("{", "\\{").replace("}", "\\}")
    t = t.replace("\n", " ").replace("\r", " ")
    t = " ".join(t.split())
    return t


def _longitud_palabra(w: str, cur: list[str]) -> int:
    """Largo de la palabra más el espacio si ya hay texto acumulado."""
    return len(w) + (1 if cur else 0)


def _cortar_linea(
    lines: list[str], cur: list[str], cur_len: int, w: str, add: int, max_chars: int
) -> tuple[list[str], int]:
    """Corta la línea actual si excede el máximo. Devuelve (cur, cur_len)."""
    if cur_len + add > max_chars and cur:
        lines.append(" ".join(cur))
        return [w], len(w)
    cur.append(w)
    return cur, cur_len + add


def _lineas_de_palabras(words: list[str], max_chars: int) -> list[str]:
    """Agrupa palabras en líneas de hasta max_chars."""
    lines: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for w in words:
        add = _longitud_palabra(w, cur)
        cur, cur_len = _cortar_linea(lines, cur, cur_len, w, add, max_chars)
    if cur:
        lines.append(" ".join(cur))
    return lines


def _wrap_text(text: str, max_chars: int = 28) -> str:
    """Envuelve el texto en líneas ASS ('\\N') de hasta max_chars."""
    words = text.split()
    if not words:
        return text
    return "\\N".join(_lineas_de_palabras(words, max_chars))


def generate_ass_content(
    segments: list[SubtitleSegment],
    title: str = "clipsai",
    style: str | None = None,
    max_chars_per_line: int = 28,
    min_duration: float = 0.8,
    max_duration: float = 6.0,
) -> str:
    style_str = style or ASS_STYLE_VERTICAL
    header = ASS_HEADER_TEMPLATE.format(title=title or "clipsai", style=style_str)
    lines: list[str] = []
    for seg in segments:
        line = _segment_to_dialogue(seg, min_duration=min_duration, max_duration=max_duration, max_chars_per_line=max_chars_per_line)
        if line is not None:
            lines.append(line)
    return header + "\n".join(lines)


def _campos_segmento(seg) -> tuple[float, float, str] | None:
    """(start, end, texto) del segmento; None si no son convertibles."""
    try:
        start = float(seg.get("start", 0))
        end = float(seg.get("end", 0))
        text_raw = str(seg.get("text", "") or "")
    except Exception:
        return None
    return start, end, text_raw


def _end_seguro(start: float, end: float, min_duration: float) -> float:
    """End mínimo garantizado cuando el segmento queda invertido."""
    if end <= start:
        return start + min_duration
    return end


def _end_limitado(start: float, end: float, min_duration: float, max_duration: float) -> float:
    """Ajusta end a los límites de duración mínima y máxima."""
    dur = end - start
    if dur < min_duration:
        return start + min_duration
    if dur > max_duration:
        return start + max_duration
    return end


def _emoji_seguro(emoji: str | None) -> str:
    """Emoji saneado para un override ASS; '' si es vacío, 'none' o inseguro."""
    limpio = str(emoji).strip()[:12]
    if any((not limpio, limpio.lower() == "none", not limpio.isprintable())):
        return ""
    return limpio.replace("{", "").replace("}", "").replace("\\", "")


def _prefijo_emoji(emoji: str | None) -> str:
    """Override inline Noto Color Emoji + vuelta a DejaVu Sans (issue #117)."""
    seguro = _emoji_seguro(emoji)
    if not seguro:
        return ""
    return f"{{\\fnNoto Color Emoji}}{seguro}{{\\fnDejaVu Sans}} "


def _segment_to_dialogue(seg, *, min_duration, max_duration, max_chars_per_line):
    """Línea 'Dialogue: ...' del segmento; None si se descarta."""
    campos = _campos_segmento(seg)
    if campos is None:
        return None
    start, end, text_raw = campos
    end = _end_seguro(start, end, min_duration)
    if end - start < 0.15:
        return None
    end = _end_limitado(start, end, min_duration, max_duration)
    text = _sanitize_text(text_raw)
    if not text:
        return None
    wrapped = _wrap_text(text, max_chars=max_chars_per_line)
    emoji = _prefijo_emoji(seg.get("emoji"))
    return f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,,{emoji}{wrapped}"


def write_ass_file(
    segments: list[SubtitleSegment],
    output_path: str | Path,
    title: str = "clipsai",
    style: str | None = None,
) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    content = generate_ass_content(segments, title=title, style=style)
    out.write_text(content, encoding="utf-8")
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"No se pudo generar ASS en {out}")
    return str(out)


def segments_from_transcript_words(words: list[dict]) -> list[SubtitleSegment]:
    result: list[SubtitleSegment] = []
    for w in words:
        try:
            result.append(
                SubtitleSegment(
                    start=float(w["start"]),
                    end=float(w["end"]),
                    text=str(w["text"]),
                )
            )
        except Exception:
            continue
    return result


def generate_ass_for_clip(
    segments: list[SubtitleSegment],
    output_path: str | Path,
    clip_title: str | None = None,
) -> str:
    return write_ass_file(segments, output_path, title=clip_title or "clipsai")


def _normalizar_ventana(hook_start: float, hook_end: float, clip_start: float, clip_end: float) -> tuple[float, float]:
    """Estandariza el teaser a ~5s recortado a la ventana del clip (issue #116).

    Espejo de `ffmpeg_service._normalizar_ventana_hook`: así el shift del ASS
    coincide SIEMPRE con el teaser que renderiza build_hook_clip, incluso si
    el caller no normalizó antes.
    """
    dur = min(TEASER_DURACION, max(0.0, clip_end - clip_start))
    inicio = min(max(hook_start, clip_start), max(clip_start, clip_end - dur))
    return round(inicio, 3), round(inicio + dur, 3)


def _validar_ventana_hook(hook_start: float, hook_end: float) -> None:
    """Valida duración y rango del hook; ValueError si es inválido.

    Banda 4.5-5.5s (issue #116): la ventana ya llega normalizada a ~5s
    (`_normalizar_ventana_hook` de ffmpeg_service) desde jobs/build_hook_clip.
    """
    hook_dur = hook_end - hook_start
    if not (HOOK_TEASER_MIN < hook_dur < HOOK_TEASER_MAX):
        raise ValueError(f"Hook duracion {hook_dur:.3f}s debe estar estrictamente entre {HOOK_TEASER_MIN} y {HOOK_TEASER_MAX}s")
    if not (0.0 <= hook_start < hook_end):
        raise ValueError(f"Rango de hook invalido: [{hook_start},{hook_end}]")


def _segmento_en_ventana(s, inicio: float, fin: float) -> bool:
    """True si el segmento cruza la ventana [inicio, fin)."""
    return float(s.get("start", 0)) < fin and float(s.get("end", 0)) > inicio


def _segmentos_en_ventana(segments: list, inicio: float, fin: float) -> list:
    """Segmentos que cruzan la ventana [inicio, fin)."""
    return [s for s in segments if _segmento_en_ventana(s, inicio, fin)]


def _ventana_de_trabajo(segments: list, clip_start: float, clip_end: float) -> tuple[float, float]:
    """Ventana [start, end) del clip, ampliada ±2s si no hay segmentos."""
    if _segmentos_en_ventana(segments, clip_start, clip_end):
        return clip_start, clip_end
    # Si no hay segmentos en la ventana, ampliar ±2 segundos
    window_start = max(0.0, clip_start - 2.0)
    window_end = clip_end + 2.0
    logging.getLogger(__name__).warning(
        "[ass] Sin segmentos en ventana [%.1f-%.1f], ampliando a [%.1f-%.1f]",
        clip_start, clip_end, window_start, window_end
    )
    return window_start, window_end


def _seg_del_rango(
    st: float, en: float, txt: str, rango_start: float, rango_end: float,
    base: float, emoji: str | None = None,
) -> SubtitleSegment | None:
    """Segmento recortado al rango con base de desplazamiento; None si queda vacío."""
    if en < rango_start or st > rango_end:
        return None
    cs = max(st, rango_start)
    ce = min(en, rango_end)
    if ce > cs:
        return SubtitleSegment(start=cs - base, end=ce - base, text=txt, emoji=emoji)
    return None


def _segs_de_segmento(
    s,
    hook_start: float,
    hook_end: float,
    window_start: float,
    window_end: float,
    clip_start: float,
    hook_dur: float,
) -> tuple[SubtitleSegment | None, SubtitleSegment | None]:
    """(hook_seg, clip_seg) recortados para el segmento s; None si quedan vacíos."""
    st = float(s.get("start", 0))
    en = float(s.get("end", 0))
    txt = str(s.get("text", "")).strip()
    emoji = s.get("emoji")
    if not txt or en <= st:
        return None, None
    # Segmentos para el hook
    hook_seg = _seg_del_rango(st, en, txt, hook_start, hook_end, hook_start, emoji)
    # Segmentos para el clip (usar ventana ampliada si es necesario)
    clip_seg = _seg_del_rango(st, en, txt, window_start, window_end, clip_start - hook_dur, emoji)
    return hook_seg, clip_seg


def _generate_hooked_segments(
    segments: list[SubtitleSegment],
    clip_start: float,
    clip_end: float,
    hook_start: float,
    hook_end: float,
) -> tuple[list[SubtitleSegment], list[SubtitleSegment]]:
    """Lógica compartida de segmentos hooked. Retorna (hook_segs, clip_segs)."""
    _validar_ventana_hook(hook_start, hook_end)
    window_start, window_end = _ventana_de_trabajo(segments, clip_start, clip_end)
    hook_dur = hook_end - hook_start
    hook_segs: list[SubtitleSegment] = []
    clip_segs: list[SubtitleSegment] = []
    for s in segments:
        try:
            hook_seg, clip_seg = _segs_de_segmento(
                s, hook_start, hook_end, window_start, window_end, clip_start, hook_dur
            )
            if hook_seg is not None:
                hook_segs.append(hook_seg)
            if clip_seg is not None:
                clip_segs.append(clip_seg)
        except Exception:
            continue
    return hook_segs, clip_segs


def generate_hooked_ass(
    segments: list[SubtitleSegment],
    clip_start: float,
    clip_end: float,
    hook_start: float,
    hook_end: float,
    output_path: str | Path,
    title: str = "clipsai",
    style: str | None = None,
) -> str:
    hook_start, hook_end = _normalizar_ventana(hook_start, hook_end, clip_start, clip_end)
    hook_segs, clip_segs = _generate_hooked_segments(segments, clip_start, clip_end, hook_start, hook_end)
    all_shifted = sorted(hook_segs + clip_segs, key=lambda x: x["start"])
    return write_ass_file(all_shifted, output_path, title=title, style=style)


def build_hooked_ass_content(
    segments: list[SubtitleSegment],
    clip_start: float,
    clip_end: float,
    hook_start: float,
    hook_end: float,
    title: str = "clipsai",
    style: str | None = None,
) -> str:
    hook_start, hook_end = _normalizar_ventana(hook_start, hook_end, clip_start, clip_end)
    hook_segs, clip_segs = _generate_hooked_segments(segments, clip_start, clip_end, hook_start, hook_end)
    all_shifted = sorted(hook_segs + clip_segs, key=lambda x: x["start"])
    return generate_ass_content(all_shifted, title=title, style=style)
