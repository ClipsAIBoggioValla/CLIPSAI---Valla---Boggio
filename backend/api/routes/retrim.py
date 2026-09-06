from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend_fastapi.app.database import get_db
from backend_fastapi.app.deps import get_current_user
from backend_fastapi.app.models import Clip, Job, Video

router = APIRouter(prefix="/clips", tags=["clips-retrim"])


class RetrimRequest(BaseModel):
    start_time: float = Field(..., ge=0, description="Nuevo inicio en segundos")
    end_time: float = Field(..., ge=0, description="Nuevo fin en segundos")

    def validate_range(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("end_time debe ser > start_time")
        if self.end_time - self.start_time < 5:
            raise ValueError("Duración mínima 5s")
        if self.end_time - self.start_time > 90:
            raise ValueError("Duración máxima 90s")


class RetrimResponse(BaseModel):
    clip_id: str
    start_time: float
    end_time: float
    duration: float
    status: str = "ready"
    file_path: str | None = None


def _assert_ownership_and_get_clip(db, clip_id: str, user_id: uuid.UUID) -> Clip:
    try:
        cid = uuid.UUID(clip_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="clip_id inválido")
    clip = db.execute(select(Clip).where(Clip.id == cid)).scalar_one_or_none()
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip no encontrado")
    job = db.execute(select(Job).where(Job.id == clip.job_id)).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    video = db.execute(select(Video).where(Video.id == job.video_id)).scalar_one_or_none()
    if video is None or video.user_id != user_id:
        raise HTTPException(status_code=404, detail="Clip no encontrado")
    return clip


@router.post("/{clip_id}/retrim", response_model=RetrimResponse)
async def retrim_clip(
    clip_id: str,
    body: RetrimRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        body.validate_range()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    clip = _assert_ownership_and_get_clip(db, clip_id, current_user.id)

    job = db.execute(select(Job).where(Job.id == clip.job_id)).scalar_one_or_none()
    video = db.execute(select(Video).where(Video.id == job.video_id)).scalar_one_or_none() if job else None

    src_candidates = []
    if clip.storage_path and Path(clip.storage_path).exists():
        src_candidates.append(Path(clip.storage_path))
    if clip.video and hasattr(clip.video, "filepath") and clip.video.filepath:
        src_candidates.append(Path(clip.video.filepath))
    if video and video.filepath:
        src_candidates.append(Path(video.filepath))
    if job and job.video and hasattr(job.video, "filepath"):
        src_candidates.append(Path(job.video.filepath))

    src = None
    for p in src_candidates:
        if p and p.exists():
            src = p
            break
    if src is None and src_candidates:
        src = src_candidates[0]
    if src is None or not src.exists():
        raise HTTPException(status_code=404, detail=f"Video origen no encontrado para re-trim: {src}")

    duration = body.end_time - body.start_time
    out_dir = Path("storage/retrims")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{clip_id}_retrim_{int(body.start_time)}_{int(body.end_time)}.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(body.start_time),
        "-i",
        str(src),
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            detail = result.stderr.decode(errors="ignore")[:600] if result.stderr else "FFmpeg error"
            raise HTTPException(status_code=500, detail=f"FFmpeg re-trim falló: {detail}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"FFmpeg no instalado: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise HTTPException(status_code=504, detail="Timeout FFmpeg re-trim 120s") from e

    if not out_path.exists():
        raise HTTPException(status_code=500, detail="Re-trim no produjo archivo")

    clip.start_time = float(body.start_time)
    clip.end_time = float(body.end_time)
    clip.storage_path = str(out_path)
    db.commit()
    db.refresh(clip)

    return RetrimResponse(
        clip_id=str(clip.id),
        start_time=float(clip.start_time),
        end_time=float(clip.end_time),
        duration=float(duration),
        status=clip.status or "ready",
        file_path=str(out_path),
    )
