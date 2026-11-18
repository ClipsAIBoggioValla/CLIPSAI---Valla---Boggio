"""Router de estadísticas para Dashboard — GET /stats/summary (Issue 15)."""

from __future__ import annotations

from sqlalchemy import and_, case, func, select

from fastapi import APIRouter
from typing import Any

from ..deps import CurrentUser, DbSession
from ..models import Clip, Job, Video
from ..schemas.stats import RecentJobSummary, ScoreDistributionItem, StatsSummaryResponse

router = APIRouter(prefix="/stats", tags=["stats"])


def _total_de_videos(db: DbSession, user_id: Any) -> int:
    """Cantidad de videos del usuario."""
    return db.scalar(select(func.count(Video.id)).where(Video.user_id == user_id)) or 0


def _conteo_or0(valor: Any) -> int:
    """Conteo seguro de una fila agregada (None → 0)."""
    return int(valor or 0)


def _fila_a_resumen(row: Any) -> tuple[int, float, list[ScoreDistributionItem]]:
    """Convierte la fila agregada en (total_clips, avg_score, distribución)."""
    avg_score: float = round(float(row.avg_score), 1) if row.avg_score is not None else 0.0
    score_distribution = [
        ScoreDistributionItem(range="0-40", count=_conteo_or0(row.low), label="Bajo"),
        ScoreDistributionItem(range="41-70", count=_conteo_or0(row.medium), label="Medio"),
        ScoreDistributionItem(range="71-100", count=_conteo_or0(row.high), label="Alto"),
    ]
    return _conteo_or0(row.total_clips), avg_score, score_distribution


def _resumen_de_clips(db: DbSession, user_id: Any) -> tuple[int, float, list[ScoreDistributionItem]]:
    """(total_clips, avg_score, distribución) de los clips del usuario."""
    video_ids_subq = select(Video.id).where(Video.user_id == user_id)

    agg_stmt = select(
        func.count(Clip.id).label("total_clips"),
        func.avg(Clip.score).label("avg_score"),
        func.count(case((and_(Clip.score >= 0, Clip.score <= 40), 1))).label("low"),
        func.count(case((and_(Clip.score >= 41, Clip.score <= 70), 1))).label("medium"),
        func.count(case((and_(Clip.score >= 71, Clip.score <= 100), 1))).label("high"),
    ).where(Clip.video_id.in_(video_ids_subq))

    row = db.execute(agg_stmt).one()

    return _fila_a_resumen(row)


def _job_reciente(db: DbSession, user_id: Any) -> RecentJobSummary | None:
    """Resumen del último job del usuario, o None si no tiene."""
    recent_job_row = db.execute(
        select(Job)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == user_id)
        .order_by(Job.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if recent_job_row is None:
        return None
    return RecentJobSummary.model_validate(recent_job_row)


@router.get(
    "/summary",
    response_model=StatsSummaryResponse,
    summary="Resumen de estadísticas del usuario autenticado",
)
def get_stats_summary(
    current_user: CurrentUser,
    db: DbSession,
) -> StatsSummaryResponse:
    """Resumen de estadísticas del usuario autenticado."""
    user_id = current_user.id

    total_videos: int = _total_de_videos(db, user_id)
    total_clips, avg_score, score_distribution = _resumen_de_clips(db, user_id)

    return StatsSummaryResponse(
        total_videos=total_videos,
        total_clips=total_clips,
        avg_score=avg_score,
        estimated_time_saved_minutes=total_clips * 15,
        score_distribution=score_distribution,
        recent_job=_job_reciente(db, user_id),
    )
