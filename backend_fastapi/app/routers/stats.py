"""Router de estadísticas para Dashboard — GET /stats/summary (Issue 15)."""

from __future__ import annotations

from sqlalchemy import and_, case, func, select

from fastapi import APIRouter

from ..deps import CurrentUser, DbSession
from ..models import Clip, Job, Video
from ..schemas.stats import RecentJobSummary, ScoreDistributionItem, StatsSummaryResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get(
    "/summary",
    response_model=StatsSummaryResponse,
    summary="Resumen de estadísticas del usuario autenticado",
)
def get_stats_summary(
    current_user: CurrentUser,
    db: DbSession,
) -> StatsSummaryResponse:
    user_id = current_user.id

    total_videos: int = db.scalar(
        select(func.count(Video.id)).where(Video.user_id == user_id)
    ) or 0

    video_ids_subq = select(Video.id).where(Video.user_id == user_id)

    agg_stmt = select(
        func.count(Clip.id).label("total_clips"),
        func.avg(Clip.score).label("avg_score"),
        func.count(case((and_(Clip.score >= 0, Clip.score <= 40), 1))).label("low"),
        func.count(case((and_(Clip.score >= 41, Clip.score <= 70), 1))).label("medium"),
        func.count(case((and_(Clip.score >= 71, Clip.score <= 100), 1))).label("high"),
    ).where(Clip.video_id.in_(video_ids_subq))

    row = db.execute(agg_stmt).one()

    total_clips: int = int(row.total_clips or 0)
    raw_avg = row.avg_score
    avg_score: float = round(float(raw_avg), 1) if raw_avg is not None else 0.0

    low: int = int(row.low or 0)
    medium: int = int(row.medium or 0)
    high: int = int(row.high or 0)

    score_distribution = [
        ScoreDistributionItem(range="0-40", count=low, label="Bajo"),
        ScoreDistributionItem(range="41-70", count=medium, label="Medio"),
        ScoreDistributionItem(range="71-100", count=high, label="Alto"),
    ]

    estimated_time_saved_minutes: int = total_clips * 15

    recent_job_row = db.execute(
        select(Job)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id)
        .order_by(Job.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    recent_job: RecentJobSummary | None = None
    if recent_job_row is not None:
        recent_job = RecentJobSummary.model_validate(recent_job_row)

    return StatsSummaryResponse(
        total_videos=total_videos,
        total_clips=total_clips,
        avg_score=avg_score,
        estimated_time_saved_minutes=estimated_time_saved_minutes,
        score_distribution=score_distribution,
        recent_job=recent_job,
    )
