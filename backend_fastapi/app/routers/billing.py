"""Consulta autenticada de saldo e historial de créditos."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession
from ..models import CreditTransaction

router = APIRouter(prefix="/billing", tags=["billing"])


class CreditTransactionRead(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None
    transaction_type: str
    amount: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditsPage(BaseModel):
    balance: int | None
    credits_unlimited: bool
    transactions: list[CreditTransactionRead]
    page: int
    page_size: int
    total: int


@router.get("/credits", response_model=CreditsPage, summary="Consultar saldo e historial de créditos")
def get_credits(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CreditsPage:
    """Devuelve movimientos del usuario autenticado, más recientes primero."""
    filters = CreditTransaction.user_id == current_user.id
    total = db.scalar(select(func.count()).select_from(CreditTransaction).where(filters)) or 0
    transactions = db.scalars(
        select(CreditTransaction)
        .where(filters)
        .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return CreditsPage(
        balance=None if current_user.is_admin else int(getattr(current_user, "credits_balance", 0) or 0),
        credits_unlimited=bool(current_user.is_admin),
        transactions=list(transactions),
        page=page,
        page_size=page_size,
        total=int(total),
    )
