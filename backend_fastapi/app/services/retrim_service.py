"""Re-trim y re-render de clips existentes (Issue #121).

El servicio es independiente del transporte HTTP: recibe un clip ya validado
(ownership) y devuelve el archivo re-renderizado. Reutiliza el pipeline real
de FFmpeg/ASS para no reprocesar el video fuente (Whisper/LLM).

Reglas de alcance:
- El rango se valida contra la duración real del video fuente.
- Se preserva toda la metadata y el estado de publicación del clip.
- El contador de ediciones se guarda en ``clip.tags["_retrim"]`` (sin migración).
"""

from __future__ import annotations

import copy
import logging
import os
import re
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.core.schemas import RenderConfig

from ..models import Clip, Job, Video
from . import ass_generator, editor, ffmpeg_service
from .transcript_utils import parse_transcript_text_to_segments

logger = logging.getLogger(__name__)

MIN_DURATION = 5.0
MAX_DURATION = 90.0
DEFAULT_MAX_RETRIMS = 3
MAX_SUBTITLE_CUES = 500
MAX_TEXT_CHARS = 20_000
RETRIM_TAG = "_retrim"
TMP_SUFFIX = ".retrim.tmp.mp4"
DEFAULT_CAPTION_STYLE = "karaoke_yellow"


@dataclass(frozen=True)
class RetrimPlan:
    """Todo lo necesario para renderizar un re-trim, ya validado."""

    source: Path
    start: float
    end: float
    cues: list[dict[str, Any]]
    hook: tuple[float, float] | None
    config: RenderConfig
    title: str


# ---------------------------------------------------------------------------
# Retry limit (protección de créditos, Issue #121 + #124)
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tags_dict(tags: object) -> dict[str, Any]:
    return dict(tags) if isinstance(tags, dict) else {}


def retrim_meta(clip: Clip) -> dict[str, Any]:
    """Metadata interna de re-trim almacenada en los tags del clip."""
    meta = _tags_dict(getattr(clip, "tags", None)).get(RETRIM_TAG)
    return dict(meta) if isinstance(meta, dict) else {}


def retrim_count(clip: Clip) -> int:
    try:
        return max(0, int(retrim_meta(clip).get("count", 0)))
    except (TypeError, ValueError):
        return 0


def max_retrims() -> int:
    """Límite configurable por entorno; nunca menor a 1."""
    try:
        value = int(os.getenv("RETRIM_MAX_PER_CLIP", str(DEFAULT_MAX_RETRIMS)))
    except (TypeError, ValueError):
        value = DEFAULT_MAX_RETRIMS
    return max(1, value)


def _merge_tags(clip: Clip, updates: dict[str, Any]) -> dict[str, Any]:
    tags = _tags_dict(getattr(clip, "tags", None))
    tags.update(updates)
    clip.tags = tags
    return tags


def reserve_retrim(clip: Clip, db: Any) -> object:
    """Reserva una edición antes del render; 429 si el clip agotó el límite."""
    limit = max_retrims()
    count = retrim_count(clip)
    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Este clip alcanzó el límite de {limit} ediciones.",
        )
    previous = copy.deepcopy(getattr(clip, "tags", None))
    _merge_tags(clip, {RETRIM_TAG: {"count": count + 1, "limit": limit, "updated_at": _now_iso()}})
    db.commit()
    return previous


def release_retrim(clip: Clip, db: Any, previous: object) -> None:
    """Devuelve la reserva si el render falla (no consume crédito)."""
    clip.tags = previous
    try:
        db.commit()
    except Exception:
        db.rollback()


# ---------------------------------------------------------------------------
# Origen y validación del rango
# ---------------------------------------------------------------------------


def _owner_path(owner: object) -> Path | None:
    if owner is None:
        return None
    path = getattr(owner, "filepath", None)
    if not path:
        path = getattr(owner, "file_path", None)
    return Path(path) if path else None


def _owner_paths(clip: Clip, job: Job | None, video: Video | None) -> list[Path]:
    owners = (video, getattr(clip, "video", None), getattr(job, "video", None))
    return list(filter(None, (_owner_path(owner) for owner in owners)))


def _source_candidates(clip: Clip, job: Job | None, video: Video | None) -> list[Path]:
    paths = _owner_paths(clip, job, video)
    storage = str(getattr(clip, "storage_path", "") or "")
    if storage and not _is_remote(storage):
        paths.append(Path(storage))
    return paths


def _is_remote(path: str) -> bool:
    return path.startswith(("http://", "https://", "s3://"))


def select_source(clip: Clip, job: Job | None, video: Video | None) -> Path:
    """Prefiere el video original; si falta, cae al archivo ya renderizado."""
    candidates = _source_candidates(clip, job, video)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise HTTPException(status_code=404, detail="No se encontró el video de origen del clip.")


def _exceeds_source(end: float, source_duration: float | None) -> bool:
    if not source_duration:
        return False
    return end > source_duration + 0.05


def validate_window(start: float, end: float, source_duration: float | None) -> float:
    """Valida el rango (5-90 s) y que no exceda el video fuente."""
    duration = end - start
    if duration < MIN_DURATION:
        raise HTTPException(status_code=422, detail="La duración mínima es de 5 segundos.")
    if duration > MAX_DURATION:
        raise HTTPException(status_code=422, detail="La duración máxima es de 90 segundos.")
    if _exceeds_source(end, source_duration):
        raise HTTPException(status_code=422, detail="El rango excede la duración del video fuente.")
    return duration


# ---------------------------------------------------------------------------
# Subtítulos editados
# ---------------------------------------------------------------------------


def _cue_field(cue: object, name: str) -> object:
    if isinstance(cue, dict):
        return cue.get(name)
    return getattr(cue, name, None)


def _cue_times(cue: object) -> tuple[float, float]:
    try:
        return float(_cue_field(cue, "start")), float(_cue_field(cue, "end"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Cue de subtítulo inválido.") from None


def _cue_in_window(cue_start: float, cue_end: float, window: tuple[float, float]) -> bool:
    start, end = window
    if cue_start < start:
        return False
    return cue_end <= end + 0.05


def _cue_text(cue: object) -> str:
    raw = _cue_field(cue, "text")
    if raw is None:
        return ""
    return str(raw).strip()


def _normalize_cue(cue: object, window: tuple[float, float]) -> dict[str, Any]:
    cue_start, cue_end = _cue_times(cue)
    text = _cue_text(cue)
    if not text:
        raise HTTPException(status_code=422, detail="Cue de subtítulo sin texto.")
    if cue_end <= cue_start:
        raise HTTPException(status_code=422, detail="Cue con end <= start.")
    if not _cue_in_window(cue_start, cue_end, window):
        raise HTTPException(status_code=422, detail="Cue fuera del rango del clip.")
    return {"start": cue_start, "end": cue_end, "text": text}


def _normalize_cues(cues: list[object], window: tuple[float, float]) -> list[dict[str, Any]]:
    if len(cues) > MAX_SUBTITLE_CUES:
        raise HTTPException(status_code=422, detail="Demasiados cues de subtítulo.")
    return [_normalize_cue(cue, window) for cue in cues]


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "\n").split("\n")]


def _non_empty_lines(text: str) -> list[str]:
    return [line for line in _clean_lines(text) if line]


def _split_parts(line: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?…])\s+", line) if part.strip()]


def _split_sentences(text: str) -> list[str]:
    lines = _non_empty_lines(text)
    if len(lines) > 1:
        return lines
    if not lines:
        return []
    return _split_parts(lines[0])


def _line_overflows(current: list[str], word: str, max_chars: int) -> bool:
    if not current:
        return False
    return len(" ".join(current + [word])) > max_chars


def _chunk_text(text: str, max_chars: int = 70) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    for word in text.split():
        if _line_overflows(current, word, max_chars):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _text_pieces(text: str) -> list[str]:
    return [chunk for sentence in _split_sentences(text) for chunk in _chunk_text(sentence)]


def _limit_pieces(pieces: list[str], duration: float) -> list[str]:
    """Evita cues por debajo de ~0.15 s agrupando piezas consecutivas."""
    limit = max(1, int(duration / 0.15))
    if len(pieces) <= limit:
        return pieces
    size = (len(pieces) + limit - 1) // limit
    return [" ".join(pieces[index:index + size]) for index in range(0, len(pieces), size)]


def _total_chars(pieces: list[str]) -> int:
    return sum(len(piece) for piece in pieces) or 1


def _cues_from_text(text: str, window: tuple[float, float]) -> list[dict[str, Any]]:
    start, end = window
    pieces = _limit_pieces(_text_pieces(text), end - start)
    if not pieces:
        raise HTTPException(status_code=422, detail="El texto de subtítulos está vacío.")
    total = _total_chars(pieces)
    cursor = start
    cues: list[dict[str, Any]] = []
    for index, piece in enumerate(pieces):
        share = (end - start) * len(piece) / total
        cue_end = end if index == len(pieces) - 1 else min(end, cursor + share)
        cues.append({"start": cursor, "end": cue_end, "text": piece})
        cursor = cue_end
    return cues


def _seg_times(seg: object) -> tuple[float, float, str] | None:
    try:
        return float(seg["start"]), float(seg["end"]), str(seg["text"]).strip()  # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return None


def _seg_overlaps(seg_start: float, seg_end: float, window: tuple[float, float]) -> bool:
    start, end = window
    if seg_end <= start:
        return False
    return seg_start < end


def _seg_in_window(seg: object, window: tuple[float, float]) -> dict[str, Any] | None:
    times = _seg_times(seg)
    if times is None:
        return None
    seg_start, seg_end, text = times
    if not text:
        return None
    if not _seg_overlaps(seg_start, seg_end, window):
        return None
    start, end = window
    return {"start": max(seg_start, start), "end": min(seg_end, end), "text": text}


def _cues_from_segments(segments: list[Any], window: tuple[float, float]) -> list[dict[str, Any]]:
    return [cue for cue in (_seg_in_window(seg, window) for seg in segments) if cue]


def _result_segments(job: Job | None) -> list[Any]:
    metadata = getattr(job, "result_metadata", None)
    if not isinstance(metadata, dict):
        return []
    segments = metadata.get("transcription_segments")
    return segments if isinstance(segments, list) else []


def _original_segments(job: Job | None, video: Video | None) -> list[Any]:
    segments = _result_segments(job)
    if segments:
        return segments
    transcript = getattr(video, "transcript", None) if video else None
    return parse_transcript_text_to_segments(str(transcript or ""))


def _fallback_text(clip: Clip) -> str:
    return str(getattr(clip, "transcript", None) or getattr(clip, "title", None) or "CLIPSAI")


def options_cues(clip: Clip, job: Job | None, video: Video | None, window: tuple[float, float]) -> list[dict[str, Any]]:
    """Cues actuales del clip para precargar el editor."""
    cues = _cues_from_segments(_original_segments(job, video), window)
    return cues or _cues_from_text(_fallback_text(clip), window)


def resolve_cues(body: Any, clip: Clip, job: Job | None, video: Video | None) -> list[dict[str, Any]]:
    """Cues editados explícitos, texto libre o transcripción original."""
    window = (float(body.start_time), float(body.end_time))
    if body.subtitle_cues:
        return _normalize_cues(body.subtitle_cues, window)
    if body.subtitles_text and str(body.subtitles_text).strip():
        return _cues_from_text(str(body.subtitles_text)[:MAX_TEXT_CHARS], window)
    return options_cues(clip, job, video, window)


def _shift_cues(cues: list[dict[str, Any]], start: float) -> list[dict[str, Any]]:
    return [
        {"start": max(0.0, float(cue["start"]) - start), "end": max(0.0, float(cue["end"]) - start), "text": cue["text"]}
        for cue in cues
    ]


# ---------------------------------------------------------------------------
# Hook y ASS
# ---------------------------------------------------------------------------


def _hook_dict(clip: Clip) -> dict[str, Any]:
    hook = _tags_dict(getattr(clip, "tags", None)).get("hook")
    return hook if isinstance(hook, dict) else {}


def _hook_times(hook: dict[str, Any]) -> tuple[float, float] | None:
    try:
        return float(hook["start"]), float(hook["end"])
    except (KeyError, TypeError, ValueError):
        return None


def _valid_hook(times: tuple[float, float] | None) -> tuple[float, float] | None:
    if times is None:
        return None
    if times[1] <= times[0]:
        return None
    return times


def hook_window(clip: Clip) -> tuple[float, float] | None:
    """Ventana del teaser ya aplicada al clip (solo modo teaser)."""
    hook = _hook_dict(clip)
    if not hook.get("applied"):
        return None
    if str(hook.get("mode", "teaser")) != "teaser":
        return None
    return _valid_hook(_hook_times(hook))


def _write_ass(plan: RetrimPlan, output: Path) -> None:
    style = ass_generator.ass_style_for(plan.config.caption_style)
    if plan.hook:
        ass_generator.generate_hooked_ass(
            plan.cues, plan.start, plan.end, plan.hook[0], plan.hook[1], output, title=plan.title, style=style
        )
        return
    ass_generator.write_ass_file(_shift_cues(plan.cues, plan.start), output, title=plan.title, style=style)


def _render_trimmed(plan: RetrimPlan, output: Path) -> None:
    if plan.hook:
        ffmpeg_service.build_hook_clip(
            plan.source, plan.start, plan.end, plan.hook[0], plan.hook[1], output, sfx_mood=plan.config.sfx_mood
        )
        return
    ffmpeg_service.cut_segment(plan.source, plan.start, plan.end, output)


# ---------------------------------------------------------------------------
# Render final (watermark / resolución / fps)
# ---------------------------------------------------------------------------


def _watermark_path(config: RenderConfig) -> Path | None:
    raw = getattr(config, "watermark_path", None)
    if not raw:
        return None
    candidate = Path(str(raw))
    if candidate.is_file():
        return candidate
    raise HTTPException(status_code=422, detail="watermark_path debe ser un archivo local existente.")


def _scale_filter(width: int, height: int, fps: int) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}"
    )


def _overlay_filter(width: int, height: int, fps: int) -> str:
    return f"[0:v]{_scale_filter(width, height, fps)}[base];[base][1:v]overlay=W-w-24:H-h-48[outv]"


def _run_finalize(rendered: Path, final: Path, target: tuple[int, int, int], watermark: Path | None) -> None:
    width, height, fps = target
    cmd = ["ffmpeg", "-y", "-i", str(rendered)]
    if watermark:
        cmd += ["-i", str(watermark), "-filter_complex", _overlay_filter(width, height, fps), "-map", "[outv]", "-map", "0:a?"]
    else:
        cmd += ["-vf", _scale_filter(width, height, fps)]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        detail = result.stderr.decode(errors="ignore")[:600] if result.stderr else "sin stderr"
        raise HTTPException(status_code=500, detail=f"FFmpeg final falló: {detail}")


def _video_fps(path: Path) -> float | None:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate", "-of", "default=nw=1:nk=1", str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        numerator, _, denominator = result.stdout.strip().partition("/")
        return float(numerator) / float(denominator or 1)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _finalize(rendered: Path, final: Path, config: RenderConfig) -> None:
    watermark = _watermark_path(config)
    width, height = str(config.resolution).split("x")
    target = (int(width), int(height), int(config.fps))
    if watermark is None and target == (1080, 1920, 30) and _video_fps(rendered) == 30.0:
        os.replace(rendered, final)
        return
    _run_finalize(rendered, final, target, watermark)


def _default_clips_dir() -> Path:
    env_dir = os.getenv("STORAGE_CLIPS_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    if Path("/.dockerenv").exists() or os.getenv("PORT"):
        return Path("/tmp/clipsai/clips")
    return Path(__file__).resolve().parents[3] / "storage" / "clips"


def _storage_value(clip: Clip) -> str:
    return str(getattr(clip, "storage_path", "") or "")


def _clip_output_path(clip: Clip) -> Path:
    storage = _storage_value(clip)
    if storage and not _is_remote(storage):
        return Path(storage)
    job_id = str(getattr(clip, "job_id", "") or "retrims")
    return _default_clips_dir() / job_id / f"{clip.id}_retrim.mp4"


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------


def _render_pipeline(plan: RetrimPlan, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="clipsai_retrim_") as tmp:
        root = Path(tmp)
        trimmed = root / "trimmed.mp4"
        reframed = root / "reframed_9x16.mp4"
        ass_file = root / "subtitles.ass"
        burned = root / "burned.mp4"
        _render_trimmed(plan, trimmed)
        editor.reframe_video(trimmed, reframed, aspect_ratio="9:16")
        _write_ass(plan, ass_file)
        ffmpeg_service.burn_subtitles(reframed, ass_file, burned)
        _finalize(burned, output, plan.config)


def _require_output(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="El re-render no produjo un archivo válido.")


def _cleanup(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("[retrim] no se pudo borrar temporal %s", path)


def _apply_hook_tag(tags: dict[str, Any], hook: tuple[float, float] | None) -> None:
    if hook:
        tags["hook"] = {"start": hook[0], "end": hook[1], "applied": True, "mode": "teaser"}
        return
    if "hook" in tags:
        tags["hook"] = {**tags["hook"], "applied": False}


def _apply_result(db: Any, clip: Clip, plan: RetrimPlan, output: Path) -> None:
    clip.start_time = float(plan.start)
    clip.end_time = float(plan.end)
    clip.storage_path = str(output)
    meta = retrim_meta(clip)
    render = "hook+ass" if plan.hook else "ass"
    tags = _merge_tags(
        clip,
        {
            "has_ass": bool(plan.cues),
            "has_hook": bool(plan.hook),
            "ass": {"applied": bool(plan.cues), "segments": len(plan.cues), "style": plan.config.caption_style},
            "_render": render,
            RETRIM_TAG: {
                **meta,
                "last_file": str(output),
                "caption_style": plan.config.caption_style,
                "watermark_path": plan.config.watermark_path,
            },
        },
    )
    _apply_hook_tag(tags, plan.hook)
    db.commit()
    db.refresh(clip)


def execute_retrim(db: Any, clip: Clip, plan: RetrimPlan) -> Path:
    """Renderiza a un temporal y reemplaza el archivo del clip de forma atómica."""
    output = _clip_output_path(clip)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output.with_name(f".{output.stem}{TMP_SUFFIX}")
    try:
        _render_pipeline(plan, tmp_output)
        _require_output(tmp_output)
        os.replace(tmp_output, output)
    finally:
        _cleanup(tmp_output)
    _apply_result(db, clip, plan, output)
    return output


def clip_uuid(clip_id: object) -> uuid.UUID:
    """UUID validado para el path param; 422 si no es válido."""
    try:
        return uuid.UUID(str(clip_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="clip_id inválido.") from None
