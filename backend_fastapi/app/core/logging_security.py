"""Redacción de secretos en logs (compuerta ASH).

Los servicios OAuth de Meta/TikTok/YouTube loguean respuestas de APIs que
pueden incluir access tokens, refresh tokens o upload tokens. Este filtro
elimina esos valores antes de que lleguen a stdout/archivo. Es una red de
seguridad: además, los logs más sensibles se reducen en origen.
"""

from __future__ import annotations

import logging
import re
from typing import Any

_PATRONES = (
    (re.compile(r'(?i)("?(?:access_token|refresh_token|id_token|client_secret|session_token|upload_token|code_verifier|token|code)"?\s*[:=]\s*")([^"]*)(")'), r"\1[REDACTED]\3"),
    (re.compile(r"(?i)\b(access_token|refresh_token|client_secret|upload_token|token|code)=([^&\s]+)"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]+"), "Bearer [REDACTED]"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]+"), "[REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "[REDACTED]"),
)


def redact(text: str) -> str:
    """Devuelve el texto con tokens/credenciales reemplazados."""
    for patron, reemplazo in _PATRONES:
        text = patron.sub(reemplazo, text)
    return text


def _redact_dict(value: dict) -> dict:
    return {key: redact_detail(item) for key, item in value.items()}


def _redact_seq(value: list | tuple) -> Any:
    return type(value)(redact_detail(item) for item in value)


def redact_detail(value: Any) -> Any:
    """Redacta recursivamente detalles de error (str/dict/list)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return _redact_dict(value)
    if isinstance(value, (list, tuple)):
        return _redact_seq(value)
    return value


def _redact_record(record: logging.LogRecord) -> None:
    record.msg = redact(str(record.msg))
    if isinstance(record.args, dict):
        record.args = _redact_dict(record.args)
    elif record.args:
        record.args = tuple(redact_detail(arg) for arg in record.args)


class RedactionFilter(logging.Filter):
    """Filtro de logging que redacta msg y args antes de emitir."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            _redact_record(record)
        except Exception:
            # Nunca bloquear un log por un fallo de redacción.
            pass
        return True


def _has_filter(filters: list) -> bool:
    return any(isinstance(item, RedactionFilter) for item in filters)


def _install_on_logger(logger: logging.Logger, filtro: RedactionFilter) -> None:
    if not _has_filter(logger.filters):
        logger.addFilter(filtro)
    for handler in logger.handlers:
        if not _has_filter(handler.filters):
            handler.addFilter(filtro)


def install_redaction_filter() -> None:
    """Instala el filtro en root y en los loggers de uvicorn (idempotente)."""
    filtro = RedactionFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "backend_fastapi", "clipsai"):
        _install_on_logger(logging.getLogger(name), filtro)
