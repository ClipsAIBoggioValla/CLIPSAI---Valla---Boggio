"""Credit policy for the fixed set of unlimited-credit accounts."""

from __future__ import annotations

CREDITS_EXEMPT_EMAILS = frozenset({
    "mf.boggio@alumno.etec.um.edu.ar",
    "b.levatino@alumno.etec.um.edu.ar",
})


def normalize_credit_email(email: str | None) -> str:
    return (email or "").strip().lower()


def is_credits_exempt(user) -> bool:
    return bool(getattr(user, "credits_exempt", False)) or (
        normalize_credit_email(getattr(user, "email", None)) in CREDITS_EXEMPT_EMAILS
    )
