"""Router de métricas — GET /metrics (Issue 19)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession
from ..models import Clip, Job, Video
from ..schemas.metrics import MetricsResponse, RecentActivityItem

router = APIRouter(tags=["metrics"])


def _total_de_jobs(db: DbSession, user_id: Any) -> int:
    """Cantidad de jobs del usuario."""
    return db.scalar(
        select(func.count(Job.id))
        .select_from(Job)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id)
    ) or 0


def _total_de_clips(db: DbSession, user_id: Any) -> int:
    """Cantidad de clips del usuario."""
    return db.scalar(
        select(func.count(Clip.id))
        .select_from(Clip)
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id)
    ) or 0


def _minutos_procesados(db: DbSession, user_id: Any) -> float:
    """Minutos totales procesados (duración de los videos del usuario)."""
    total_seconds: float = db.scalar(
        select(func.coalesce(func.sum(Video.duration_seconds), 0)).where(Video.user_id == user_id)
    ) or 0
    return round(float(total_seconds) / 60.0, 2)


def _horas_ahorradas(total_minutes: float, total_clips: int) -> float:
    """Horas ahorradas: 3x los minutos procesados, o 15 min por clip si no hay."""
    if total_minutes > 0:
        return round(total_minutes * 3 / 60.0, 2)
    return round(total_clips * 15 / 60.0, 2)


def _sumar_red(distribution: dict[str, int], red: str, cantidad: int) -> None:
    """Acumula el conteo de clips en la clave canónica de la red."""
    if red == "tiktok":
        distribution["tiktok"] += cantidad
    elif red in ("youtube", "youtube_shorts"):
        distribution["youtube"] += cantidad
    elif red in ("instagram", "instagram_reels"):
        distribution["instagram"] += cantidad
    else:
        distribution[red] = distribution.get(red, 0) + cantidad


def _distribucion_plataformas(db: DbSession, user_id: Any) -> dict[str, int]:
    """Conteo de clips por red social del usuario."""
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
        _sumar_red(platform_distribution, str(social).lower(), int(cnt))
    return platform_distribution


def _jobs_por_dia(db: DbSession, user_id: Any, start_date: Any) -> dict[str, int]:
    """Jobs del usuario por día (fecha ISO → conteo)."""
    jobs_by_day_rows = db.execute(
        select(func.date(Job.created_at), func.count(Job.id))
        .select_from(Job)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id, func.date(Job.created_at) >= start_date)
        .group_by(func.date(Job.created_at))
    ).all()
    return {str(r[0]): int(r[1]) for r in jobs_by_day_rows if r[0] is not None}


def _clips_por_dia(db: DbSession, user_id: Any, start_date: Any) -> dict[str, int]:
    """Clips del usuario por día (fecha ISO → conteo)."""
    clips_by_day_rows = db.execute(
        select(func.date(Clip.created_at), func.count(Clip.id))
        .select_from(Clip)
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id, func.date(Clip.created_at) >= start_date)
        .group_by(func.date(Clip.created_at))
    ).all()
    return {str(r[0]): int(r[1]) for r in clips_by_day_rows if r[0] is not None}


def _minutos_por_dia(db: DbSession, user_id: Any, start_date: Any) -> dict[str, float]:
    """Minutos procesados por día (fecha ISO → minutos redondeados)."""
    minutes_by_day_rows = db.execute(
        select(func.date(Video.created_at), func.coalesce(func.sum(Video.duration_seconds), 0))
        .where(Video.user_id == user_id, func.date(Video.created_at) >= start_date)
        .group_by(func.date(Video.created_at))
    ).all()
    return {
        str(r[0]): round(float(r[1]) / 60.0, 2) for r in minutes_by_day_rows if r[0] is not None
    }


def _actividad_reciente(
    start_date: Any,
    jobs_map: dict[str, int],
    clips_map: dict[str, int],
    minutes_map: dict[str, float],
) -> list[RecentActivityItem]:
    """Actividad de los últimos 7 días para el dashboard."""
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
    return recent_activity


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
    """Métricas del usuario autenticado (dashboard)."""
    user_id = current_user.id

    total_jobs: int = _total_de_jobs(db, user_id)
    total_clips: int = _total_de_clips(db, user_id)
    total_minutes_processed: float = _minutos_procesados(db, user_id)
    time_saved_hours: float = _horas_ahorradas(total_minutes_processed, total_clips)
    platform_distribution = _distribucion_plataformas(db, user_id)

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=6)

    jobs_map = _jobs_por_dia(db, user_id, start_date)
    clips_map = _clips_por_dia(db, user_id, start_date)
    minutes_map = _minutos_por_dia(db, user_id, start_date)
    recent_activity = _actividad_reciente(start_date, jobs_map, clips_map, minutes_map)

    return MetricsResponse(
        total_jobs=int(total_jobs),
        total_clips=int(total_clips),
        total_minutes_processed=float(total_minutes_processed),
        time_saved_hours=float(time_saved_hours),
        platform_distribution=platform_distribution,
        recent_activity=recent_activity,
    )
