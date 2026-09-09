from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from ..deps import CurrentUser, DbSession
from ..models import Clip, Video
from ..schemas import PublishClipRequest, PublishClipResponse

router = APIRouter(prefix="/clips", tags=["clips"])

ALLOWED_PLATFORMS = {"tiktok", "instagram", "youtube", "webhook"}


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


@router.post(
    "/{clip_id}/publicar",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PublishClipResponse,
    summary="Publicar clip en red social (async)",
)
@router.post(
    "/{clip_id}/publish",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PublishClipResponse,
    summary="Publicar clip en red social (async) - alias",
    include_in_schema=False,
)
def publish_clip(
    clip_id: uuid.UUID,
    payload: PublishClipRequest,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    platform = (payload.platform or "").strip().lower()
    if platform not in ALLOWED_PLATFORMS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"platform debe ser una de {sorted(ALLOWED_PLATFORMS)}")

    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)

    from ..services.publish_service import publish_clip_task

    background_tasks.add_task(publish_clip_task, clip.id, platform, payload.caption, payload.webhook_override_url)

    clip.status = "PUBLISHING"
    try:
        clip.published_platform = platform
        clip.publication_status = "PUBLISHING"
    except Exception:
        pass
    db.commit()

    return PublishClipResponse(detail="Publicación encolada", clip_id=clip.id, status="PUBLISHING", platform=platform)
