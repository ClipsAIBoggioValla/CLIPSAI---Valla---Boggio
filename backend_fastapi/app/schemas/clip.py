"""Schemas Pydantic para Clip (Issue 5 + Issue 16 Biblioteca)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    published_platform: str | None = None
    social_post_id: str | None = None
    social_post_url: str | None = None
    published_at: datetime | None = None
    publication_status: str | None = None
    social_network: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublishClipRequest(BaseModel):
    platform: str = Field(description="tiktok|instagram|youtube|webhook")
    caption: str | None = Field(default=None, max_length=500)
    webhook_override_url: str | None = None


class PublishClipResponse(BaseModel):
    detail: str
    clip_id: uuid.UUID
    status: str
    platform: str


class ClipListItem(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    title: str | None = None
    score: float | int | None = None
    start_time: float
    end_time: float
    transcript: str | None = None
    status: str | None = None
    published_platform: str | None = None
    social_post_url: str | None = None
    published_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClipListResponse(BaseModel):
    items: list[ClipListItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=0)
