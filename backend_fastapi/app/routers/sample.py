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

from ..deps import CurrentUser, DbSession
from ..models import Job, Video
from ..schemas import JobResponse

router = APIRouter(prefix="/videos", tags=["videos"])


def _muestra_de_entorno() -> Path | None:
    """Ruta de SAMPLE_VIDEO_PATH si apunta a un archivo existente."""
    env_path = os.getenv("SAMPLE_VIDEO_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p
    return None


def _muestra_de_parents() -> Path | None:
    """sample.mp4 buscado en backend_fastapi/storage/sample desde los parents."""
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        candidate = parent / "backend_fastapi" / "storage" / "sample" / "sample.mp4"
        if candidate.is_file():
            return candidate
    return None


def _muestra_de_fallback() -> Path | None:
    """sample.mp4 bajo el directorio de trabajo actual, si existe."""
    fallback = Path.cwd() / "backend_fastapi" / "storage" / "sample" / "sample.mp4"
    if fallback.is_file():
        return fallback
    return None


def _muestra_esperada() -> Path:
    """Ruta esperada del sample (raíz del sistema de archivos) para el error descriptivo."""
    return Path(__file__).resolve().parents[-1] / "backend_fastapi" / "storage" / "sample" / "sample.mp4"


def _get_sample_video_path() -> Path:
    """Resuelve la ruta del video de muestra."""
    por_entorno = _muestra_de_entorno()
    if por_entorno is not None:
        return por_entorno
    por_parents = _muestra_de_parents()
    if por_parents is not None:
        return por_parents
    por_fallback = _muestra_de_fallback()
    if por_fallback is not None:
        return por_fallback
    return _muestra_esperada()


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
    # Stateless (Koyeb/Cloud Run): storage efímero en /tmp — sin disco persistente.
    upload_dir = Path(os.getenv("UPLOAD_DIR", "/tmp/clipsai/uploads"))
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

    from .jobs import create_job_for_video

    return create_job_for_video(db, entity.id, background_tasks, video=entity, is_admin=current_user.is_admin)
