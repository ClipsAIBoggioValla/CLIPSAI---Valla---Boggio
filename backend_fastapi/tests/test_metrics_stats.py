from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend_fastapi.app.routers.metrics import get_metrics
from backend_fastapi.app.routers.stats import get_stats_summary


def _mk_user() -> SimpleNamespace:
    return SimpleNamespace(id="00000000-0000-0000-0000-000000000001")


def test_get_metrics_zero() -> None:
    db = MagicMock()
    db.scalar.return_value = 0
    db.execute.return_value = MagicMock(all=lambda: [])
    resp = get_metrics(_mk_user(), db)
    assert resp.total_jobs == 0
    assert resp.total_clips == 0
    assert resp.total_minutes_processed == 0.0


def test_get_metrics_full() -> None:
    db = MagicMock()
    db.scalar.side_effect = [3, 7, 120.0]
    rows = [
        ("tiktok", 2),
        ("youtube_shorts", 1),
    ]
    db.execute.return_value = MagicMock(all=lambda: rows)
    resp = get_metrics(_mk_user(), db)
    assert resp.total_jobs == 3
    assert resp.total_clips == 7
    assert resp.total_minutes_processed == 2.0


def test_get_stats_summary() -> None:
    from datetime import datetime, timezone as _tz
    from backend_fastapi.app.schemas.stats import RecentJobSummary
    db = MagicMock()
    row = MagicMock()
    row.total_clips = 5
    row.avg_score = 7.5
    row.low = 1
    row.medium = 2
    row.high = 2
    recent = RecentJobSummary(id=uuid.uuid4(), status="COMPLETED", created_at=datetime.now(_tz.utc))
    db.execute.return_value = MagicMock(one=lambda: row, scalar_one_or_none=lambda: recent)
    db.scalar.return_value = 4
    resp = get_stats_summary(_mk_user(), db)
    assert resp.total_videos == 4
    assert resp.total_clips == 5
    assert resp.avg_score == 7.5
    assert len(resp.score_distribution) == 3
    assert resp.recent_job is not None


def test_get_stats_summary_no_recent_job() -> None:
    db = MagicMock()
    row = MagicMock()
    row.total_clips = 0
    row.avg_score = None
    row.low = 0
    row.medium = 0
    row.high = 0
    db.execute.return_value = MagicMock(one=lambda: row, scalar_one_or_none=lambda: None)
    db.scalar.return_value = 0
    resp = get_stats_summary(_mk_user(), db)
    assert resp.recent_job is None
    assert resp.avg_score == 0.0
