"""Router de Clips — CRUD + descarga (Issue 5)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from ..deps import CurrentUser, DbSession
from ..models import Clip, Video
from ..schemas import ClipResponse, ClipUpdate

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
    response_model=list[ClipResponse],
    summary="Listar clips del usuario (filtros opcionales)",
)
def list_clips(
    db: DbSession,
    current_user: CurrentUser,
    video_id: Optional[uuid.UUID] = Query(default=None, description="Filtrar por video"),
    status: Optional[str] = Query(default=None, description="Filtrar por status"),
) -> list[Clip]:
    from ..models import Job

    q = (
        select(Clip)
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == current_user.id)
    )
    if video_id is not None:
        q = q.where((Clip.video_id == video_id) | (Job.video_id == video_id))
    if status is not None:
        q = q.where(Clip.status == status)
    q = q.order_by(Clip.created_at.desc())
    rows = db.execute(q).scalars().all()
    return list(rows)


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
