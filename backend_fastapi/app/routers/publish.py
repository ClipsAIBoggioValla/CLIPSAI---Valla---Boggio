from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse

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

    try:
        from ..services.publish_service import publish_clip_task

        background_tasks.add_task(publish_clip_task, clip.id, platform, payload.caption, payload.webhook_override_url, str(current_user.id))

        clip.status = "PUBLISHING"
        try:
            clip.published_platform = platform
            clip.publication_status = "PUBLISHING"
        except Exception:
            pass
        db.commit()

        return PublishClipResponse(detail="Publicación encolada", clip_id=clip.id, status="PUBLISHING", platform=platform)
    except Exception as e:
        try:
            clip.status = "FAILED"
            db.add(clip)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{clip_id}/publish-stream",
    summary="SSE stream estado publicación (PUBLISHING → PUBLISHED/FAILED)",
)
async def publish_stream(
    clip_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
):
    # Ownership check con la sesión del request
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)
    user_id = current_user.id

    async def event_gen():
        from ..database import SessionLocal as _SessionLocal

        seen_status: str | None = None
        # Polling 1s, timeout 90s para evitar conexión infinita
        for _ in range(90):
            sdb = _SessionLocal()
            try:
                c = sdb.get(Clip, clip_id)
                if c is None:
                    yield f"event: error\ndata: {json.dumps({'detail': 'Clip no encontrado'}, ensure_ascii=False)}\n\n"
                    return
                # Re-validar ownership por si cambia
                ok_owner = False
                if c.video_id is not None:
                    v = sdb.get(Video, c.video_id)
                    if v is not None and str(v.user_id) == str(user_id):
                        ok_owner = True
                if not ok_owner and c.job_id is not None:
                    from ..models import Job

                    j = sdb.get(Job, c.job_id)
                    if j is not None:
                        v2 = sdb.get(Video, j.video_id)
                        if v2 is not None and str(v2.user_id) == str(user_id):
                            ok_owner = True
                if not ok_owner:
                    yield f"event: error\ndata: {json.dumps({'detail': 'No autorizado'}, ensure_ascii=False)}\n\n"
                    return

                status_val = str(getattr(c, "status", "") or "").upper()
                pub_status = str(getattr(c, "publication_status", "") or "").upper()
                platform = getattr(c, "published_platform", None) or getattr(c, "social_network", None)
                # Normalizar: PUBLISHING/PUBLISHED/FAILED
                effective = pub_status or status_val
                payload = {
                    "clip_id": str(c.id),
                    "status": status_val,
                    "publication_status": pub_status,
                    "published_platform": platform,
                    "social_post_id": getattr(c, "social_post_id", None),
                    "social_post_url": getattr(c, "social_post_url", None),
                }
                # Solo emitir si cambia o primera vez
                if effective != seen_status:
                    seen_status = effective
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                # Condiciones de cierre
                if effective in ("PUBLISHED", "FAILED") or status_val in ("PUBLISHED", "FAILED"):
                    yield "event: done\ndata: {}\n\n"
                    return
                if status_val == "PUBLISHED" or pub_status == "PUBLISHED":
                    yield "event: done\ndata: {}\n\n"
                    return
            finally:
                try:
                    sdb.close()
                except Exception:
                    pass
            await asyncio.sleep(1.0)
        # Timeout: enviar último estado
        yield "event: timeout\ndata: {}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
