"""Router de Clips — CRUD + descarga + biblioteca (Issue 5 + Issue 16)."""

from __future__ import annotations

import math
import os
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession
from ..models import Clip, Video
from ..schemas import ClipListItem, ClipListResponse, ClipResponse, ClipUpdate

router = APIRouter(prefix="/clips", tags=["clips"])


def _get_clip_or_404(db: DbSession, clip_id: uuid.UUID) -> Clip:
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    return clip


def _assert_ownership(db: DbSession, clip: Clip, current_user) -> None:
    video = None
    if clip.video_id is not None:
        video = db.get(Video, clip.video_id)
    if video is None and clip.job_id is not None:
        from ..models import Job

        job = db.get(Job, clip.job_id)
        if job is not None:
            video = db.get(Video, job.video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    if video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para este clip")


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
) -> ClipListResponse:
    from ..models import Job

    base = (
        select(Clip, Video.transcript.label("video_transcript"))
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == current_user.id)
    )

    if q is not None and q.strip() != "":
        pattern = f"%{q.strip()}%"
        base = base.where((Clip.title.ilike(pattern)) | (Video.transcript.ilike(pattern)))

    if min_score is not None:
        base = base.where(Clip.score >= min_score)

    if video_id is not None:
        base = base.where((Clip.video_id == video_id) | (Job.video_id == video_id))

    if status is not None:
        base = base.where(Clip.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total: int = db.scalar(count_stmt) or 0
    total_pages: int = math.ceil(total / limit) if total > 0 else 0

    if sort_by == "created_at_desc":
        base = base.order_by(Clip.created_at.desc())
    elif sort_by == "created_at_asc":
        base = base.order_by(Clip.created_at.asc())
    elif sort_by == "score_desc":
        base = base.order_by(Clip.score.desc().nulls_last(), Clip.created_at.desc())
    elif sort_by == "score_asc":
        base = base.order_by(Clip.score.asc().nulls_last(), Clip.created_at.desc())

    base = base.offset((page - 1) * limit).limit(limit)

    rows = db.execute(base).all()

    items: list[ClipListItem] = []
    for clip, video_transcript in rows:
        transcript: str | None = None
        if video_transcript:
            transcript = str(video_transcript)[:500]
        items.append(
            ClipListItem(
                id=clip.id,
                job_id=clip.job_id,
                title=clip.title,
                score=clip.score,
                start_time=clip.start_time,
                end_time=clip.end_time,
                transcript=transcript,
                created_at=clip.created_at,
            )
        )

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
) -> Clip:
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)
    return clip


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
) -> Clip:
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
    return clip


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

    for attr in ("storage_path", "file_path"):
        p = getattr(clip, attr, None)
        if p:
            try:
                path = Path(str(p))
                if path.is_file():
                    path.unlink()
            except Exception:
                pass

    db.delete(clip)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{clip_id}/descarga",
    summary="Descargar archivo del clip",
)
def download_clip(
    clip_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)

    candidates: list[Path] = []
    for attr in ("storage_path", "file_path"):
        v = getattr(clip, attr, None)
        if v:
            candidates.append(Path(str(v)))

    video = None
    if clip.video_id is not None:
        video = db.get(Video, clip.video_id)
    if video is not None:
        for attr in ("filepath", "file_path"):
            v = getattr(video, attr, None)
            if v:
                candidates.append(Path(str(v)))
        tp = getattr(video, "transcription_filepath", None)
        if tp:
            candidates.append(Path(str(tp)))

    for path in candidates:
        if path.is_file():
            filename = path.name or f"{clip.id}.mp4"
            media_type = "application/octet-stream"
            if path.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv"):
                media_type = "video/mp4"
            elif path.suffix.lower() in (".txt", ".srt", ".vtt"):
                media_type = "text/plain"
            return FileResponse(
                path=str(path),
                filename=filename,
                media_type=media_type,
            )

    tmp = Path(os.getenv("TMPDIR", "/tmp")) / f"clip_{clip.id}.txt"
    try:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            f"Clip {clip.id}\nTitle: {clip.title or ''}\nStart: {clip.start_time}\nEnd: {clip.end_time}\nStatus: {clip.status}\n",
            encoding="utf-8",
        )
        return FileResponse(path=str(tmp), filename=f"{clip.id}.txt", media_type="text/plain")
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo del clip no encontrado")
