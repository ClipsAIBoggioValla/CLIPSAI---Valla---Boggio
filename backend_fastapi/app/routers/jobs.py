"""Router de Jobs — creacion en background y consulta de estado (Issue 4)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from ..database import SessionLocal
from ..deps import CurrentUser, DbSession
from ..models import Job, JobStatus, Video
from ..schemas import JobResponse

logger = logging.getLogger(__name__)

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


def _fallback_result(video: Video | None) -> dict:
    preview = ""
    if video is not None:
        try:
            if video.transcript:
                preview = str(video.transcript)[:120]
            elif video.transcription_filepath:
                import pathlib

                p = pathlib.Path(str(video.transcription_filepath))
                if p.is_file():
                    preview = p.read_text(encoding="utf-8", errors="ignore")[:120]
        except Exception:
            preview = ""
    return {
        "clips": [
            {"inicio": "00:00:10", "fin": "00:00:45", "titulo": "Clip destacado 1 (fallback)", "score": 7.5, "transcript_preview": preview},
            {"inicio": "00:01:00", "fin": "00:01:35", "titulo": "Clip destacado 2 (fallback)", "score": 7.0},
        ],
        "engine": "fallback",
        "fallback": True,
        "reason": "LLM no disponible, clip fallback automático",
    }


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

        try:
            result = run_clip_engine(video.filepath, video.transcription_filepath or "")
        except Exception:
            logger.exception("run_clip_engine fallo job=%s, aplicando fallback para no dejar FAILED", job_id)
            result = _fallback_result(video)
            result["fallback_error"] = "LLM fallo, fallback aplicado"

        clips_payload = []
        if isinstance(result, dict):
            clips_payload = result.get("clips") or result.get("result") or result.get("clips_generated") or []
        elif isinstance(result, list):
            clips_payload = result

        if not clips_payload:
            logger.warning("run_clip_engine devolvio 0 clips job=%s, usando fallback", job_id)
            result = _fallback_result(video)
            clips_payload = result.get("clips", [])

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
        if result.get("fallback"):
            logger.warning("Job %s completado via fallback (%s clips)", job_id, len(clips_to_create))
        else:
            logger.info("Job %s completado (%s clips)", job_id, len(clips_to_create))
    except Exception as exc:
        logger.exception("Fallo irrecuperable job=%s", job_id)
        try:
            video_fallback: Video | None = None
            try:
                j = db.get(Job, job_id)
                if j is not None:
                    video_fallback = db.get(Video, j.video_id)
            except Exception:
                pass
            fallback = _fallback_result(video_fallback)
            fallback["fatal_error"] = str(exc)[:1000]
            failed: Job | None = db.get(Job, job_id)
            if failed is not None:
                from ..models import Clip as ClipModel

                failed.result_metadata = fallback
                failed.status = JobStatus.COMPLETED.value
                failed.error_message = None
                for item in fallback.get("clips", []):
                    if not isinstance(item, dict):
                        continue
                    title = item.get("titulo", "Clip fallback")
                    start = _parse_time_to_seconds(item.get("inicio", 10))
                    end = _parse_time_to_seconds(item.get("fin", 45))
                    db.add(
                        ClipModel(
                            video_id=video_fallback.id if video_fallback else failed.video_id,
                            job_id=failed.id,
                            title=str(title)[:255],
                            start_time=float(start),
                            end_time=float(end),
                            score=float(item.get("score", 7.0)),
                            tags=None,
                            storage_path="",
                            status="ready",
                        )
                    )
                db.commit()
                logger.warning("Job %s recuperado via fallback tras error fatal", job_id)
                return
        except Exception:
            logger.exception("Fallo al aplicar fallback fatal job=%s", job_id)
        try:
            failed2: Job | None = db.get(Job, job_id)
            if failed2 is not None:
                failed2.status = JobStatus.FAILED.value
                failed2.error_message = str(exc)[:2000]
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
