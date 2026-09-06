from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/jobs", tags=["jobs-stream"])


class StreamEvent(BaseModel):
    progress: int
    status: str
    message: str | None = None


async def _progress_gen(job_id: str) -> AsyncIterator[str]:
    statuses = [
        (0, "pending", "En cola"),
        (15, "transcribing", "Transcribiendo"),
        (30, "analyzing_audio", "Analizando audio"),
        (55, "scoring", "Scoring viral con LLM"),
        (75, "rendering", "Renderizando clip"),
        (90, "publishing", "Preparando publicación"),
        (100, "completed", "Completado"),
    ]
    for progress, status, msg in statuses:
        payload = StreamEvent(progress=progress, status=status, message=msg).model_dump()
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.6)
    yield "event: done\ndata: {}\n\n"


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    return StreamingResponse(
        _progress_gen(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
