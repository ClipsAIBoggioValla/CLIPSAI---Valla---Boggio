"""Eventos SSE para seguir el estado de publicación de un clip."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..deps import DbSession
from ..models import Clip, Job, Usuario, Video
from ..security.jwt import TokenDecodeError, TokenExpiredError, decode_access_token

router = APIRouter(prefix="/clips", tags=["publish-stream"])
POLL_INTERVAL_SECONDS = 2
STREAM_TIMEOUT_SECONDS = 90
TERMINAL_STATUSES = {"PUBLISHED", "FAILED"}


def _get_owner_video(db: Session, clip: Clip) -> Video | None:
    """Resuelve el video propietario para clips antiguos y actuales."""
    if clip.video_id is not None:
        video = db.get(Video, clip.video_id)
        if video is not None:
            return video
    if clip.job_id is not None:
        job = db.get(Job, clip.job_id)
        if job is not None:
            return db.get(Video, job.video_id)
    return None


def _effective_status(clip: Clip) -> str:
    publication_status = str(clip.publication_status or "").strip().upper()
    clip_status = str(clip.status or "").strip().upper()
    if publication_status in {"PUBLISHING", *TERMINAL_STATUSES}:
        return publication_status
    if clip_status in {"PUBLISHING", *TERMINAL_STATUSES}:
        return clip_status
    return publication_status or clip_status or "UNKNOWN"


def _event(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get(
    "/{clip_id}/publish-stream",
    response_class=StreamingResponse,
    summary="SSE del estado de publicación de un clip",
    operation_id="clips_publish_stream_sse",
    responses={
        200: {
            "description": "Flujo SSE con actualizaciones del estado de publicación",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        401: {"description": "Token ausente o inválido"},
        403: {"description": "El clip pertenece a otro usuario"},
        404: {"description": "Clip no encontrado"},
    },
)
async def publish_stream(
    clip_id: uuid.UUID,
    request: Request,
    db: DbSession,
    token: Annotated[str, Query(description="JWT para clientes EventSource")],
) -> StreamingResponse:
    """Emite el estado cada dos segundos y termina en estado terminal o tras 90s."""
    try:
        claims = decode_access_token(token)
        user_id = uuid.UUID(str(claims["sub"]))
    except TokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "token_expired", "detail": "Token expirado"}) from exc
    except (TokenDecodeError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "invalid_token", "detail": "Token inválido"}) from exc

    if db.get(Usuario, user_id) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "user_not_found", "detail": "Usuario no encontrado"})

    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "clip_not_found", "detail": "Clip no encontrado"})
    owner_video = _get_owner_video(db, clip)
    if owner_video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "clip_not_found", "detail": "Clip no encontrado"})
    if owner_video.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "forbidden", "detail": "No autorizado para este clip"})
    # La sesión de autorización no debe retener una conexión durante los 90s del stream.
    db.close()

    async def event_generator() -> AsyncIterator[str]:
        started_at = time.monotonic()
        while time.monotonic() - started_at < STREAM_TIMEOUT_SECONDS:
            if await request.is_disconnected():
                return

            session = SessionLocal()
            try:
                current_clip = session.get(Clip, clip_id)
                if current_clip is None:
                    yield _event("error", {"error": "clip_not_found", "detail": "Clip no encontrado"})
                    yield _event("done", {})
                    return

                current_video = _get_owner_video(session, current_clip)
                if current_video is None or current_video.user_id != user_id:
                    yield _event("error", {"error": "forbidden", "detail": "No autorizado para este clip"})
                    yield _event("done", {})
                    return

                current_status = _effective_status(current_clip)
                payload = {
                    "clip_id": str(current_clip.id),
                    "status": current_status,
                    "social_post_url": current_clip.social_post_url,
                    "error_log": current_clip.error_log,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if current_status in TERMINAL_STATUSES:
                    yield "event: done\ndata: {}\n\n"
                    return
            except Exception:
                yield _event("error", {"error": "stream_query_failed", "detail": "No se pudo consultar el estado de publicación"})
                yield _event("done", {})
                return
            finally:
                session.close()

            remaining = STREAM_TIMEOUT_SECONDS - (time.monotonic() - started_at)
            if remaining <= 0:
                break
            await asyncio.sleep(min(POLL_INTERVAL_SECONDS, remaining))

        yield _event("timeout", {"error": "stream_timeout", "detail": "Tiempo máximo de seguimiento alcanzado"})
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
