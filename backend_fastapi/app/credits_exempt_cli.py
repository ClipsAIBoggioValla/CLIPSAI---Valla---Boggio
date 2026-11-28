"""Operator-only, fixed allowlist for enabling unlimited processing credits."""

from __future__ import annotations

from sqlalchemy import func, select

from .database import SessionLocal
from .models import Usuario
from .services.credits_policy import CREDITS_EXEMPT_EMAILS

TARGET_EMAILS = CREDITS_EXEMPT_EMAILS


def grant_credits_exempt(db) -> int:
    """Idempotently exempts only the two approved, already-registered accounts."""
    users = db.scalars(select(Usuario).where(func.lower(Usuario.email).in_(TARGET_EMAILS))).all()
    found = {user.email.casefold() for user in users}
    missing = TARGET_EMAILS - found
    if missing:
        raise ValueError("Estas cuentas deben registrarse antes de habilitar la exención.")
    for user in users:
        user.credits_exempt = True
    db.commit()
    return len(users)


def main() -> None:
    if SessionLocal is None:
        raise RuntimeError("No hay base de datos configurada en este entorno.")
    with SessionLocal() as db:
        count = grant_credits_exempt(db)
    print(f"Exención de créditos habilitada para {count} cuentas aprobadas.")


if __name__ == "__main__":
    main()
