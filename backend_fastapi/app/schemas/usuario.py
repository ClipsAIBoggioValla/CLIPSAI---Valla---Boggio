"""Schemas Pydantic v2 para el recurso Usuario."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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

    model_config = ConfigDict(from_attributes=True)


ThemePreference = Literal["dark", "light", "system"]


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    theme_preference: ThemePreference = Field(default="dark")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    theme_preference: ThemePreference | None = Field(default=None)
    email: EmailStr | None = Field(default=None)

    @field_validator("avatar_url")
    @classmethod
    def _validate_avatar_url(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            return None
        if v is not None and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("avatar_url debe ser una URL http(s)")
        return v


class UserUpdateSimple(BaseModel):
    nombre: str | None = Field(default=None, max_length=100, alias="full_name")
    full_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = Field(default=None)
    avatar_url: str | None = Field(default=None, max_length=500)
    theme_preference: ThemePreference | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("avatar_url")
    @classmethod
    def _validate_avatar2(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            return None
        if v is not None and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("avatar_url debe ser una URL http(s)")
        return v


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
