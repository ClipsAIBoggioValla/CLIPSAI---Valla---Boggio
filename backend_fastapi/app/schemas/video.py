"""Schemas Pydantic para Video (Issue 4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VideoFromUrlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class VideoResponse(BaseModel):
    id: uuid.UUID
    filename: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VideoFromUrlResponse(VideoResponse):
    job_id: uuid.UUID
    status: str
