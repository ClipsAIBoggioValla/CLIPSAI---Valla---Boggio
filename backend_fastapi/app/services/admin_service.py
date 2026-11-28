"""Operaciones administrativas explícitas para cuentas ya registradas."""

from __future__ import annotations

from sqlalchemy import func, select

from ..models import Usuario


def grant_admins(db, emails: list[str]) -> int:
    """Promueve las cuentas existentes indicadas; nunca crea usuarios ni contraseñas."""
    normalized = {email.strip().casefold() for email in emails if email.strip()}
    if not normalized:
        raise ValueError("Indica al menos un email registrado.")
    users = db.scalars(select(Usuario).where(func.lower(Usuario.email).in_(normalized))).all()
    found = {user.email.casefold() for user in users}
    missing = normalized - found
    if missing:
        raise ValueError("Primero deben registrarse estas cuentas: " + ", ".join(sorted(missing)))
    for user in users:
        user.is_admin = True
    db.commit()
    return len(users)
