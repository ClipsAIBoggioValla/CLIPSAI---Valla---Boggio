"""Modelo ORM de la tabla `usuarios`.

La tabla fisica la crea el script DDL de la Issue 1
(`init-scripts/01-init-schema.sql`). Aqui solo la mapeamos.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .mixins import TimestampMixin


class Usuario(Base, TimestampMixin):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("credits_balance >= 0", name="chk_usuarios_credits_balance"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    theme_preference: Mapped[str | None] = mapped_column(String(20), nullable=True, server_default="dark")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    credits_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    credits_exempt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


    def __repr__(self) -> str:  # pragma: no cover
        return f"<Usuario id={self.id} email={self.email!r}>"
