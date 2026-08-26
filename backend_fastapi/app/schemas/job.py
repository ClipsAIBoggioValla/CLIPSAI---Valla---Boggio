"""Schemas Pydantic para Job (Issue 4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class JobResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    status: str
    error_message: str | None = None
    result_metadata: dict[str, Any] | list[Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.lower()
        if hasattr(v, "value"):
            return str(v.value).lower()
        return str(v).lower()

    @field_serializer("status")
    def _serialize_status(self, v: str) -> str:
        return v.upper() if isinstance(v, str) else str(v).upper()
