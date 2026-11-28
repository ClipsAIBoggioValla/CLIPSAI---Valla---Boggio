"""Orígenes CORS compartidos por la app y el middleware de seguridad."""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

from ..config import get_settings

CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_HEADERS = [
    "Authorization",
    "Content-Type",
    "ngrok-skip-browser-warning",
    "X-Requested-With",
    "Accept",
    "Origin",
    "X-Request-ID",
    "X-CSRF-Token",
]
# Allowlist por defecto: solo subdominios de clipsai.xyz. Para previews de
# Vercel/ngrok, definir CORS_ORIGIN_REGEX explícitamente en el entorno.
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.clipsai\.xyz")


def _extras_de_entorno() -> list[str]:
    settings = get_settings()
    extras: list[str] = []
    for value in (settings.frontend_url, settings.frontend_redirect_url, os.getenv("CORS_EXTRA_ORIGINS", "")):
        if value:
            extras.extend(str(value).split(","))
    return extras


def _normalizar_origen(extra: str) -> str:
    return extra.strip().rstrip("/")


def build_cors_origins() -> list[str]:
    origins = [
        "https://api.clipsai.xyz",
        "https://clipsai.xyz",
        "https://www.clipsai.xyz",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    for extra in _extras_de_entorno():
        origin = _normalizar_origen(extra)
        if origin and origin not in origins:
            origins.append(origin)
    return origins


CORS_ORIGINS = build_cors_origins()


def _normalizar_origin(origin: str) -> str:
    parsed = urlsplit(origin)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else origin


def _coincide_regex(origin: str) -> bool:
    return re.match(CORS_ORIGIN_REGEX, origin) is not None


def origin_is_allowed(origin: str) -> bool:
    if not origin:
        return False
    normalized = _normalizar_origin(origin)
    return normalized in CORS_ORIGINS or _coincide_regex(normalized)
