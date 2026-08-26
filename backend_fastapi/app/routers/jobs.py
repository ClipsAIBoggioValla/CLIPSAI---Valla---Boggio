"""Router de Jobs — creacion en background y consulta de estado (Issue 4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from ..database import SessionLocal
from ..deps import CurrentUser, DbSession
from ..models import Job, JobStatus, Video
from ..schemas import JobResponse

router = APIRouter(tags=["jobs"])


def _parse_time_to_seconds(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return 0.0
    try:
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
        return float(s)
    except Exception:
        return 0.0


def _run_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job: Job | None = db.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.PROCESSING.value
        db.commit()

        video: Video | None = db.get(Video, job.video_id)
        if video is None:
            raise RuntimeError("Video asociado no encontrado")

        from ..services.engine import run_clip_engine

        result = run_clip_engine(video.filepath, video.transcription_filepath or "")

        clips_payload = []
        if isinstance(result, dict):
            clips_payload = result.get("clips") or result.get("result") or result.get("clips_generated") or []
        elif isinstance(result, list):
            clips_payload = result

        from ..models import Clip

        clips_to_create = []
        for item in clips_payload:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("titulo") or item.get("titulo_sugerido") or item.get("name") or "Clip"
            start_raw = item.get("start_time", item.get("inicio", item.get("start", 0)))
            end_raw = item.get("end_time", item.get("fin", item.get("end", 10)))
            start = _parse_time_to_seconds(start_raw)
            end = _parse_time_to_seconds(end_raw)
            if end <= start:
                end = start + 30.0
            score = item.get("score")
            try:
                score_val = float(score) if score is not None else None
            except Exception:
                score_val = None
            tags = item.get("tags")
            if tags is not None and not isinstance(tags, list):
                tags = [str(tags)]
            storage = item.get("storage_path") or item.get("file_path") or item.get("path") or ""
            if not isinstance(storage, str):
                storage = str(storage) if storage is not None else ""
            storage = storage.strip() or ""

            clips_to_create.append(
                Clip(
                    video_id=video.id,
                    job_id=job.id,
                    title=str(title)[:255] if title else None,
                    start_time=float(start),
                    end_time=float(end),
                    score=score_val,
                    tags=tags,
                    storage_path=storage,
                    status="ready",
                )
            )

        refreshed: Job | None = db.get(Job, job_id)
        if refreshed is None:
            return
        refreshed.result_metadata = result
        refreshed.status = JobStatus.COMPLETED.value
        refreshed.error_message = None
        for c in clips_to_create:
            db.add(c)
        db.commit()
    except Exception as exc:
        try:
            failed: Job | None = db.get(Job, job_id)
            if failed is not None:
                failed.status = JobStatus.FAILED.value
                failed.error_message = str(exc)[:2000]
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


@router.post(
    "/videos/{video_id}/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear Job de procesamiento para un video",
)
def create_job(
    video_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> Job:
    video: Video | None = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado")
    if video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para este video")

    job = Job(
        video_id=video.id,
        status=JobStatus.PENDING.value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_run_job, job.id)

    return job


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="Consultar estado de un Job",
)
def get_job(
    job_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Job:
    job: Job | None = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")

    video: Video | None = db.get(Video, job.video_id)
    if video is None or video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")

    return job
