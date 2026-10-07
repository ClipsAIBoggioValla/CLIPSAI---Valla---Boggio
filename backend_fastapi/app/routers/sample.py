"""Router POST /videos/sample — video de muestra para evaluación (Issue 34).

Permite probar el flujo completo sin subir un video pesado. El video de muestra
debe estar en backend_fastapi/storage/sample/sample.mp4 (o configurado vía
SAMPLE_VIDEO_PATH).
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from ..database import SessionLocal
from ..deps import CurrentUser, DbSession
from ..models import Job, JobStatus, Video
from ..schemas import JobResponse

router = APIRouter(tags=["videos"])


def _get_sample_video_path() -> Path:
    """Resuelve la ruta del video de muestra."""
    env_path = os.getenv("SAMPLE_VIDEO_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    # Ruta por defecto: backend_fastapi/storage/sample/sample.mp4
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        candidate = parent / "backend_fastapi" / "storage" / "sample" / "sample.mp4"
        if candidate.is_file():
            return candidate

    # Fallback: buscar en el directorio de trabajo actual
    fallback = Path.cwd() / "backend_fastapi" / "storage" / "sample" / "sample.mp4"
    if fallback.is_file():
        return fallback

    return candidate  # Retorna la ruta esperada aunque no exista (para error descriptivo)


@router.post(
    "/sample",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear job con video de muestra",
)
def create_sample_job(
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> Job:
    sample_path = _get_sample_video_path()

    if not sample_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Video de muestra no encontrado en {sample_path}. "
                "Colocá un archivo sample.mp4 en esa ubicación o configurá SAMPLE_VIDEO_PATH."
            ),
        )

    # Copiar el video de muestra al directorio de uploads del usuario
    upload_dir = Path(os.getenv("UPLOAD_DIR", "storage/uploads"))
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        upload_dir = Path.cwd() / "storage" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / f"sample_{uuid.uuid4().hex}.mp4"
    shutil.copy2(sample_path, dest)

    # Crear registro de video
    entity = Video(
        user_id=current_user.id,
        filename="sample.mp4",
        filepath=str(dest),
        transcript=None,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    # Crear job
    job = Job(
        video_id=entity.id,
        status=JobStatus.PENDING.value,
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Ejecutar en background
    try:
        from .jobs import run_job_safely

        background_tasks.add_task(run_job_safely, str(job.id))
    except Exception:
        from .jobs import _run_job

        background_tasks.add_task(_run_job, job.id)

    return job