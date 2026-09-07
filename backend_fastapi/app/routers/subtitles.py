from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from ..deps import CurrentUser, DbSession
from ..models import Clip
from ..schemas.clip import ClipResponse

router = APIRouter(prefix="/clips", tags=["subtitles"])


def _get_clip_or_404(db: DbSession, clip_id: uuid.UUID) -> Clip:
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    return clip


def _assert_ownership(db: DbSession, clip: Clip, current_user) -> None:
    video = None
    if clip.video_id is not None:
        from ..models import Video

        video = db.get(Video, clip.video_id)
    if video is None and clip.job_id is not None:
        from ..models import Job

        job = db.get(Job, clip.job_id)
        if job is not None:
            from ..models import Video

            video = db.get(Video, job.video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    if video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para este clip")


@router.post(
    "/{clip_id}/subtitles",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Disparar subtitulado burned-in ASS para un clip",
)
def trigger_subtitles(
    clip_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> dict:
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)
    if clip.status == "PROCESSING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Clip ya en procesamiento")
    from ..tasks.subtitle_pipeline import run_subtitle_pipeline

    background_tasks.add_task(run_subtitle_pipeline, clip.id)
    return {
        "clip_id": str(clip.id),
        "status": "PROCESSING",
        "message": "Subtitulado iniciado en background",
    }


@router.get(
    "/{clip_id}/subtitles/status",
    response_model=ClipResponse,
    summary="Consultar estado de subtitulado (proxy a clip status)",
)
def get_subtitle_status(
    clip_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Clip:
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)
    return clip
