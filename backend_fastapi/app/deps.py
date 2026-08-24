"""Dependencias de FastAPI: sesion de DB y usuario autenticado."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Usuario
from .security.jwt import TokenDecodeError, TokenExpiredError, decode_access_token

# `auto_error=True` -> si falta el header Authorization, FastAPI ya devuelve 401.
_bearer_scheme = HTTPBearer(auto_error=True, description="JWT emitido por /auth/login")


DbSession = Annotated[Session, Depends(get_db)]
BearerCreds = Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(creds: BearerCreds, db: DbSession) -> Usuario:
    """Extrae el JWT, valida firma/expiracion y busca el usuario en la DB.

    Devuelve 401 en cualquiera de estos casos:
      - Falta el header o el esquema no es Bearer (lo maneja HTTPBearer).
      - Firma invalida o payload corrupto.
      - Token expirado.
      - El `sub` no corresponde a un usuario existente en la DB.
    """
    token = creds.credentials

    try:
        payload = decode_access_token(token)
    except TokenExpiredError as exc:
        raise _unauthorized("Token expirado") from exc
    except TokenDecodeError as exc:
        raise _unauthorized("Token invalido") from exc

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise _unauthorized("Token invalido") from exc

    usuario = db.execute(select(Usuario).where(Usuario.id == user_id)).scalar_one_or_none()
    if usuario is None:
        # El usuario fue eliminado o el token corresponde a un id inexistente.
        raise _unauthorized("Usuario no encontrado")

    return usuario


CurrentUser = Annotated[Usuario, Depends(get_current_user)]
