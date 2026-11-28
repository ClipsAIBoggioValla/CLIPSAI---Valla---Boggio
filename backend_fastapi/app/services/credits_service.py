"""Operaciones atómicas e idempotentes del ledger de créditos."""

from __future__ import annotations

import math
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from ..models import CreditTransaction, Usuario, Video

TRIAL_CREDITS = 15


def credit_cost(duration_seconds: float | None) -> int:
    """Créditos/minutos requeridos; duración desconocida no se cobra a ciegas."""
    if duration_seconds is None:
        raise HTTPException(status_code=422, detail="No se pudo determinar la duración del video.")
    try:
        duration = float(duration_seconds)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="La duración del video no es válida.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise HTTPException(status_code=422, detail="La duración del video no es válida.")
    return math.ceil(duration / 60)


def _duration_is_usable(duration: float | None) -> bool:
    try:
        return duration is not None and math.isfinite(float(duration)) and float(duration) > 0
    except (TypeError, ValueError):
        return False


def resolve_video_duration(video: Video) -> float:
    """Usa metadata existente o intenta medir el archivo local con ffprobe."""
    duration = video.duration_seconds
    if not _duration_is_usable(duration) and video.filepath:
        from .ffmpeg_service import probe_duration

        duration = probe_duration(video.filepath)
        if _duration_is_usable(duration):
            video.duration_seconds = duration
    credit_cost(duration)
    return float(duration)


def _transaction_exists(db, key: str) -> bool:
    return db.scalar(select(CreditTransaction.id).where(CreditTransaction.idempotency_key == key)) is not None


def _balance_update(db, user_id: uuid.UUID, amount: int, minimum: int | None):
    """Modifica el balance en SQL; el predicado evita saldo negativo bajo concurrencia."""
    stmt = update(Usuario).where(Usuario.id == user_id)
    if minimum is not None:
        stmt = stmt.where(Usuario.credits_balance >= minimum)
    return db.execute(
        stmt.values(credits_balance=Usuario.credits_balance + amount)
        .returning(Usuario.credits_balance)
    ).scalar_one_or_none()


def debit_job_credits(
    db, user_id: uuid.UUID, job_id: uuid.UUID, duration_seconds: float, is_admin: bool = False,
) -> int:
    """Descuenta una vez por job. El llamador confirma junto con el job."""
    credits = credit_cost(duration_seconds)
    if is_admin:
        return 0
    key = f"usage:{job_id}"
    if _transaction_exists(db, key):
        return credits
    balance = _balance_update(db, user_id, -credits, credits)
    if balance is None:
        raise HTTPException(status_code=402, detail="Créditos insuficientes para procesar este video.")
    db.add(CreditTransaction(
        user_id=user_id, job_id=job_id, transaction_type="usage", amount=-credits,
        idempotency_key=key,
    ))
    return credits


def grant_free_trial(db, user: Usuario) -> None:
    """Asigna el trial al registrar la cuenta y registra el movimiento."""
    user.credits_balance = TRIAL_CREDITS
    db.add(CreditTransaction(
        user_id=user.id, transaction_type="free_trial", amount=TRIAL_CREDITS,
        idempotency_key=f"trial:{user.id}",
    ))


def _refund_usage(db, usage: CreditTransaction, job_id: uuid.UUID) -> None:
    """Aplica el delta de reembolso una vez, respaldado por clave única."""
    key = f"refund:{job_id}"
    if _transaction_exists(db, key):
        return
    amount = abs(int(usage.amount))
    _balance_update(db, usage.user_id, amount, None)
    db.add(CreditTransaction(
        user_id=usage.user_id, job_id=job_id, transaction_type="refund", amount=amount,
        idempotency_key=key,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if not _transaction_exists(db, key):
            raise


def refund_job_credits(db, job_id: uuid.UUID) -> None:
    """Reembolsa el usage del job; llamadas repetidas no acreditan dos veces."""
    usage = db.scalar(select(CreditTransaction).where(
        CreditTransaction.idempotency_key == f"usage:{job_id}"
    ))
    if usage is not None:
        _refund_usage(db, usage, job_id)
