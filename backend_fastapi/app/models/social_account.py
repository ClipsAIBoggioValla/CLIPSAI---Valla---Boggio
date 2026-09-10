"""Modelo ORM `SocialAccount` — cuentas OAuth vinculadas (Issue #22)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (
        CheckConstraint("lower(platform) IN ('youtube','instagram','tiktok')", name="chk_social_accounts_platform"),
        UniqueConstraint("user_id", "platform", name="uq_social_accounts_user_platform"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    platform: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    platform_account_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    platform_username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    access_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    refresh_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    user: Mapped[object | None] = relationship("Usuario", backref="social_accounts", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SocialAccount id={self.id} user_id={self.user_id} platform={self.platform!r} username={self.platform_username!r}>"
