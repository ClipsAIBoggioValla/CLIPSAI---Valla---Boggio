"""Schemas Pydantic para Dashboard de Métricas (Issue 19)."""

from __future__ import annotations

from pydantic import BaseModel


class RecentActivityItem(BaseModel):
    date: str
    jobs: int
    clips: int
    minutes_processed: float


class MetricsResponse(BaseModel):
    total_jobs: int
    total_clips: int
    total_minutes_processed: float
    time_saved_hours: float
    platform_distribution: dict[str, int]
    recent_activity: list[RecentActivityItem]
