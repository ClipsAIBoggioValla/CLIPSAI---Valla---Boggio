"""Router POST /videos — subida de video + transcripcion (Issue 4)."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, status
from pydantic import BaseModel, model_validator
from sqlalchemy import select

from ..deps import CurrentUser, DbSession
from ..models import Video
from ..schemas import VideoFromUrlRequest, VideoResponse
from ..services.r2_service import get_r2_client
from ..services.ytdlp_service import (
    DownloadTooLarge,
    InvalidVideoUrl,
    VideoDownloadFailed,
    download_video_from_url,
)
from ..core.security.rate_limiter import RateLimitExceeded, RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])
upload_url_router = APIRouter(prefix="/api/videos", tags=["videos"])
limiter = RateLimiter(max_requests=10, window_seconds=60)


class UploadUrlRequest(BaseModel):
    file_name: str
    file_type: str


def _texto_no_vacio(valor: str | None) -> bool:
    """True si el valor es un string no vacío."""
    return bool(valor and valor.strip())


class ProcessVideoRequest(BaseModel):
    file_key: str | None = None
    video_url: str | None = None
    transcription_url: str | None = None
    transcription_text: str | None = None
    video_id: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "ProcessVideoRequest":
        if _texto_no_vacio(self.file_key) == _texto_no_vacio(self.video_url):
            raise ValueError("Envía exactamente uno de file_key o video_url")
        if self.transcription_url and self.transcription_text is not None:
            raise ValueError("Envía transcription_url o transcription_text, no ambos")
        return self


def get_s3_client():
    """Delegado al servicio centralizado de R2 (r2_service.get_r2_client)."""
    return get_r2_client()


@upload_url_router.post("/upload-url", summary="Generar URL prefirmada para subir un video")
async def generate_upload_url(payload: UploadUrlRequest, request: Request) -> dict[str, str]:
    client_key = request.client.host if request.client else "unknown"
    try:
        limiter.check(client_key)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail="Límite de 10 solicitudes por minuto excedido") from exc

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


def _presigned_get_url(payload: ProcessVideoRequest) -> str:
    """URL prefirmada de lectura del file_key; HTTPException 500 si falla."""
    try:
        s3_client = get_s3_client()
        return s3_client.generate_presigned_url(
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


def _procesar_via_runpod(payload: ProcessVideoRequest, video_url: str) -> dict[str, Any]:
    """Llama a RunPod; HTTPException 504/502 ante RunPodError."""
    from ..services.runpod_service import RunPodError, process_video_via_runpod

    try:
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


@upload_url_router.post("/process", summary="Procesar un video almacenado en R2 mediante RunPod")
def process_video(payload: ProcessVideoRequest) -> dict[str, Any]:
    video_url = payload.video_url.strip() if payload.video_url else ""

    if payload.file_key:
        video_url = _presigned_get_url(payload)

    return _procesar_via_runpod(payload, video_url)


def _descargar_video_desde_url(payload: VideoFromUrlRequest):
    try:
        return download_video_from_url(payload.url, _get_upload_dir(), MAX_FILE_SIZE)
    except InvalidVideoUrl as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DownloadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El video supera el tamaño máximo permitido de 500MB",
        ) from exc
    except VideoDownloadFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo descargar el video desde la URL indicada",
        ) from exc


@upload_url_router.post(
    "/from-url",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Descargar y registrar un video desde una URL pública",
)
def import_video_from_url(
    payload: VideoFromUrlRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Video:
    downloaded = _descargar_video_desde_url(payload)
    entity = Video(
        user_id=current_user.id,
        filename=downloaded.filename,
        filepath=str(downloaded.filepath),
        duration_seconds=downloaded.duration_seconds,
    )
    try:
        db.add(entity)
        db.commit()
        db.refresh(entity)
    except Exception as exc:
        db.rollback()
        _limpiar_archivos_subida(downloaded.filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar el video",
        ) from exc
    return entity

ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".avi"}
ALLOWED_TRANSCRIPT_EXTS = {".txt", ".srt"}
MAX_FILE_SIZE = 500 * 1024 * 1024


def _get_upload_dir() -> Path:
    # Stateless (Koyeb/Cloud Run): storage efímero en /tmp — sin disco persistente.
    base = Path(os.getenv("UPLOAD_DIR", "/tmp/clipsai/uploads"))
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


def _limpiar_archivos_subida(*destinos: Path | None) -> None:
    """Borra los archivos parciales si el guardado falló a mitad de camino."""
    for p in destinos:
        if p is None:
            continue
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


def _garantizar_espacio(upload_dir: Path) -> None:
    # Garantizar espacio antes de escribir en disco (evita [Errno 28] en Render)
    try:
        from ..services.storage_cleanup import ensure_disk_space
        ensure_disk_space(upload_dir, min_free_mb=500)
    except Exception as disk_err:
        logger.warning("[upload] ensure_disk_space falló (non-fatal): %s", disk_err)


async def _cerrar_uploads(video, transcription) -> None:
    """Cierra los uploads ignorando errores."""
    try:
        await video.close()
    except Exception:
        pass
    if transcription is not None:
        try:
            await transcription.close()
        except Exception:
            pass


async def _guardar_sin_limpieza(video: UploadFile, video_dest: Path, transcription: UploadFile | None, transcript_dest: Path | None) -> None:
    """Guarda video y transcripción en disco (lanza si falla)."""
    await _save_upload_file(video, video_dest)
    if transcription is not None and transcript_dest is not None:
        await _save_upload_file(transcription, transcript_dest)


async def _guardar_archivos(video: UploadFile, video_dest: Path, transcription: UploadFile | None, transcript_dest: Path | None) -> None:
    """Guarda video (+ transcripción) en disco y limpia los parciales si falla."""
    _garantizar_espacio(video_dest.parent)
    try:
        await _guardar_sin_limpieza(video, video_dest, transcription, transcript_dest)
    except HTTPException:
        _limpiar_archivos_subida(video_dest, transcript_dest)
        raise
    except Exception as exc:
        _limpiar_archivos_subida(video_dest, transcript_dest)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error al guardar archivos: {exc}") from exc
    finally:
        await _cerrar_uploads(video, transcription)


def _leer_transcript(transcript_dest: Path | None) -> str | None:
    """Lee el texto de la transcripción guardada (50k chars máx). None si falla."""
    if transcript_dest is None:
        return None
    try:
        return transcript_dest.read_text(encoding="utf-8")[:50000]
    except Exception:
        return None


def _borrar_transcript_local(transcript_dest: Path | None) -> None:
    """Borrar transcripción local: ya está en el campo `transcript` de la BD.

    El video se conserva (filepath) hasta que el job lo procese; se limpia luego
    por cleanup_storage cuando supere la antigüedad.
    """
    try:
        from ..services.storage_cleanup import delete_file_safe  # type: ignore
        if transcript_dest and transcript_dest.exists():
            delete_file_safe(transcript_dest, "transcript")
    except Exception:
        pass


def _destinos_de_subida(upload_dir: Path, video_ext: str, transcript_ext: str | None) -> tuple[Path, Path | None]:
    """Rutas destino del video y de la transcripción (esta última solo si hay archivo)."""
    video_dest = upload_dir / f"{uuid.uuid4().hex}{video_ext}"
    transcript_dest: Path | None = None
    if transcript_ext is not None:
        transcript_dest = upload_dir / f"{uuid.uuid4().hex}{transcript_ext}"
    return video_dest, transcript_dest


def _entidad_video(current_user, video: UploadFile, video_dest: Path, transcript_dest: Path | None) -> Video:
    """Entidad Video persistible desde los archivos subidos."""
    return Video(
        user_id=current_user.id,
        filename=video.filename or video_dest.name,
        filepath=str(video_dest),
        transcription_filepath=str(transcript_dest) if transcript_dest else None,
        transcript=_leer_transcript(transcript_dest),
    )


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
    video_dest, transcript_dest = _destinos_de_subida(upload_dir, video_ext, transcript_ext)

    await _guardar_archivos(video, video_dest, transcription, transcript_dest)

    entity = _entidad_video(current_user, video, video_dest, transcript_dest)
    db.add(entity)
    db.commit()
    db.refresh(entity)

    _borrar_transcript_local(transcript_dest)

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
