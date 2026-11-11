from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from backend_fastapi.app.routers.stream import _get_owner_video, _effective_status, _event


def test_get_owner_video_via_video_id() -> None:
    db = MagicMock()
    video = SimpleNamespace(id="v1")
    db.get.return_value = video
    clip = SimpleNamespace(video_id="v1", job_id=None)
    assert _get_owner_video(db, clip) is video


def test_get_owner_video_via_job() -> None:
    db = MagicMock()
    job = SimpleNamespace(video_id="v2")
    video = SimpleNamespace(id="v2")
    def get_side_effect(model, pk):
        if model.__name__ == "Job":
            return job
        return video
    db.get.side_effect = get_side_effect
    clip = SimpleNamespace(video_id=None, job_id="j1")
    assert _get_owner_video(db, clip) is video


def test_get_owner_video_none() -> None:
    db = MagicMock()
    db.get.return_value = None
    clip = SimpleNamespace(video_id=None, job_id=None)
    assert _get_owner_video(db, clip) is None


def test_effective_status_publication() -> None:
    c = SimpleNamespace(publication_status="PUBLISHED", status="COMPLETED")
    assert _effective_status(c) == "PUBLISHED"


def test_effective_status_clip() -> None:
    c = SimpleNamespace(publication_status=None, status="FAILED")
    assert _effective_status(c) == "FAILED"


def test_effective_status_unknown() -> None:
    c = SimpleNamespace(publication_status="", status="")
    assert _effective_status(c) == "UNKNOWN"


def test_event() -> None:
    s = _event("x", {"a": 1})
    assert "event: x" in s
    assert "data:" in s
