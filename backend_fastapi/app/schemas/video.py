"""Schemas Pydantic para Video (Issue 4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VideoResponse(BaseModel):
    id: uuid.UUID
    filename: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
