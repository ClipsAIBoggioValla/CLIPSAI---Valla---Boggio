"""Schemas Pydantic v2 para el recurso Usuario."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _UsuarioBase(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=100)


class UsuarioCreate(_UsuarioBase):
    """Payload de POST /auth/registro."""

    password: str = Field(min_length=8, max_length=128)


class UsuarioLogin(BaseModel):
    """Payload de POST /auth/login (variante JSON)."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UsuarioRead(_UsuarioBase):
    """Respuesta segura: NUNCA incluye password/hash."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # from_attributes = True permite serializar directamente desde el modelo ORM.
    model_config = ConfigDict(from_attributes=True)
