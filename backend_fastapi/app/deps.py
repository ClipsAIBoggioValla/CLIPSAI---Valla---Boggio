"""Dependencias de FastAPI: sesion de DB y usuario autenticado."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.session import SESSION_COOKIE_NAME
from .database import get_db
from .models import Usuario
from .security.jwt import TokenDecodeError, TokenExpiredError, decode_access_token

# `auto_error=True` -> si falta el header Authorization, FastAPI ya devuelve 401.
_bearer_scheme = HTTPBearer(auto_error=False, description="JWT emitido por /auth/login")
_optional_bearer_scheme = HTTPBearer(auto_error=False, description="JWT opcional")


DbSession = Annotated[Session, Depends(get_db)]
BearerCreds = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]
OptionalBearerCreds = Annotated[HTTPAuthorizationCredentials | None, Depends(_optional_bearer_scheme)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _payload_de_token(token: str) -> dict:
    try:
        return decode_access_token(token)
    except TokenExpiredError as exc:
        raise _unauthorized("Token expirado") from exc
    except TokenDecodeError as exc:
        raise _unauthorized("Token invalido") from exc


def _user_id_de_payload(payload: dict) -> uuid.UUID:
    try:
        return uuid.UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise _unauthorized("Token invalido") from exc


def _validar_token_version(payload: dict, usuario: Usuario) -> None:
    if int(payload.get("ver", 0)) != int(getattr(usuario, "token_version", 0) or 0):
        raise _unauthorized("Sesión revocada")


def _usuario_desde_token(token: str, db: Session) -> Usuario:
    payload = _payload_de_token(token)
    user_id = _user_id_de_payload(payload)
    usuario = db.execute(select(Usuario).where(Usuario.id == user_id)).scalar_one_or_none()
    if usuario is None:
        raise _unauthorized("Usuario no encontrado")
    _validar_token_version(payload, usuario)
    return usuario


def _token_de_request(creds: BearerCreds, request: Request) -> str | None:
    if creds is not None:
        return creds.credentials
    return request.cookies.get(SESSION_COOKIE_NAME)


def get_current_user(creds: BearerCreds, request: Request, db: DbSession) -> Usuario:
    """Extrae el JWT, valida firma/expiracion y busca el usuario en la DB.

    Devuelve 401 en cualquiera de estos casos:
      - Falta el header o el esquema no es Bearer (lo maneja HTTPBearer).
      - Firma invalida o payload corrupto.
      - Token expirado.
      - El `sub` no corresponde a un usuario existente en la DB.
    """
    token = _token_de_request(creds, request)
    if not token:
        raise _unauthorized("No autenticado")
    return _usuario_desde_token(token, db)


def get_current_user_optional(creds: OptionalBearerCreds, request: Request, db: DbSession) -> Usuario | None:
    """Usuario autenticado o None; un token inválido no autentica."""
    token = _token_de_request(creds, request)
    if not token:
        return None
    try:
        return _usuario_desde_token(token, db)
    except HTTPException:
        return None


CurrentUser = Annotated[Usuario, Depends(get_current_user)]
OptionalUser = Annotated[Usuario | None, Depends(get_current_user_optional)]
