"""Schemas Pydantic v2 para el JWT."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class Token(BaseModel):
    """Respuesta de /auth/login."""

    access_token: str
    token_type: str = Field(default="bearer")


class TokenPayload(BaseModel):
    """Claims que emitimos y validamos en el JWT."""

    sub: uuid.UUID           # user id
    exp: datetime            # expiration (UTC)
    iat: datetime | None = None
    type: str = Field(default="access")
