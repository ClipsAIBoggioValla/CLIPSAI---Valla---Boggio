from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse

from ..deps import CurrentUser, DbSession
from ._clip_common import assert_clip_ownership as _assert_ownership, get_clip_or_404 as _get_clip_or_404
from ..models import Clip, Video
from ..schemas import PublishClipRequest, PublishClipResponse

router = APIRouter(prefix="/clips", tags=["clips"])

ALLOWED_PLATFORMS = {"tiktok", "instagram", "youtube", "webhook"}




@router.post(
    "/{clip_id}/publicar",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PublishClipResponse,
    summary="Publicar clip en red social (async)",
)
@router.post(
    "/{clip_id}/publish",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PublishClipResponse,
    summary="Publicar clip en red social (async) - alias",
    include_in_schema=False,
)
def publish_clip(
    clip_id: uuid.UUID,
    payload: PublishClipRequest,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    platform = (payload.platform or "").strip().lower()
    if platform not in ALLOWED_PLATFORMS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"platform debe ser una de {sorted(ALLOWED_PLATFORMS)}")

    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)

    try:
        from ..services.publish_service import publish_clip_task

        background_tasks.add_task(publish_clip_task, clip.id, platform, payload.caption, payload.webhook_override_url, str(current_user.id))
    except Exception as e:
        _marcar_publicacion_fallida(db, clip)
        raise HTTPException(status_code=500, detail=str(e))
    _encolar_publicacion(db, clip, platform)
    return PublishClipResponse(detail="Publicación encolada", clip_id=clip.id, status="PUBLISHING", platform=platform)


def _encolar_publicacion(db, clip: Any, platform: str) -> None:
    """Marca el clip como PUBLISHING y commitea."""
    clip.status = "PUBLISHING"
    try:
        clip.published_platform = platform
        clip.publication_status = "PUBLISHING"
    except Exception:
        pass
    db.commit()


def _marcar_publicacion_fallida(db, clip: Any) -> None:
    """El encolado falló: el clip pasa a FAILED (rollback si la DB también falla)."""
    try:
        clip.status = "FAILED"
        db.add(clip)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _estado_publicacion_efectivo(clip: Any) -> str:
    """PUBLISHING/PUBLISHED/FAILED efectivo (publication_status con fallback a status)."""
    return str(getattr(clip, "publication_status", "") or "").upper() or str(getattr(clip, "status", "") or "").upper()


def _clip_publicado(clip: Any) -> bool:
    """True si el clip ya terminó de publicar (PUBLISHED/FAILED)."""
    effective = _estado_publicacion_efectivo(clip)
    if effective in ("PUBLISHED", "FAILED"):
        return True
    status_val = str(getattr(clip, "status", "") or "").upper()
    return status_val in ("PUBLISHED", "FAILED")


def _payload_estado_clip(clip: Any) -> dict:
    """Payload SSE con el estado de publicación del clip."""
    platform = getattr(clip, "published_platform", None) or getattr(clip, "social_network", None)
    return {
        "clip_id": str(clip.id),
        "status": str(getattr(clip, "status", "") or "").upper(),
        "publication_status": str(getattr(clip, "publication_status", "") or "").upper(),
        "published_platform": platform,
        "social_post_id": getattr(clip, "social_post_id", None),
        "social_post_url": getattr(clip, "social_post_url", None),
    }


def _es_dueño_directo(sdb, clip: Any, user_id) -> bool:
    """Ownership vía video_id directo."""
    if clip.video_id is None:
        return False
    v = sdb.get(Video, clip.video_id)
    return v is not None and str(v.user_id) == str(user_id)


def _es_dueño_via_job(sdb, clip: Any, user_id) -> bool:
    """Ownership vía job → video."""
    if clip.job_id is None:
        return False
    from ..models import Job

    j = sdb.get(Job, clip.job_id)
    if j is None:
        return False
    v2 = sdb.get(Video, j.video_id)
    return v2 is not None and str(v2.user_id) == str(user_id)


def _acceso_valido(sdb, clip: Any, user_id) -> bool:
    """Re-valida ownership por si cambia (directo o vía job)."""
    return _es_dueño_directo(sdb, clip, user_id) or _es_dueño_via_job(sdb, clip, user_id)


def _clip_no_encontrado_evento() -> str:
    return f"event: error\ndata: {json.dumps({'detail': 'Clip no encontrado'}, ensure_ascii=False)}\n\n"


def _no_autorizado_evento() -> str:
    return f"event: error\ndata: {json.dumps({'detail': 'No autorizado'}, ensure_ascii=False)}\n\n"


def _cerrar_sesion(sdb) -> None:
    try:
        sdb.close()
    except Exception:
        pass


def _evento_estado(sdb, clip_id, user_id, seen_status: str | None) -> tuple[str | None, str | None, bool]:
    """Estado del clip + evento de cambio. Devuelve (evento, nuevo_seen, terminar)."""
    c = sdb.get(Clip, clip_id)
    if c is None:
        return _clip_no_encontrado_evento(), seen_status, True
    if not _acceso_valido(sdb, c, user_id):
        return _no_autorizado_evento(), seen_status, True
def _evento_cierre(evento: str | None) -> str:
    """Evento final 'done' concatenado al último estado emitido (si lo hubo)."""
    base = evento if evento is not None else ""
    return base + "event: done\ndata: {}\n\n"


def _evento_estado(sdb, clip_id, user_id, seen_status: str | None) -> tuple[str | None, str | None, bool]:
    """Estado del clip + evento de cambio. Devuelve (evento, nuevo_seen, terminar)."""
    c = sdb.get(Clip, clip_id)
    if c is None:
        return _clip_no_encontrado_evento(), seen_status, True
    if not _acceso_valido(sdb, c, user_id):
        return _no_autorizado_evento(), seen_status, True
    effective = _estado_publicacion_efectivo(c)
    evento = None
    if effective != seen_status:
        evento = f"data: {json.dumps(_payload_estado_clip(c), ensure_ascii=False)}\n\n"
    if _clip_publicado(c):
        return _evento_cierre(evento), effective, True
    return evento, effective, False


@router.get(
    "/{clip_id}/publish-stream",
    summary="SSE stream estado publicación (PUBLISHING → PUBLISHED/FAILED)",
)
async def publish_stream(
    clip_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
):
    # Ownership check con la sesión del request
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)
    user_id = current_user.id

    async def event_gen():
        from ..database import SessionLocal as _SessionLocal

        seen_status: str | None = None
        # Polling 1s, timeout 90s para evitar conexión infinita
        for _ in range(90):
            sdb = _SessionLocal()
            try:
                evento, seen_status, terminar = _evento_estado(sdb, clip_id, user_id, seen_status)
                if evento:
                    yield evento
                if terminar:
                    return
            finally:
                _cerrar_sesion(sdb)
            await asyncio.sleep(1.0)
        # Timeout: enviar último estado
        yield "event: timeout\ndata: {}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
