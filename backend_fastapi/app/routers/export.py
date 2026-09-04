from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from ..deps import CurrentUser, DbSession
from ..models import Clip, Job, Video

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs-export"])


def _get_transcript(clip: Clip) -> str:
    for attr in ("transcript", "transcript_text", "transcription", "text"):
        v = getattr(clip, attr, None)
        if v:
            return str(v)
    tags = getattr(clip, "tags", None)
    if isinstance(tags, dict) and tags.get("transcript"):
        return str(tags["transcript"])
    return ""


@router.get("/{job_id}/export", summary="Exportar clips de un job en CSV o JSON")
def export_job_clips(
    job_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    format: Literal["csv", "json"] = Query(..., description="Formato de exportacion: csv o json"),
) -> Response:
    job: Job | None = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
    video: Video | None = db.get(Video, job.video_id)
    if video is None or video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
    clips = db.execute(select(Clip).where(Clip.job_id == job_id).order_by(Clip.start_time.asc())).scalars().all()
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(["ID", "Título", "Inicio", "Fin", "Score", "Transcripción"])
        for clip in clips:
            transcript = _get_transcript(clip)
            writer.writerow([str(clip.id), clip.title or "", clip.start_time, clip.end_time, clip.score if clip.score is not None else "", transcript])
        content = output.getvalue()
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="job_{job_id}_clips.csv"'})
    payload = {
        "job_id": str(job_id),
        "total_clips": len(clips),
        "clips": [{"id": str(clip.id), "title": clip.title, "start_time": clip.start_time, "end_time": clip.end_time, "score": clip.score, "transcript": _get_transcript(clip)} for clip in clips],
    }
    if clips and any(c.score is not None for c in clips):
        scores = [c.score for c in clips if c.score is not None]
        payload["avg_score"] = round(sum(scores) / len(scores), 2) if scores else None  # type: ignore
    content_json = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(content=content_json, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="job_{job_id}_clips.json"'})
