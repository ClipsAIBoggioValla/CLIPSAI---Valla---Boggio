"""Schemas Pydantic para Clip (Issue 5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ClipBase(BaseModel):
    title: str | None = None
    tags: list[str] | None = None


class ClipUpdate(ClipBase):
    pass


class ClipResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID | None = None
    job_id: uuid.UUID
    title: str | None = None
    start_time: float
    end_time: float
    score: float | int | None = None
    tags: list[Any] | None = None
    storage_path: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
