"""Router POST /videos — subida de video + transcripcion (Issue 4)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from sqlalchemy import select

from ..deps import CurrentUser, DbSession
from ..models import Video
from ..schemas import VideoResponse

router = APIRouter(prefix="/videos", tags=["videos"])

ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".avi"}
ALLOWED_TRANSCRIPT_EXTS = {".txt", ".srt"}
MAX_FILE_SIZE = 500 * 1024 * 1024


def _get_upload_dir() -> Path:
    base = Path(os.getenv("UPLOAD_DIR", "/storage/uploads"))
    try:
        base.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        base = Path.cwd() / "storage" / "uploads"
        base.mkdir(parents=True, exist_ok=True)
    return base


def _validate_extension(filename: str | None, allowed: set[str], label: str) -> str:
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label}: nombre de archivo requerido")
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label}: extension no permitida '{ext}'. Permitidas: {', '.join(sorted(allowed))}",
        )
    return ext


async def _save_upload_file(upload: UploadFile, dest: Path) -> None:
    size = 0
    with dest.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                out.close()
                try:
                    dest.unlink()
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Archivo '{upload.filename}' supera el tamaño máximo de 500MB",
                )
            out.write(chunk)


@router.post(
    "",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir video y transcripcion",
)
async def upload_video(
    db: DbSession,
    current_user: CurrentUser,
    video: UploadFile = File(..., description="Archivo de video"),
    transcription: UploadFile = File(..., description="Archivo de transcripcion"),
) -> Video:
    if video is None or transcription is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Se requieren ambos archivos: video y transcription")

    video_ext = _validate_extension(video.filename, ALLOWED_VIDEO_EXTS, "video")
    transcript_ext = _validate_extension(transcription.filename, ALLOWED_TRANSCRIPT_EXTS, "transcription")

    upload_dir = _get_upload_dir()
    video_dest = upload_dir / f"{uuid.uuid4().hex}{video_ext}"
    transcript_dest = upload_dir / f"{uuid.uuid4().hex}{transcript_ext}"

    try:
        await _save_upload_file(video, video_dest)
        await _save_upload_file(transcription, transcript_dest)
    except HTTPException:
        for p in (video_dest, transcript_dest):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        raise
    except Exception as exc:
        for p in (video_dest, transcript_dest):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error al guardar archivos: {exc}") from exc
    finally:
        try:
            await video.close()
        except Exception:
            pass
        try:
            await transcription.close()
        except Exception:
            pass

    try:
        transcript_text = transcript_dest.read_text(encoding="utf-8")[:50000]
    except Exception:
        transcript_text = None

    entity = Video(
        user_id=current_user.id,
        filename=video.filename or video_dest.name,
        filepath=str(video_dest),
        transcription_filepath=str(transcript_dest),
        transcript=transcript_text,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.get(
    "",
    response_model=list[VideoResponse],
    summary="Listar videos del usuario autenticado",
)
def list_videos(
    db: DbSession,
    current_user: CurrentUser,
) -> list[Video]:
    rows = db.execute(select(Video).where(Video.user_id == current_user.id).order_by(Video.created_at.desc())).scalars().all()
    return list(rows)
