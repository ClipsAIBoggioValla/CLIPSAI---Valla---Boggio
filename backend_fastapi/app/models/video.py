"""Modelo ORM `Video` — compatible con DDL Issue 1 y spec Issue 4."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        "usuario_id",
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    filename: Mapped[str] = mapped_column(
        "original_filename",
        String(255),
        nullable=False,
    )

    filepath: Mapped[str] = mapped_column(
        "file_path",
        Text,
        nullable=False,
    )

    transcription_filepath: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    transcript: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)

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

    usuario: Mapped[object] = relationship("Usuario", backref="videos", lazy="joined")
    jobs: Mapped[list[object]] = relationship("Job", back_populates="video", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Video id={self.id} filename={self.filename!r} user_id={self.user_id}>"
