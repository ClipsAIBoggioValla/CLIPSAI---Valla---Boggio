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


_ACTIVOS = {"PUBLISHING", *TERMINAL_STATUSES}


def _estado_normalizado(valor: Any) -> str:
    """Texto del estado en mayúsculas y sin espacios."""
    return str(valor or "").strip().upper()


def _effective_status(clip: Clip) -> str:
    """Estado efectivo: publicación activa/terminal > estado del clip > fallback."""
    publication_status = _estado_normalizado(clip.publication_status)
    clip_status = _estado_normalizado(clip.status)
    if publication_status in _ACTIVOS:
        return publication_status
    if clip_status in _ACTIVOS:
        return clip_status
    return publication_status or clip_status or "UNKNOWN"


def _event(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _usuario_del_token(token: str) -> uuid.UUID:
    """user_id del JWT; 401 si expiró o es inválido."""
    try:
        claims = decode_access_token(token)
        return uuid.UUID(str(claims["sub"]))
    except TokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "token_expired", "detail": "Token expirado"}) from exc
    except (TokenDecodeError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "invalid_token", "detail": "Token inválido"}) from exc


def _clip_de_autorizacion(db: Session, clip_id: uuid.UUID, user_id: uuid.UUID) -> Clip:
    """Clip autorizado del usuario o HTTPException 404/403."""
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "clip_not_found", "detail": "Clip no encontrado"})
    owner_video = _get_owner_video(db, clip)
    if owner_video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "clip_not_found", "detail": "Clip no encontrado"})
    if owner_video.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "forbidden", "detail": "No autorizado para este clip"})
    return clip


def _video_autorizado(session: Session, current_clip: Clip, user_id: uuid.UUID) -> bool:
    """True si el clip tiene video propietario y pertenece al usuario."""
    current_video = _get_owner_video(session, current_clip)
    return current_video is not None and current_video.user_id == user_id


def _eventos_consulta(session: Session, clip_id: uuid.UUID, user_id: uuid.UUID) -> tuple[list[str], bool]:
    """Eventos de una consulta exitosa y si el stream debe terminar."""
    current_clip = session.get(Clip, clip_id)
    if current_clip is None:
        return [_event("error", {"error": "clip_not_found", "detail": "Clip no encontrado"}), _event("done", {})], True
    if not _video_autorizado(session, current_clip, user_id):
        return [_event("error", {"error": "forbidden", "detail": "No autorizado para este clip"}), _event("done", {})], True
    current_status = _effective_status(current_clip)
    payload = {
        "clip_id": str(current_clip.id),
        "status": current_status,
        "social_post_url": current_clip.social_post_url,
        "error_log": current_clip.error_log,
    }
    if current_status in TERMINAL_STATUSES:
        return [f"data: {json.dumps(payload, ensure_ascii=False)}\n\n", "event: done\ndata: {}\n\n"], True
    return [f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"], False


def _eventos_de_estado(session: Session, clip_id: uuid.UUID, user_id: uuid.UUID) -> tuple[list[str], bool]:
    """Eventos SSE de la consulta actual y si el stream debe terminar."""
    try:
        return _eventos_consulta(session, clip_id, user_id)
    except Exception:
        return [
            _event("error", {"error": "stream_query_failed", "detail": "No se pudo consultar el estado de publicación"}),
            _event("done", {}),
        ], True


async def _pausa_entre_consultas(started_at: float) -> bool:
    """Pausa hasta la próxima consulta; False si no queda ventana de stream."""
    remaining = STREAM_TIMEOUT_SECONDS - (time.monotonic() - started_at)
    if remaining <= 0:
        return False
    await asyncio.sleep(min(POLL_INTERVAL_SECONDS, remaining))
    return True


async def _cerrar_iteracion(terminar: bool, started_at: float, corte: dict[str, str]) -> None:
    """Decide si el stream termina, agota su ventana o continúa tras la pausa."""
    if terminar:
        corte["motivo"] = "terminar"
        return
    if await _pausa_entre_consultas(started_at):
        corte["motivo"] = "seguir"
        return
    corte["motivo"] = "timeout"


async def _eventos_iteracion(
    request: Request,
    clip_id: uuid.UUID,
    user_id: uuid.UUID,
    started_at: float,
    corte: dict[str, str],
) -> AsyncIterator[str]:
    """Eventos de una iteración del stream; deja en corte['motivo'] cómo continúa."""
    if await request.is_disconnected():
        corte["motivo"] = "terminar"
        return
    session = SessionLocal()
    try:
        eventos, terminar = _eventos_de_estado(session, clip_id, user_id)
    finally:
        session.close()
    for evento in eventos:
        yield evento
    await _cerrar_iteracion(terminar, started_at, corte)


def _seguir_stream(corte: dict[str, str], started_at: float) -> bool:
    """True si el stream continúa: motivo activo y ventana de 90s vigente."""
    return corte["motivo"] == "seguir" and time.monotonic() - started_at < STREAM_TIMEOUT_SECONDS


async def _generador_sse(request: Request, clip_id: uuid.UUID, user_id: uuid.UUID) -> AsyncIterator[str]:
    """Generador SSE: emite estado cada 2s y termina en estado terminal o tras 90s."""
    started_at = time.monotonic()
    corte: dict[str, str] = {"motivo": "seguir"}
    while _seguir_stream(corte, started_at):
        async for evento in _eventos_iteracion(request, clip_id, user_id, started_at, corte):
            yield evento
    if corte["motivo"] != "terminar":
        yield _event("timeout", {"error": "stream_timeout", "detail": "Tiempo máximo de seguimiento alcanzado"})
        yield "event: done\ndata: {}\n\n"


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
    user_id = _usuario_del_token(token)

    if db.get(Usuario, user_id) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "user_not_found", "detail": "Usuario no encontrado"})

    _clip_de_autorizacion(db, clip_id, user_id)
    # La sesión de autorización no debe retener una conexión durante los 90s del stream.
    db.close()

    return StreamingResponse(
        _generador_sse(request, clip_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
