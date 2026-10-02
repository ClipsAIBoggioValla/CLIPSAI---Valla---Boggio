"""Router POST /videos — subida de video + transcripcion (Issue 4)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from pydantic import BaseModel, model_validator
from sqlalchemy import select

from ..deps import CurrentUser, DbSession
from ..models import Video
from ..schemas import VideoResponse

router = APIRouter(prefix="/videos", tags=["videos"])
upload_url_router = APIRouter(prefix="/api/videos", tags=["videos"])


class UploadUrlRequest(BaseModel):
    file_name: str
    file_type: str


class ProcessVideoRequest(BaseModel):
    file_key: str | None = None
    video_url: str | None = None
    transcription_url: str | None = None
    transcription_text: str | None = None
    video_id: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "ProcessVideoRequest":
        has_file_key = bool(self.file_key and self.file_key.strip())
        has_video_url = bool(self.video_url and self.video_url.strip())
        if has_file_key == has_video_url:
            raise ValueError("Envía exactamente uno de file_key o video_url")
        if self.transcription_url and self.transcription_text is not None:
            raise ValueError("Envía transcription_url o transcription_text, no ambos")
        return self


def get_s3_client():
    # Import lazily so the FastAPI app can still load in environments that have
    # not installed the optional S3 dependency yet.
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
        region_name=os.getenv("AWS_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


@upload_url_router.post("/upload-url", summary="Generar URL prefirmada para subir un video")
async def generate_upload_url(payload: UploadUrlRequest) -> dict[str, str]:
    try:
        s3_client = get_s3_client()
        bucket_name = os.getenv("BUCKET_NAME", "clipsai-videos")

        file_extension = os.path.splitext(payload.file_name)[1]
        file_key = f"uploads/{uuid.uuid4()}{file_extension}"

        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": bucket_name,
                "Key": file_key,
                "ContentType": payload.file_type,
            },
            ExpiresIn=900,
        )

        return {"upload_url": presigned_url, "file_key": file_key}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar la presigned URL: {str(exc)}",
        ) from exc


@upload_url_router.post("/process", summary="Procesar un video almacenado en R2 mediante RunPod")
def process_video(payload: ProcessVideoRequest) -> dict[str, Any]:
    video_url = payload.video_url.strip() if payload.video_url else ""

    if payload.file_key:
        try:
            s3_client = get_s3_client()
            video_url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": os.getenv("BUCKET_NAME", "clipsai-videos"),
                    "Key": payload.file_key.strip(),
                },
                ExpiresIn=3600,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Error al generar la presigned URL de lectura: {str(exc)}",
            ) from exc

    try:
        from ..services.runpod_service import RunPodError, process_video_via_runpod

        return process_video_via_runpod(
            video_url,
            transcription_url=payload.transcription_url,
            transcription_text=payload.transcription_text,
            video_id=payload.video_id,
        )
    except RunPodError as exc:
        message = str(exc)
        status_code = 504 if "timeout" in message.lower() or "no terminó" in message.lower() else 502
        raise HTTPException(status_code=status_code, detail=f"Error al procesar con RunPod: {message}") from exc

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
    transcription: UploadFile | None = File(None, description="Archivo de transcripcion (opcional)"),
) -> Video:
    if video is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Se requiere archivo de video")

    video_ext = _validate_extension(video.filename, ALLOWED_VIDEO_EXTS, "video")
    transcript_ext: str | None = None
    if transcription is not None:
        transcript_ext = _validate_extension(transcription.filename, ALLOWED_TRANSCRIPT_EXTS, "transcription")

    upload_dir = _get_upload_dir()
    video_dest = upload_dir / f"{uuid.uuid4().hex}{video_ext}"
    transcript_dest: Path | None = None
    if transcription is not None and transcript_ext is not None:
        transcript_dest = upload_dir / f"{uuid.uuid4().hex}{transcript_ext}"

    try:
        await _save_upload_file(video, video_dest)
        if transcription is not None and transcript_dest is not None:
            await _save_upload_file(transcription, transcript_dest)
    except HTTPException:
        for p in (video_dest, transcript_dest) if transcript_dest else (video_dest,):
            if p is None:
                continue
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        raise
    except Exception as exc:
        for p in (video_dest, transcript_dest) if transcript_dest else (video_dest,):
            if p is None:
                continue
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
        if transcription is not None:
            try:
                await transcription.close()
            except Exception:
                pass

    transcript_text: str | None = None
    if transcript_dest is not None:
        try:
            transcript_text = transcript_dest.read_text(encoding="utf-8")[:50000]
        except Exception:
            transcript_text = None

    entity = Video(
        user_id=current_user.id,
        filename=video.filename or video_dest.name,
        filepath=str(video_dest),
        transcription_filepath=str(transcript_dest) if transcript_dest else None,
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
