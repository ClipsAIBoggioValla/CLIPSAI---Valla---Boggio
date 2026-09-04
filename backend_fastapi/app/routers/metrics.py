"""Router de métricas — GET /metrics (Issue 19)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession
from ..models import Clip, Job, Video
from ..schemas.metrics import MetricsResponse, RecentActivityItem

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Métricas del usuario autenticado (dashboard)",
)
@router.get(
    "/api/metrics",
    response_model=MetricsResponse,
    summary="Métricas del usuario autenticado (alias)",
    include_in_schema=False,
)
def get_metrics(
    current_user: CurrentUser,
    db: DbSession,
) -> MetricsResponse:
    user_id = current_user.id

    total_jobs: int = db.scalar(
        select(func.count(Job.id))
        .select_from(Job)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id)
    ) or 0

    total_clips: int = db.scalar(
        select(func.count(Clip.id))
        .select_from(Clip)
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id)
    ) or 0

    total_seconds: float = db.scalar(
        select(func.coalesce(func.sum(Video.duration_seconds), 0)).where(Video.user_id == user_id)
    ) or 0
    total_minutes_processed: float = round(float(total_seconds) / 60.0, 2)

    if total_minutes_processed > 0:
        time_saved_hours: float = round(total_minutes_processed * 3 / 60.0, 2)
    else:
        time_saved_hours = round(total_clips * 15 / 60.0, 2)

    platform_rows = db.execute(
        select(Clip.social_network, func.count(Clip.id))
        .select_from(Clip)
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id)
        .group_by(Clip.social_network)
    ).all()

    platform_distribution: dict[str, int] = {"tiktok": 0, "youtube": 0, "instagram": 0}
    for social, cnt in platform_rows:
        if social is None:
            continue
        s = str(social).lower()
        c = int(cnt)
        if s == "tiktok":
            platform_distribution["tiktok"] += c
        elif s in ("youtube", "youtube_shorts"):
            platform_distribution["youtube"] += c
        elif s in ("instagram", "instagram_reels"):
            platform_distribution["instagram"] += c
        else:
            platform_distribution[s] = platform_distribution.get(s, 0) + c

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=6)

    jobs_by_day_rows = db.execute(
        select(func.date(Job.created_at), func.count(Job.id))
        .select_from(Job)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id, func.date(Job.created_at) >= start_date)
        .group_by(func.date(Job.created_at))
    ).all()
    jobs_map: dict[str, int] = {str(r[0]): int(r[1]) for r in jobs_by_day_rows if r[0] is not None}

    clips_by_day_rows = db.execute(
        select(func.date(Clip.created_at), func.count(Clip.id))
        .select_from(Clip)
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id, func.date(Clip.created_at) >= start_date)
        .group_by(func.date(Clip.created_at))
    ).all()
    clips_map: dict[str, int] = {str(r[0]): int(r[1]) for r in clips_by_day_rows if r[0] is not None}

    minutes_by_day_rows = db.execute(
        select(func.date(Video.created_at), func.coalesce(func.sum(Video.duration_seconds), 0))
        .where(Video.user_id == user_id, func.date(Video.created_at) >= start_date)
        .group_by(func.date(Video.created_at))
    ).all()
    minutes_map: dict[str, float] = {
        str(r[0]): round(float(r[1]) / 60.0, 2) for r in minutes_by_day_rows if r[0] is not None
    }

    recent_activity: list[RecentActivityItem] = []
    for i in range(7):
        d = start_date + timedelta(days=i)
        d_str = d.isoformat()
        recent_activity.append(
            RecentActivityItem(
                date=d_str,
                jobs=int(jobs_map.get(d_str, 0)),
                clips=int(clips_map.get(d_str, 0)),
                minutes_processed=float(minutes_map.get(d_str, 0.0)),
            )
        )

    return MetricsResponse(
        total_jobs=int(total_jobs),
        total_clips=int(total_clips),
        total_minutes_processed=float(total_minutes_processed),
        time_saved_hours=float(time_saved_hours),
        platform_distribution=platform_distribution,
        recent_activity=recent_activity,
    )
