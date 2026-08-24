"""Emision y validacion de JSON Web Tokens (JWT) con python-jose."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt

from ..config import get_settings

_settings = get_settings()


class TokenDecodeError(Exception):
    """Se lanza cuando el token esta corrupto, firma invalida, etc."""


class TokenExpiredError(Exception):
    """Se lanza cuando el token esta expirado."""


def create_access_token(
    subject: uuid.UUID | str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Emite un JWT firmado con el secreto de la app.

    - `sub` = identificador del usuario (UUID como string).
    - `exp` = fecha de expiracion (UTC).
    - `iat` = fecha de emision.
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=_settings.jwt_expire_minutes)
    )

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(
        to_encode,
        _settings.jwt_secret,
        algorithm=_settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Verifica firma + expiracion del token y devuelve el payload.

    Levanta:
        TokenExpiredError: si el token esta vencido.
        TokenDecodeError: si el token esta mal formado o firma invalida.
    """
    try:
        payload = jwt.decode(
            token,
            _settings.jwt_secret,
            algorithms=[_settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Token expirado") from exc
    except JWTError as exc:
        raise TokenDecodeError("Token invalido") from exc

    if "sub" not in payload:
        raise TokenDecodeError("Token sin claim 'sub'")

    return payload
