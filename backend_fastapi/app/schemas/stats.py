"""Schemas Pydantic para Dashboard / Stats (Issue 15)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


class ScoreDistributionItem(BaseModel):
    range: str
    count: int
    label: str


class RecentJobSummary(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("status")
    def _serialize_status(self, v: str) -> str:
        return v.upper() if isinstance(v, str) else str(v).upper()


class StatsSummaryResponse(BaseModel):
    total_videos: int
    total_clips: int
    avg_score: float
    estimated_time_saved_minutes: int
    score_distribution: list[ScoreDistributionItem]
    recent_job: RecentJobSummary | None = None
