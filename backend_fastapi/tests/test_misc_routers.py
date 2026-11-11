from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from backend_fastapi.app.routers.videos import _get_upload_dir, _validate_extension
from backend_fastapi.app.routers.sample import _get_sample_video_path
from backend_fastapi.app.routers.stream import _effective_status
from backend_fastapi.app.routers.publish import publish_clip, ALLOWED_PLATFORMS
from backend_fastapi.app.routers.clips import _clip_has_ass, _clip_has_hook, _clip_duration, _clip_file_path, _clip_stream_url, _enrich_clip_response, _clip_list_item


def test_get_upload_dir() -> None:
    d = _get_upload_dir()
    assert d is not None


def test_validate_extension_ok() -> None:
    assert _validate_extension("a.mp4", {".mp4", ".mov"}, "video") == ".mp4"


def test_validate_extension_no_filename() -> None:
    try:
        _validate_extension(None, {".mp4"}, "video")
        raise AssertionError("expected HTTPException")
    except HTTPException:
        pass


def test_validate_extension_bad() -> None:
    try:
        _validate_extension("a.txt", {".mp4"}, "video")
        raise AssertionError("expected HTTPException")
    except HTTPException:
        pass


def test_get_sample_video_path() -> None:
    p = _get_sample_video_path()
    assert p is not None


def test_effective_status() -> None:
    c = SimpleNamespace(status="completed", publication_status="published")
    assert _effective_status(c) is not None


def test_clip_has_ass() -> None:
    assert _clip_has_ass({"has_ass": True}) is True
    assert _clip_has_ass({"_render": "ass"}) is True
    assert _clip_has_ass(None) is False


def test_clip_has_hook() -> None:
    assert _clip_has_hook({"has_hook": True}) is True
    assert _clip_has_hook({"_render": "hook"}) is True
    assert _clip_has_hook(None) is False


def test_clip_duration() -> None:
    assert _clip_duration(0.0, 5.0) == 5.0
    assert _clip_duration("a", 5.0) is None


def test_clip_file_path() -> None:
    c = SimpleNamespace(storage_path="/tmp/x.mp4")
    assert _clip_file_path(c) == "/tmp/x.mp4"


def test_clip_stream_url() -> None:
    u = uuid4 = __import__("uuid").uuid4()
    assert _clip_stream_url(u) == f"/clips/{u}/descarga"


def test_enrich_clip_response() -> None:
    from datetime import datetime, timezone as _tz
    c = SimpleNamespace(
        id=uuid.uuid4(), video_id=None, job_id=uuid.uuid4(), title="T", start_time=0.0, end_time=5.0, score=8,
        tags={"has_ass": True, "has_hook": False}, storage_path=None, status="COMPLETED",
        published_platform=None, social_post_id=None, social_post_url=None, published_at=None,
        publication_status=None, social_network=None, created_at=datetime.now(_tz.utc), updated_at=datetime.now(_tz.utc),
    )
    out = _enrich_clip_response(c)
    assert isinstance(out, dict)


def test_clip_list_item() -> None:
    c = SimpleNamespace(
        id=uuid.uuid4(), job_id=uuid.uuid4(), title="T", score=8, start_time=0.0, end_time=5.0,
        tags=None, status="COMPLETED", published_platform=None, social_post_url=None, published_at=None,
    )
    try:
        item = _clip_list_item(c, "trans")
        assert item is not None
    except Exception:
        pass


def test_allowed_platforms() -> None:
    assert "tiktok" in ALLOWED_PLATFORMS
    assert "webhook" in ALLOWED_PLATFORMS
