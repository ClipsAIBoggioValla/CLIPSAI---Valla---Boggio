"""Modelo ORM `Clip` — clips virales generados por un Job (Issue 5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, Float, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Clip(Base):
    __tablename__ = "clips"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )

    video_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    start_time: Mapped[float] = mapped_column(Float, nullable=False)

    end_time: Mapped[float] = mapped_column(Float, nullable=False)

    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    tags: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    storage_path: Mapped[str | None] = mapped_column(
        "file_path",
        Text,
        nullable=False,
        server_default="",
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ready",
        server_default="ready",
    )

    publication_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        server_default="draft",
    )

    social_network: Mapped[str | None] = mapped_column(String(50), nullable=True)

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

    video: Mapped[object | None] = relationship("Video", backref="clips", lazy="joined")
    job: Mapped[object | None] = relationship("Job", backref="clips", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Clip id={self.id} job_id={self.job_id} title={self.title!r}>"
