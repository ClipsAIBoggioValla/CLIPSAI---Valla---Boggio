"""Helpers compartidos entre routers que operan sobre Clip."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status

from ..deps import DbSession
from ..models import Clip, Video


def get_clip_or_404(db: DbSession, clip_id: uuid.UUID) -> Clip:
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    return clip


def resolve_clip_video(db: DbSession, clip: Clip) -> Any | None:
    """Dado un clip, devuelve el Video asociado (puede venir de video_id directo o via job)."""
    video = None
    if clip.video_id is not None:
        video = db.get(Video, clip.video_id)
    if video is None and clip.job_id is not None:
        from ..models import Job

        job = db.get(Job, clip.job_id)
        if job is not None:
            video = db.get(Video, job.video_id)
    return video


def assert_clip_ownership(db: DbSession, clip: Clip, current_user) -> None:
    video = resolve_clip_video(db, clip)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    if video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para este clip")
