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

router = APIRouter(tags=["export"])


def _resolve_transcript(clip: Clip, video_transcript: str | None) -> str:
    for attr in ("transcript", "transcript_text", "transcription", "text"):
        v = getattr(clip, attr, None)
        if v:
            return str(v)
    tags = getattr(clip, "tags", None)
    if isinstance(tags, dict) and tags.get("transcript"):
        return str(tags["transcript"])
    if isinstance(tags, dict) and tags.get("text"):
        return str(tags["text"])
    if video_transcript:
        return str(video_transcript)
    return ""


def _build_csv(clips_with_transcript: list[tuple[Clip, str]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["ID", "Título", "Inicio", "Fin", "Score", "Transcripción"])
    for clip, vt in clips_with_transcript:
        transcript = _resolve_transcript(clip, vt)
        writer.writerow([
            str(clip.id),
            clip.title or "",
            clip.start_time,
            clip.end_time,
            clip.score if clip.score is not None else "",
            transcript,
        ])
    return output.getvalue()


def _build_json_payload(clips_with_transcript: list[tuple[Clip, str]], job_id: uuid.UUID | None = None) -> dict:
    clips_payload = []
    scores: list[float] = []
    for clip, vt in clips_with_transcript:
        transcript = _resolve_transcript(clip, vt)
        clips_payload.append({
            "id": str(clip.id),
            "title": clip.title,
            "start_time": clip.start_time,
            "end_time": clip.end_time,
            "score": clip.score,
            "transcript": transcript,
        })
        if clip.score is not None:
            try:
                scores.append(float(clip.score))
            except Exception:
                pass
    payload: dict = {
        "total_clips": len(clips_payload),
        "clips": clips_payload,
    }
    if job_id is not None:
        payload["job_id"] = str(job_id)
    if scores:
        payload["avg_score"] = round(sum(scores) / len(scores), 2)
    return payload


def _fetch_job_clips(db: DbSession, job_id: uuid.UUID) -> list[tuple[Clip, str]]:
    rows = db.execute(
        select(Clip, Video.transcript)
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Clip.job_id == job_id)
        .order_by(Clip.start_time.asc())
    ).all()
    return [(clip, vt or "") for clip, vt in rows]


def _fetch_user_clips(db: DbSession, current_user) -> list[tuple[Clip, str]]:
    rows = db.execute(
        select(Clip, Video.transcript)
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == current_user.id)
        .order_by(Clip.start_time.asc())
    ).all()
    return [(clip, vt or "") for clip, vt in rows]


def _export_response(content: str, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _handle_export(clips_with_transcript: list[tuple[Clip, str]], fmt: str, job_id: uuid.UUID | None = None) -> Response:
    if fmt == "csv":
        csv_content = _build_csv(clips_with_transcript)
        return _export_response(csv_content, "text/csv; charset=utf-8", "clips_export.csv")
    payload = _build_json_payload(clips_with_transcript, job_id)
    json_content = json.dumps(payload, ensure_ascii=False, indent=2)
    return _export_response(json_content, "application/json", "clips_export.json")


@router.get("/jobs/{job_id}/export", summary="Exportar clips de un job en CSV o JSON")
@router.get("/api/v1/jobs/{job_id}/export", summary="Exportar clips de un job en CSV o JSON (alias)", include_in_schema=False)
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
    clips_with_transcript = _fetch_job_clips(db, job_id)
    return _handle_export(clips_with_transcript, format, job_id)


@router.get("/clips/export", summary="Exportar todos los clips del usuario en CSV o JSON")
def export_all_clips(
    db: DbSession,
    current_user: CurrentUser,
    format: Literal["csv", "json"] = Query(..., description="Formato de exportacion: csv o json"),
) -> Response:
    clips_with_transcript = _fetch_user_clips(db, current_user)
    return _handle_export(clips_with_transcript, format)
