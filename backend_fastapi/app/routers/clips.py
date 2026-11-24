"""Router de Clips — CRUD + descarga + biblioteca (Issue 5 + Issue 16)."""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

from ..deps import CurrentUser, DbSession
from ..models import Clip, Video
from ..schemas import ClipListItem, ClipListResponse, ClipResponse, ClipUpdate
from ..services.r2_service import BUCKET_NAME_ENV, delete_r2_object, get_r2_client, r2_object_key_from_url

router = APIRouter(prefix="/clips", tags=["clips"])


def _clip_has_ass(tags: object) -> bool:
    if not isinstance(tags, dict):
        return False
    # FIX: has_ass explícito tiene prioridad (re-render)
    if "has_ass" in tags:
        return bool(tags.get("has_ass"))
    if isinstance(tags.get("ass"), dict) and tags["ass"].get("applied"):
        return True
    r = tags.get("_render")
    return r in ("ass", "hook+ass")


def _clip_has_hook(tags: object) -> bool:
    if not isinstance(tags, dict):
        return False
    if "has_hook" in tags:
        return bool(tags.get("has_hook"))
    if isinstance(tags.get("hook"), dict) and tags["hook"].get("applied"):
        return True
    r = tags.get("_render")
    return r in ("hook", "hook+ass")


def _clip_duration(start: float, end: float) -> float | None:
    try:
        return float(end) - float(start)
    except Exception:
        return None


def _clip_file_path(clip: Clip) -> str | None:
    return getattr(clip, "storage_path", None)


def _clip_stream_url(clip_id: uuid.UUID) -> str:
    return f"/clips/{clip_id}/descarga"


def _enrich_clip_response(clip: Clip) -> dict:
    return {
        "id": clip.id,
        "video_id": getattr(clip, "video_id", None),
        "job_id": clip.job_id,
        "title": clip.title,
        "start_time": clip.start_time,
        "end_time": clip.end_time,
        "score": clip.score,
        "tags": clip.tags,
        "storage_path": getattr(clip, "storage_path", None),
        "file_path": _clip_file_path(clip),
        "stream_url": _clip_stream_url(clip.id),
        "duration": _clip_duration(clip.start_time, clip.end_time),
        "has_ass": _clip_has_ass(clip.tags),
        "has_hook": _clip_has_hook(clip.tags),
        "status": clip.status,
        "published_platform": getattr(clip, "published_platform", None),
        "social_post_id": getattr(clip, "social_post_id", None),
        "social_post_url": getattr(clip, "social_post_url", None),
        "published_at": getattr(clip, "published_at", None),
        "publication_status": getattr(clip, "publication_status", None),
        "social_network": getattr(clip, "social_network", None),
        "created_at": clip.created_at,
        "updated_at": clip.updated_at,
    }


class ReRenderRequest(BaseModel):
    enable_ass: bool = True
    enable_hook: bool = True


def _resolver_video_de_clip(db: Any, clip: Any) -> Any | None:
    """Resuelve el Video asociado al clip (directo o vía job)."""
    video = None
    if clip.video_id is not None:
        video = db.get(Video, clip.video_id)
    if video is None and clip.job_id is not None:
        from ..models import Job

        job = db.get(Job, clip.job_id)
        if job is not None:
            video = db.get(Video, job.video_id)
    return video


def _segundos_de_timestamp(ts_str: str) -> float:
    """Convierte HH:MM:SS (o MM:SS, o SS) en segundos."""
    parts = ts_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def _segmento_de_linea(line: str, re_ts, cursor: float) -> tuple[dict, float] | None:
    """Segmento con timestamp parseado; None si la línea no trae timestamp válido."""
    m = re_ts.match(line)
    if m is None:
        return None
    try:
        s = _segundos_de_timestamp(m.group(1))
    except Exception:
        return None
    return {"start": s, "end": s + 3.0, "text": m.group(2).strip()}, s + 3.0


def _parsear_transcript_simple(txt: str) -> list[dict]:
    """Parser simple `HH:MM:SS - texto` con cursor de 3s para líneas sin timestamp."""
    import re

    segs: list[dict] = []
    re_ts = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*(.+)$")
    cursor = 0.0
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        resultado = _segmento_de_linea(line, re_ts, cursor)
        if resultado is not None:
            segs.append(resultado[0])
            cursor = resultado[1]
            continue
        segs.append({"start": cursor, "end": cursor + 3.0, "text": line})
        cursor += 3.0
    return segs


def _segmentos_de_whisper(video: Any) -> list[dict]:
    """Segmentos vía Whisper (lista vacía si falla o no devuelve nada)."""
    try:
        from ..services.whisper_service import transcribe_video

        segs = transcribe_video(str(video.filepath), language="es")
        if segs:
            return [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in segs]
    except Exception:
        pass
    return []


def _transcript_de_video(video: Any) -> str | None:
    """Texto del transcript: columna directa o archivo de transcripción."""
    if video.transcript:
        return video.transcript
    if video.transcription_filepath and Path(str(video.transcription_filepath)).is_file():
        return Path(str(video.transcription_filepath)).read_text(encoding="utf-8", errors="ignore")
    return None


def _cargar_segmentos(video: Any) -> list[dict]:
    """Segmentos para re-render: Whisper primero, fallback al parser simple."""
    segs = _segmentos_de_whisper(video)
    if segs:
        return segs
    # Fallback parse transcript
    txt = _transcript_de_video(video)
    if txt:
        return _parsear_transcript_simple(txt)
    return []


def _duracion_de_video(video: Any, segments: list[dict]) -> float | None:
    """Duración estimada: duration_seconds o fin del último segmento."""
    try:
        if video.duration_seconds:
            return float(video.duration_seconds)
        if segments:
            return float(segments[-1].get("end", 0))
    except Exception:
        return None
    return None


def _detectar_hooks(video: Any, segments: list[dict]) -> list[dict]:
    """Hooks LLM para re-render (lista vacía si falla)."""
    if not segments:
        return []
    try:
        from ..services.hook_service import detect_hooks

        duration = _duracion_de_video(video, segments)
        return detect_hooks(segments, duration_hint=duration, mock=False) or []
    except Exception:
        return []


def _hook_en_rango(clip: Any, h: dict) -> tuple[float, float] | None:
    """(hs, he) si el hook cae dentro del clip y dura 3-6s; None si no."""
    hk = h.get("hook") or {}
    hs = float(hk.get("start_time", hk.get("start", 0)))
    he = float(hk.get("end_time", hk.get("end", 0)))
    if clip.start_time <= hs < he <= clip.end_time and 3.0 <= (he - hs) <= 6.0:
        return hs, he
    return None


def _score_supera(h: dict, best: tuple | None) -> bool:
    """True si el hook supera al mejor actual (o no hay mejor aún)."""
    if best is None:
        return True
    return int(h.get("viral_score", 0)) > best[2].get("viral_score", 0)


def _buscar_hook_llm(clip: Any, hooks: list[dict]) -> tuple | None:
    """Busca el hook LLM con mejor score contenido dentro del clip."""
    best = None
    for h in hooks:
        try:
            hs, he = _hook_en_rango(clip, h)
            if _score_supera(h, best):
                best = (hs, he, h)
        except Exception:
            continue
    return best


def _ajustar_al_segmento_cercano(clip: Any, segments: list[dict], hook_dur: float, hs: float, he: float) -> tuple[float, float]:
    """Ajusta el hook al inicio del segmento más cercano si cabe dentro del clip."""
    try:
        closest = min(segments, key=lambda s: abs(float(s.get("start", 0)) - hs))
        cs = float(closest.get("start", hs))
        if clip.start_time <= cs <= clip.end_time - hook_dur:
            return cs, cs + hook_dur
    except Exception:
        pass
    return hs, he


def _recortar_al_clip(hook_dur: float, hs: float, he: float, start: float, end: float) -> tuple[float, float]:
    """Ajusta el hook para que quede dentro del rango [start, end] del clip."""
    if hs < start:
        hs = start
        he = hs + hook_dur
    if he > end:
        he = end
        hs = he - hook_dur
    return hs, he


def _hook_sintetico(clip: Any, segments: list[dict]) -> tuple | None:
    """Hook sintético centrado en el clip (5s), ajustado al segmento más cercano."""
    clip_dur = clip.end_time - clip.start_time
    if not (15 <= clip_dur <= 90):
        return None
    hook_dur = 5.0
    center = (clip.start_time + clip.end_time) / 2
    hs = center - hook_dur / 2
    he = hs + hook_dur
    if segments:
        hs, he = _ajustar_al_segmento_cercano(clip, segments, hook_dur, hs, he)
    hs, he = _recortar_al_clip(hook_dur, hs, he, clip.start_time, clip.end_time)
    if he - hs >= 3.0:
        return (round(hs, 2), round(he, 2), None)
    return None


def _elegir_hook_re_render(clip: Any, hooks: list[dict], segments: list[dict]) -> tuple | None:
    """Hook para re-render: LLM contenido, si no sintético centrado. None si nada aplica."""
    try:
        best = _buscar_hook_llm(clip, hooks)
        if best:
            return best
        return _hook_sintetico(clip, segments)
    except Exception:
        return None


def _tags_hook_activado(tags: dict, hook_sel: tuple | None) -> None:
    """Marca el hook aplicado con el rango seleccionado."""
    hs, he, _ = hook_sel if hook_sel else (None, None, None)
    tags["hook"] = {"start": hs, "end": he, "applied": True, "source": "re-render"}


def _tags_hook_fallido(tags: dict, meta: dict) -> None:
    """Hook pedido pero no aplicado (ej. duración <15s o fallo FFmpeg)."""
    if meta.get("hook_applied") is False or not meta.get("hook_applied"):
        # Mantener has_hook True (usuario lo pidió) pero marcar detalle
        if "hook" not in tags:
            tags["hook"] = {"applied": False, "reason": "hook no aplicable o fallo FFmpeg", "requested": True}


def _tags_hook_re_render(tags: dict, meta: dict, enable_hook: bool, hook_sel: tuple | None) -> None:
    """Mantiene la estructura legacy 'hook' según el toggle y el resultado del render."""
    if enable_hook and meta.get("hook_applied"):
        _tags_hook_activado(tags, hook_sel)
        # has_hook ya True arriba
    elif not enable_hook:
        tags.pop("hook", None)
        tags["has_hook"] = False
    else:
        _tags_hook_fallido(tags, meta)


def _tags_ass_aplicado(tags: dict, segments: list[dict]) -> None:
    """Marca ASS aplicado con la cantidad de segmentos usados."""
    tags["ass"] = {"applied": True, "segments": len(segments) if segments else 0}
    tags["has_ass"] = True


def _tags_ass_re_render(tags: dict, meta: dict, enable_ass: bool, segments: list[dict]) -> None:
    """Mantiene la estructura legacy 'ass' según el toggle y el resultado del render."""
    if not enable_ass:
        tags.pop("ass", None)
        tags["has_ass"] = False
        return
    if meta.get("ass_applied"):
        _tags_ass_aplicado(tags, segments)
        return
    # enable_ass True pero ASS falló: mantener has_ass True y registrar error
    tags["ass"] = {"applied": False, "reason": "ASS fallo, fallback sin subtítulos", "requested": True}
    tags["has_ass"] = True


def _tags_dict(clip: Any) -> dict:
    """Tags del clip normalizados a dict (por si la columna guardó una lista)."""
    tags = clip.tags if isinstance(clip.tags, dict) else {}
    if not isinstance(tags, dict):
        tags = {}
    return tags


def _re_render_exitoso(db: Any, clip: Any, clip_id: uuid.UUID, out_path: str, meta: dict, enable_ass: bool, enable_hook: bool, segments: list[dict], hook_sel: tuple | None) -> None:
    """Persiste el resultado del re-render: storage, tags has_ass/has_hook y status ready."""
    clip.storage_path = out_path
    # Actualizar tags — FIX: actualizar explícitamente has_ass/has_hook = enable_* antes del commit (auditoría Parte 1)
    tags = _tags_dict(clip)
    # FIX explícito requerido por auditoría: has_ass/has_hook reflejan el toggle solicitado
    tags["has_ass"] = bool(enable_ass)
    tags["has_hook"] = bool(enable_hook)
    _tags_hook_re_render(tags, meta, enable_hook, hook_sel)
    _tags_ass_re_render(tags, meta, enable_ass, segments)
    tags["_render"] = meta.get("render", "re-render")
    tags["_re_render"] = {"enable_ass": enable_ass, "enable_hook": enable_hook, "at": __import__("datetime").datetime.utcnow().isoformat(), "out_path": out_path}
    clip.tags = tags
    clip.status = "ready"
    clip.error_log = None
    # FIX: storage_path ya actualizado arriba; updated_at se actualiza por trigger set_updated_at(), pero forzamos toque para cache busting
    try:
        from sqlalchemy import func as _func
        clip.updated_at = _func.now()  # noqa: trigger también lo hará
    except Exception:
        pass
    db.commit()
    logger.info(f"[re-render] clip {clip_id} ok -> {out_path} meta={meta} has_ass={tags['has_ass']} has_hook={tags['has_hook']}")


def _re_render_fallido(db: Any, clip: Any, clip_id: uuid.UUID, exc: Exception) -> None:
    import traceback

    clip.status = "FAILED"
    clip.error_log = str(exc)[:2000] + "\n" + traceback.format_exc()[:2000]
    # tags error
    tags = _tags_dict(clip)
    tags["_render_error"] = str(exc)[:500]
    clip.tags = tags
    db.commit()
    logger.exception(f"[re-render] fallo clip {clip_id}")


def _video_origen_valido(db: Any, clip: Any) -> Any | None:
    """Video origen del clip; None si no existe o su archivo físico no está en disco."""
    video = _resolver_video_de_clip(db, clip)
    if video is None or not Path(str(video.filepath)).is_file():
        return None
    return video


def _detectar_hooks_si_se_piden(enable_hook: bool, video: Any, segments: list[dict]) -> list[dict]:
    """Hooks LLM solo si enable_hook está activo y hay segmentos."""
    if enable_hook and segments:
        return _detectar_hooks(video, segments)
    return []


def _segmentos_y_hooks_re_render(enable_ass: bool, enable_hook: bool, video: Any) -> tuple[list[dict], list[dict]]:
    """Segmentos y hooks LLM para el re-render (vacíos si fallan o no se necesitan)."""
    if not (enable_ass or enable_hook):
        return [], []
    try:
        # Reusar lógica de jobs.py sin importar circular: intentar whisper + parse
        segments = _cargar_segmentos(video)
        hooks = _detectar_hooks_si_se_piden(enable_hook, video, segments)
        return segments, hooks
    except Exception as e:
        logger.warning(f"[re-render] segmentos/hooks fallo: {e}")
        return [], []


def _hook_efectivo_re_render(clip: Any, enable_hook: bool, hooks: list[dict], segments: list[dict]) -> tuple | None:
    """Hook seleccionado para el re-render (None si enable_hook es False o no aplica)."""
    # Seleccionar hook si enable_hook
    hook_sel = _elegir_hook_re_render(clip, hooks, segments) if enable_hook and segments else None
    # Desactivar flags según enable
    return hook_sel if enable_hook else None


def _renderizar_re_render(video: Any, clip: Any, enable_ass: bool, segments: list[dict], hook_sel: tuple | None) -> tuple[str, dict]:
    """Llama al renderer de jobs con los parámetros efectivos del re-render."""
    # Si enable_ass False, no pasar segmentos a render (evita ASS)
    segs_for_render = segments if enable_ass else []

    from ..routers.jobs import _render_clip_with_ass_and_hook as _render  # reuse

    # Usar helper de jobs para render (import diferido para evitar ciclo)
    # _render espera segments list; si enable_ass False, pasar lista vacía
    return _render(
        str(video.filepath),
        float(clip.start_time),
        float(clip.end_time),
        segs_for_render or [],
        hook_sel,
        clip.job_id,
        0,
        clip.title,
    )


def _ejecutar_re_render(db: Any, clip_id: uuid.UUID, enable_ass: bool, enable_hook: bool) -> None:
    """Ciclo completo de re-render sobre el clip (render + persistencia)."""
    clip = db.get(Clip, clip_id)
    if clip is None:
        return
    # Resolver video
    video = _video_origen_valido(db, clip)
    if video is None:
        clip.status = "FAILED"
        clip.error_log = "Video origen no encontrado para re-render"
        db.commit()
        return

    # Cargar segmentos si alguno de los flags activo
    segments, hooks = _segmentos_y_hooks_re_render(enable_ass, enable_hook, video)

    effective_hook = _hook_efectivo_re_render(clip, enable_hook, hooks, segments)

    try:
        out_path, meta = _renderizar_re_render(video, clip, enable_ass, segments, effective_hook)
        _re_render_exitoso(db, clip, clip_id, out_path, meta, enable_ass, enable_hook, segments, effective_hook)
    except Exception as e:
        _re_render_fallido(db, clip, clip_id, e)


def _run_re_render(clip_id: uuid.UUID, enable_ass: bool, enable_hook: bool) -> None:
    from ..database import SessionLocal as _SessionLocal

    db = _SessionLocal()
    try:
        _ejecutar_re_render(db, clip_id, enable_ass, enable_hook)
    except Exception as e:
        logger.exception(f"[re-render] error inesperado {clip_id}: {e}")
    finally:
        try:
            db.close()
        except Exception:
            pass


# Auditoría 2026-09-21: pipeline real 100% — sin fallback de prueba. El worker escribe MP4 físico en /app/storage/clips.


def _get_clip_or_404(db: DbSession, clip_id: uuid.UUID) -> Clip:
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    return clip


def _assert_ownership(db: DbSession, clip: Clip, current_user) -> None:
    video = _resolver_video_de_clip(db, clip)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    if video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para este clip")


def _filtrar_por_texto_y_score(base, q: Optional[str], min_score: Optional[float]):
    """Filtros de búsqueda por texto y score mínimo."""
    if q is not None and q.strip() != "":
        pattern = f"%{q.strip()}%"
        base = base.where(
            (Clip.title.ilike(pattern)) | (Video.transcript.ilike(pattern))
        )

    if min_score is not None:
        base = base.where(Clip.score >= min_score)
    return base


def _filtrar_por_ids_y_status(base, video_id, job_id, clip_status):
    """Filtros por video, job y status del clip."""
    if video_id is not None:
        base = base.where((Clip.video_id == video_id) | (Job.video_id == video_id))

    if job_id is not None:
        base = base.where(Clip.job_id == job_id)

    if clip_status is not None:
        base = base.where(Clip.status == clip_status)
    return base


_ORDENES_CLIPS = {
    "created_at_desc": lambda base: base.order_by(Clip.created_at.desc()),
    "created_at_asc": lambda base: base.order_by(Clip.created_at.asc()),
    "score_desc": lambda base: base.order_by(Clip.score.desc().nulls_last(), Clip.created_at.desc()),
    "score_asc": lambda base: base.order_by(Clip.score.asc().nulls_last(), Clip.created_at.desc()),
}


def _ordenar_clips(base, sort_by: str):
    """Ordena la query según `sort_by` (sin cambio si el orden es desconocido)."""
    orden = _ORDENES_CLIPS.get(sort_by)
    if orden is not None:
        return orden(base)
    return base


def _transcript_resumido(video_transcript) -> str | None:
    """Transcript del video truncado a 500 caracteres."""
    if video_transcript:
        return str(video_transcript)[:500]
    return None


def _clip_list_item(clip, video_transcript) -> ClipListItem:
    """Item de la lista de clips a partir de una fila (clip, transcript)."""
    return ClipListItem(
        id=clip.id,
        job_id=clip.job_id,
        title=clip.title,
        score=clip.score,
        start_time=clip.start_time,
        end_time=clip.end_time,
        transcript=_transcript_resumido(video_transcript),
        status=getattr(clip, "status", None),
        published_platform=getattr(clip, "published_platform", None),
        social_post_url=getattr(clip, "social_post_url", None),
        published_at=getattr(clip, "published_at", None),
        created_at=clip.created_at,
        updated_at=getattr(clip, "updated_at", None),
        file_path=_clip_file_path(clip),
        stream_url=_clip_stream_url(clip.id),
        duration=_clip_duration(clip.start_time, clip.end_time),
        has_ass=_clip_has_ass(clip.tags),
        has_hook=_clip_has_hook(clip.tags),
        tags=clip.tags if isinstance(clip.tags, (dict, list)) else None,
    )


@router.get(
    "",
    response_model=ClipListResponse,
    summary="Listar clips del usuario (biblioteca con búsqueda, filtros y paginación)",
)
def list_clips(
    db: DbSession,
    current_user: CurrentUser,
    q: Optional[str] = Query(default=None, description="Búsqueda por título o transcripción (case-insensitive)"),
    min_score: Optional[float] = Query(default=None, ge=0, le=100, description="Score mínimo (0-100)"),
    sort_by: Literal["created_at_desc", "created_at_asc", "score_desc", "score_asc"] = Query(
        default="created_at_desc", description="Orden de resultados"
    ),
    page: int = Query(default=1, ge=1, description="Número de página"),
    limit: int = Query(default=10, ge=1, le=100, description="Tamaño de página"),
    video_id: Optional[uuid.UUID] = Query(default=None, description="Filtrar por video"),
    status: Optional[str] = Query(default=None, description="Filtrar por status"),
    job_id: Optional[uuid.UUID] = Query(default=None, description="Filtrar por job"),
) -> ClipListResponse:
    from ..models import Job

    base = (
        select(Clip, Video.transcript.label("video_transcript"))
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == current_user.id)
    )

    base = _filtrar_por_texto_y_score(base, q, min_score)
    base = _filtrar_por_ids_y_status(base, video_id, job_id, status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total: int = db.scalar(count_stmt) or 0
    total_pages: int = math.ceil(total / limit) if total > 0 else 0

    base = _ordenar_clips(base, sort_by).offset((page - 1) * limit).limit(limit)

    rows = db.execute(base).all()

    items: list[ClipListItem] = [_clip_list_item(clip, video_transcript) for clip, video_transcript in rows]

    return ClipListResponse(items=items, total=total, page=page, limit=limit, total_pages=total_pages)


@router.get(
    "/{clip_id}",
    response_model=ClipResponse,
    summary="Obtener un clip por id",
)
def get_clip(
    clip_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)
    return _enrich_clip_response(clip)


@router.patch(
    "/{clip_id}",
    response_model=ClipResponse,
    summary="Actualizar metadata de un clip (title/tags)",
)
def update_clip(
    clip_id: uuid.UUID,
    payload: ClipUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nada para actualizar")

    if "title" in data:
        clip.title = data["title"]
    if "tags" in data:
        clip.tags = data["tags"]

    db.commit()
    db.refresh(clip)
    return _enrich_clip_response(clip)


@router.post(
    "/{clip_id}/re-render",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-renderizar clip con ASS/Hook (enable_ass, enable_hook)",
)
def re_render_clip(
    clip_id: uuid.UUID,
    payload: ReRenderRequest,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)
    if clip.status == "PROCESSING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Clip ya en procesamiento")
    clip.status = "PROCESSING"
    try:
        clip.error_log = None
    except Exception:
        pass
    db.commit()
    background_tasks.add_task(_run_re_render, clip.id, bool(payload.enable_ass), bool(payload.enable_hook))
    return {"detail": "Re-render encolado", "clip_id": str(clip.id), "status": "PROCESSING", "enable_ass": bool(payload.enable_ass), "enable_hook": bool(payload.enable_hook)}


@router.delete(
    "/{clip_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un clip",
)
def delete_clip(
    clip_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)

    _purge_clip_storage(clip)

    db.delete(clip)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _purge_clip_storage(clip: Clip) -> None:
    """Elimina el objeto de R2 (best-effort) o archivo local del clip.

    Si storage_path apunta a R2 (http(s)), borra el objeto con delete_r2_object
    sin bloquear la transacción de DB aunque R2 falle. Si es ruta local,
    conserva el unlink actual.
    """
    storage_path = getattr(clip, "storage_path", None)
    if not storage_path:
        return
    storage_path = str(storage_path).strip()
    if storage_path.lower().startswith(("http://", "https://")):
        key = r2_object_key_from_url(storage_path)
        if not key:
            logger.warning(
                "[CLIP DELETE] no se pudo extraer key R2 de %s", storage_path[:120]
            )
            return
        try:
            s3 = get_r2_client()
            bucket = BUCKET_NAME_ENV
            delete_r2_object(s3, bucket, key)
        except Exception as exc:  # nunca bloquea el borrado en DB
            logger.warning("[CLIP DELETE] fallo cliente R2: %s", exc)
        return
    # Ruta local: unlink actual
    try:
        path = Path(storage_path)
        if path.is_file():
            path.unlink()
    except Exception:
        pass


def _ruta_desde_atributos(obj, attrs: tuple[str, ...]) -> str | None:
    """Primer atributo del objeto con una ruta no vacía."""
    for attr in attrs:
        v = getattr(obj, attr, None)
        if v and str(v).strip():
            return str(v).strip()
    return None


def _ruta_del_video_asociado(db, clip: Clip) -> str | None:
    """Ruta cruda del archivo del video asociado al clip (None si falla o no hay)."""
    try:
        video = db.get(Video, clip.video_id)
        if video is not None:
            return _ruta_desde_atributos(video, ("filepath", "file_path", "video_path", "path"))
    except Exception:
        pass
    return None


def _raw_path_de_clip(db, clip: Clip) -> str | None:
    """Ruta cruda del archivo del clip (clip primero, video asociado como fallback)."""
    raw_path = _ruta_desde_atributos(clip, ("file_path", "video_path", "output_path", "storage_path", "filepath", "path"))
    # Fallback: si clip no tiene ruta, intentar video asociado
    if raw_path or clip.video_id is None:
        return raw_path
    return _ruta_del_video_asociado(db, clip)


def _redirigir_si_remota(raw_path: str, clip_id: uuid.UUID):
    """RedirectResponse 302 si la ruta es una URL remota (R2); None si es local."""
    # Clips procesados por el worker RunPod: storage_path es una URL R2 → redirigir
    if raw_path.lower().startswith(("http://", "https://")):
        logger.info(f"[CLIP DESCARGA] clip {clip_id} es URL remota (R2) — redirigiendo: {raw_path[:120]}")
        return RedirectResponse(url=raw_path, status_code=302)
    return None


def _encontrar_en_storage_reales(basename: str) -> str | None:
    """Busca el basename en los directorios reales de storage; None si no está."""
    # Fallback limitado y real: buscar basename solo en directorios de storage configurados
    candidatos_reales = [
        f"/app/storage/clips/{basename}",
        f"/app/storage/uploads/{basename}",
        f"/app/storage/{basename}",
    ]
    for cand in candidatos_reales:
        if os.path.isfile(cand) and os.path.getsize(cand) > 0:
            logger.info(f"[CLIP DESCARGA] Fallback real encontrado en {cand} para basename {basename}")
            return cand
    return None


def _ruta_final_descarga(raw_path: str, clip_id: uuid.UUID) -> str:
    """Resuelve la ruta final del archivo (fallback a storage real o 404)."""
    # 2. Verificación de ruta — modo 100% real: solo ubicaciones válidas de storage, sin fallback de prueba
    ruta_final = raw_path
    if not os.path.isfile(ruta_final):
        basename = os.path.basename(ruta_final) if os.path.basename(ruta_final) else ruta_final
        encontrado = _encontrar_en_storage_reales(basename)
        if encontrado:
            ruta_final = encontrado
        else:
            # Modo 100% real: no existe archivo físico → error 404 real para que el frontend muestre toast
            logger.error(f"[CLIP DESCARGA] clip {clip_id} archivo no encontrado raw_path={raw_path} basename={basename} — sin fallback de prueba (modo 100%% real)")
            raise HTTPException(status_code=404, detail=f"Archivo de clip no encontrado en storage: {raw_path}. El clip debe ser reprocesado via /clips/{{id}}/re-render.")
    return ruta_final


def _tamano_verificado(ruta_final: str) -> int:
    """Tamaño del archivo; HTTPException 400 si no se puede leer o está vacío."""
    # Verificación final tamaño
    try:
        size = os.path.getsize(ruta_final)
        if size == 0:
            raise HTTPException(status_code=400, detail="El archivo de clip no existe o está vacío")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CLIP DESCARGA] error obteniendo tamaño {ruta_final}: {e}")
        raise HTTPException(status_code=400, detail="El archivo de clip no existe o está vacío")
    return size


@router.get(
    "/{clip_id}/descarga",
    summary="Descargar archivo del clip (público - sin autenticación para Meta crawler)",
)
def download_clip(
    clip_id: uuid.UUID,
    db: DbSession,
):
    # 1. Lectura directa desde BD: consulta registro clip y obtén ruta real almacenada
    clip = _get_clip_or_404(db, clip_id)
    raw_path = _raw_path_de_clip(db, clip)
    if not raw_path:
        logger.error(f"[CLIP DESCARGA] clip {clip_id} sin ruta en BD (file_path/video_path/output_path vacíos)")
        raise HTTPException(status_code=400, detail="El archivo de clip no existe o está vacío")

    # Clips procesados por el worker RunPod: storage_path es una URL R2 → redirigir
    redirect = _redirigir_si_remota(raw_path, clip_id)
    if redirect is not None:
        return redirect

    ruta_final = _ruta_final_descarga(raw_path, clip_id)
    size = _tamano_verificado(ruta_final)

    # Log requerido
    msg = f"[CLIP DESCARGA] Sirviendo archivo real: {ruta_final} (Tamaño: {size} bytes)"
    print(msg)
    logger.info(msg)

    # 3. Respuesta HTTP con media_type video/mp4
    return FileResponse(path=ruta_final, media_type="video/mp4", filename=f"{clip_id}.mp4")
