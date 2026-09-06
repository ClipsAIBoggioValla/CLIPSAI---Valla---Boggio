from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/clips", tags=["clips-retrim"])


class RetrimRequest(BaseModel):
    start_time: float = Field(..., ge=0, description="Nuevo inicio en segundos")
    end_time: float = Field(..., ge=0, description="Nuevo fin en segundos")

    def validate_range(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("end_time debe ser > start_time")
        if self.end_time - self.start_time < 5:
            raise ValueError("Duración mínima 5s")
        if self.end_time - self.start_time > 90:
            raise ValueError("Duración máxima 90s")


class RetrimResponse(BaseModel):
    clip_id: str
    start_time: float
    end_time: float
    duration: float
    status: str = "ready"
    file_path: str | None = None


@router.post("/{clip_id}/retrim", response_model=RetrimResponse)
async def retrim_clip(clip_id: str, body: RetrimRequest):
    try:
        body.validate_range()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    duration = body.end_time - body.start_time
    return RetrimResponse(
        clip_id=clip_id,
        start_time=body.start_time,
        end_time=body.end_time,
        duration=duration,
        status="ready",
        file_path=None,
    )
