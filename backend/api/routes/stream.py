from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from backend.core.schemas import AutopilotJobStatus
from backend_fastapi.app.deps import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs-stream"])


class StreamEvent(BaseModel):
    progress: int
    status: str
    message: str | None = None
    job_id: str | None = None
    error: str | None = None


STATUS_MAP: dict[str, tuple[int, AutopilotJobStatus, str]] = {
    "pending": (0, AutopilotJobStatus.pending, "En cola"),
    "processing": (55, AutopilotJobStatus.scoring, "Procesando con IA"),
    "completed": (100, AutopilotJobStatus.completed, "Completado"),
    "failed": (100, AutopilotJobStatus.failed, "Falló"),
}


def _to_event(status_raw: str) -> StreamEvent:
    key = status_raw.lower()
    if key in STATUS_MAP:
        progress, autopilot_status, message = STATUS_MAP[key]
        return StreamEvent(progress=progress, status=autopilot_status.value, message=message)
    try:
        autopilot = AutopilotJobStatus(key)
        return StreamEvent(progress=50, status=autopilot.value, message=autopilot.value)
    except ValueError:
        return StreamEvent(progress=0, status=key, message=key)


async def _progress_gen(job_id: str, user_id: uuid.UUID) -> AsyncIterator[str]:
    from backend_fastapi.app.database import SessionLocal
    from backend_fastapi.app.models import Job, Video

    seen: str | None = None
    while True:
        db = SessionLocal()
        try:
            try:
                jid = uuid.UUID(job_id)
            except ValueError:
                yield f"event: error\ndata: {json.dumps({'detail': 'job_id inválido'})}\n\n"
                return
            job = db.execute(select(Job).where(Job.id == jid)).scalar_one_or_none()
            if job is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'Job no encontrado'})}\n\n"
                return
            video = db.execute(select(Video).where(Video.id == job.video_id)).scalar_one_or_none()
            if video is None or video.user_id != user_id:
                yield f"event: error\ndata: {json.dumps({'detail': 'No autorizado'})}\n\n"
                return
            status_raw = str(job.status)
            if status_raw != seen:
                seen = status_raw
                ev = _to_event(status_raw)
                ev.job_id = str(job.id)
                if job.error_message:
                    ev.error = job.error_message
                yield f"data: {json.dumps(ev.model_dump(exclude_none=True), ensure_ascii=False)}\n\n"
                if status_raw.lower() in ("completed", "failed"):
                    yield "event: done\ndata: {}\n\n"
                    return
        finally:
            db.close()
        await asyncio.sleep(1.0)


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, current_user=Depends(get_current_user)):
    return StreamingResponse(
        _progress_gen(job_id, current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
