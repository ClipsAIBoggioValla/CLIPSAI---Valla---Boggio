"""RunPod callback endpoint authenticated with an HMAC-SHA256 signature."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from ..config import get_settings
from ..deps import DbSession
from ..models import Job, JobStatus, Video
from ..services.runpod_service import RunPodError, _normalize_transcription_segments, _raise_for_job_failure
from ..services.credits_service import refund_job_credits

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _firma_recibida(request: Request) -> str | None:
    """Lee la firma admitida y elimina el prefijo opcional sha256=."""
    firma = request.headers.get("X-Runpod-Signature") or request.headers.get("X-Webhook-Signature")
    if not firma:
        return None
    firma = firma.strip()
    return firma.removeprefix("sha256=")


def _firma_valida(raw: bytes, firma: str | None, secret: str) -> bool:
    """Compara en tiempo constante la firma hexadecimal HMAC-SHA256."""
    if not firma:
        return False
    esperada = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(esperada, firma)
    except TypeError:
        return False


def _exigir_autenticidad(request: Request, raw: bytes) -> None:
    """Rechaza firmas inválidas; solo permite secret vacío fuera de producción."""
    settings = get_settings()
    secret = settings.runpod_webhook_secret.strip()
    if not secret and settings.app_env.strip().lower() != "production":
        logger.warning("RUNPOD_WEBHOOK_SECRET vacío: se acepta callback sin firma fuera de producción")
        return
    if not _firma_valida(raw, _firma_recibida(request), secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma de webhook inválida")


def _obtener_job(db: Any, payload: dict[str, Any]) -> tuple[Any, Any]:
    """Busca el job referenciado por job_id o id; 404 si falta o no existe."""
    from .jobs import _normalizar_job_id

    raw_id = payload.get("job_id") or payload.get("id")
    if raw_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
    try:
        job_id = _normalizar_job_id(str(raw_id))
        job = db.get(Job, job_id)
    except (TypeError, ValueError):
        job = None
        job_id = None
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
    return job, job_id


def _marcar_fallo(db: Any, job: Any, payload: dict[str, Any]) -> bool:
    """Marca FAILED si el helper de RunPod indica estado terminal de error."""
    try:
        _raise_for_job_failure(payload)
    except RunPodError as exc:
        job.status = JobStatus.FAILED.value
        job.error_message = str(exc)
        db.commit()
        refund_job_credits(db, job.id)
        return True
    return False


def _resultado_y_clips(payload: dict[str, Any]) -> tuple[dict[str, Any], list]:
    """Normaliza resultado/segmentos y obtiene los clips del callback."""
    from .jobs import _clips_del_resultado

    output = payload.get("output")
    if isinstance(output, list):
        result: dict[str, Any] = {"clips": output}
    elif isinstance(output, dict):
        result = output
    else:
        result = payload
    result["transcription_segments"] = _normalize_transcription_segments(
        result.get("transcription_segments", [])
    )
    return result, _clips_del_resultado(result)


def _es_completado(payload: dict[str, Any]) -> bool:
    return str(payload.get("status", "")).upper() in {"COMPLETED", "SUCCEEDED"}


def _aplicar_callback(db: Any, payload: dict[str, Any]) -> dict[str, bool]:
    """Persiste estados terminales y clips R2 luego de autenticar el callback."""
    from .jobs import _persistir_clips_r2

    job, job_id = _obtener_job(db, payload)
    if _marcar_fallo(db, job, payload):
        return {"received": True}
    if _es_completado(payload):
        video = db.get(Video, job.video_id)
        if video is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video asociado no encontrado")
        result, clips = _resultado_y_clips(payload)
        _persistir_clips_r2(db, video, result, clips, job_id)
    return {"received": True}


@router.post("/runpod", status_code=status.HTTP_202_ACCEPTED)
async def runpod_callback(request: Request, db: DbSession) -> dict[str, bool]:
    raw = await request.body()
    _exigir_autenticidad(request, raw)
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON inválido") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El payload debe ser un objeto JSON")
    return _aplicar_callback(db, payload)
