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

        refreshed: Job | None = db.get(Job, job_id)
        if refreshed is None:
            return
        refreshed.result_metadata = result
        refreshed.status = JobStatus.COMPLETED.value
        refreshed.error_message = None
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
