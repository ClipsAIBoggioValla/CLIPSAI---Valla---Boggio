"""Middlewares HTTP de seguridad (ASH): headers, rate limit, request id y logs."""

from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from .security.rate_limiter import RateLimiter, RateLimitExceeded

logger = logging.getLogger("clipsai.security")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SKIP_RATE_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"})
_DOCS_PATHS = ("/docs", "/redoc")
_MAX_JSON_BODY = 1_000_000


def _rate_limit_max() -> int:
    raw = os.getenv("SECURITY_RATE_LIMIT", "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    return 120 if os.getenv("APP_ENV", "development").lower() == "production" else 5000


security_limiter = RateLimiter(max_requests=_rate_limit_max(), window_seconds=60)


def reset_security_limiter() -> None:
    security_limiter._hits.clear()


def allowed_hosts() -> list[str]:
    """Hosts permitidos por TrustedHost; en producción, lista explícita."""
    raw = os.getenv("ALLOWED_HOSTS", "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    if os.getenv("APP_ENV", "development").lower() == "production":
        return ["api.clipsai.xyz", "clipsai.xyz", "localhost", "127.0.0.1", "testserver"]
    return ["*"]


def _request_id(request: Request) -> str:
    incoming = request.headers.get("X-Request-ID", "").strip()
    if _REQUEST_ID_RE.match(incoming):
        return incoming
    return uuid.uuid4().hex


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _skip_rate_limit(path: str) -> bool:
    return path in _SKIP_RATE_PATHS or path.startswith("/docs") or path.startswith("/redoc")


def _is_https(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded == "https"


def _body_too_large(request: Request) -> bool:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return False
    content_type = request.headers.get("content-type", "").lower()
    if not content_type.startswith("application/json"):
        return False
    raw = request.headers.get("content-length", "")
    return raw.isdigit() and int(raw) > _MAX_JSON_BODY


def _security_headers(request: Request, response: Any, path: str) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if not path.startswith(_DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
    if _is_https(request) and os.getenv("APP_ENV", "development").lower() == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")


def _too_large_response(request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"detail": "Cuerpo JSON demasiado grande"},
        headers={"X-Request-ID": request_id},
    )


def _rate_limited_response(request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiadas solicitudes"},
        headers={"Retry-After": "60", "X-Request-ID": request_id},
    )


def _apply_rate_limit(request: Request, request_id: str) -> JSONResponse | None:
    if request.method == "OPTIONS" or _skip_rate_limit(request.url.path):
        return None
    try:
        security_limiter.check(f"ip:{_client_ip(request)}")
        return None
    except RateLimitExceeded:
        logger.warning(
            "security.rate_limit method=%s path=%s ip=%s request_id=%s",
            request.method, request.url.path, _client_ip(request), request_id,
        )
        return _rate_limited_response(request_id)


def _log_security_event(request: Request, response: Any, request_id: str) -> None:
    status = response.status_code
    if status in (401, 403, 429) or status >= 500:
        logger.warning(
            "security.event method=%s path=%s status=%s ip=%s request_id=%s",
            request.method, request.url.path, status, _client_ip(request), request_id,
        )


async def security_middleware(request: Request, call_next: Any) -> Any:
    """Rate limit, request id, headers de seguridad y logging de eventos."""
    request_id = _request_id(request)
    request.state.request_id = request_id

    limited = _apply_rate_limit(request, request_id)
    if limited is not None:
        _security_headers(request, limited, request.url.path)
        return limited

    if _body_too_large(request):
        logger.warning(
            "security.body_too_large method=%s path=%s ip=%s request_id=%s",
            request.method, request.url.path, _client_ip(request), request_id,
        )
        response = _too_large_response(request_id)
        _security_headers(request, response, request.url.path)
        return response

    response = await call_next(request)
    _security_headers(request, response, request.url.path)
    response.headers["X-Request-ID"] = request_id
    _log_security_event(request, response, request_id)
    return response
