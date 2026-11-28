"""URLs firmadas y de corta duración para clips (compuerta ASH).

Permite que el frontend reproduzca/descargue un clip sin exponer el JWT en la
URL y sin dejar la descarga completamente pública. La firma es HMAC-SHA256
sobre `clip_id:exp`; el secreto es `STORAGE_SIGN_KEY` (o `JWT_SECRET` como
fallback para no romper despliegues existentes).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import urlencode

DEFAULT_TTL_SECONDS = 3600


def _secret() -> str:
    configured = os.getenv("STORAGE_SIGN_KEY", "").strip()
    if configured:
        return configured
    return os.getenv("JWT_SECRET", "dev_secret_key_clipsai_2026_super_secure_local")


def _ttl() -> int:
    raw = os.getenv("MEDIA_URL_TTL_SECONDS", str(DEFAULT_TTL_SECONDS)).strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_TTL_SECONDS


def _firma(clip_id: str, exp: int) -> str:
    payload = f"{clip_id}:{exp}".encode()
    return hmac.new(_secret().encode(), payload, hashlib.sha256).hexdigest()


def signed_query(clip_id: str) -> str:
    """Query string `exp=...&sig=...` para una URL de clip."""
    exp = int(time.time()) + _ttl()
    return urlencode({"exp": exp, "sig": _firma(clip_id, exp)})


def _exp_int(exp: str | None) -> int | None:
    try:
        return int(exp) if exp is not None else None
    except (TypeError, ValueError):
        return None


def _expirada(exp_int: int | None) -> bool:
    return exp_int is None or exp_int < int(time.time())


def verify_signed_query(clip_id: str, exp: str | None, sig: str | None) -> bool:
    """True si la firma es válida y no expiró."""
    if not exp:
        return False
    if not sig:
        return False
    exp_int = _exp_int(exp)
    if _expirada(exp_int):
        return False
    return hmac.compare_digest(_firma(clip_id, exp_int), sig)
