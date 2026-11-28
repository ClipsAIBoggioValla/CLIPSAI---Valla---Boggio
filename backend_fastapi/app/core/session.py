"""Cookie de sesión HttpOnly (ASH)."""

from __future__ import annotations

import os

from starlette.responses import Response

SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "clipsai_session")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def cookie_samesite() -> str:
    value = os.getenv("SESSION_COOKIE_SAMESITE", "lax").strip().lower()
    return value if value in {"lax", "strict", "none"} else "lax"


def cookie_secure() -> bool:
    """Secure obligatorio en production y cuando SameSite=None."""
    production = os.getenv("APP_ENV", "development").strip().lower() == "production"
    return production or cookie_samesite() == "none" or _bool_env("SESSION_COOKIE_SECURE", False)


def cookie_domain() -> str | None:
    value = os.getenv("SESSION_COOKIE_DOMAIN", "").strip()
    return value or None


def cookie_max_age() -> int:
    raw = os.getenv("JWT_EXPIRE_MINUTES", "480").strip()
    minutes = int(raw) if raw.isdigit() and int(raw) > 0 else 480
    return minutes * 60


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=cookie_max_age(),
        httponly=True,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
        domain=cookie_domain(),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        domain=cookie_domain(),
        path="/",
    )
