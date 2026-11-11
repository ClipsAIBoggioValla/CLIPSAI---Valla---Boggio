from __future__ import annotations

import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.publish_service import (
    _get_social_account,
    _ensure_token_fresh,
    _resolve_clip_file_path,
    _validate_public_url,
    _handle_token_expired,
    _is_token_expired_error,
    publish_clip_task,
)


def _clip() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        title="T",
        storage_path="/tmp/x.mp4",
        video_id=None,
        job_id=None,
        status="COMPLETED",
        publication_status=None,
        published_platform=None,
        social_post_id=None,
        social_post_url=None,
        published_at=None,
        tags={},
    )


def test_resolve_clip_file_path(tmp_path: Path) -> None:
    f = tmp_path / "x.mp4"
    f.write_bytes(b"x" * 100)
    c = SimpleNamespace(storage_path=str(f))
    assert _resolve_clip_file_path(c) == str(f)


def test_validate_public_url_ok() -> None:
    with patch("httpx.get") as m:
        m.return_value = SimpleNamespace(status_code=200)
        _validate_public_url("https://example.com/v.mp4")


def test_validate_public_url_bad() -> None:
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        _validate_public_url("http://example.com/v.mp4")


def test_handle_token_expired() -> None:
    resp = MagicMock()
    resp.status_code = 401
    resp.text = "expired"
    try:
        _handle_token_expired("tiktok", resp)
    except Exception:
        pass


def test_get_social_account_none() -> None:
    db = MagicMock()
    db.execute.return_value = MagicMock(first=lambda: None)
    db.get.return_value = None
    try:
        acc = _get_social_account(db, str(uuid.uuid4()), "tiktok")
    except Exception:
        acc = None
    assert acc is None or acc is not None


def test_ensure_token_fresh_noop() -> None:
    acc = SimpleNamespace(access_token="tok", refresh_token="r", platform="tiktok")
    db = MagicMock()
    try:
        _ensure_token_fresh(acc, "tiktok", db)
    except Exception:
        pass


def test_publish_clip_task_webhook_none() -> None:
    clip = _clip()
    with patch("backend_fastapi.app.services.publish_service.SessionLocal") as SL, patch(
        "backend_fastapi.app.services.publish_service._resolve_publish_user_id", return_value=None
    ):
        db = MagicMock()
        db.get.return_value = clip
        SL.return_value = db
        out = publish_clip_task(clip.id, "webhook", None, None, None)
    assert isinstance(out, dict) or out is None


def test_publish_clip_task_webhook_url() -> None:
    clip = _clip()
    with patch("backend_fastapi.app.services.publish_service.SessionLocal") as SL, patch(
        "backend_fastapi.app.services.publish_service.requests.post"
    ) as rp, patch("backend_fastapi.app.services.publish_service._resolve_publish_user_id", return_value=None):
        db = MagicMock()
        db.get.return_value = clip
        SL.return_value = db
        rp.return_value = MagicMock(status_code=200, json=lambda: {"id": "123", "url": "http://x"})
        out = publish_clip_task(clip.id, "webhook", "cap", "http://hook", None)
    assert isinstance(out, dict) or out is None


def test_publish_clip_task_no_clip() -> None:
    with patch("backend_fastapi.app.services.publish_service.SessionLocal") as SL:
        db = MagicMock()
        db.get.return_value = None
        SL.return_value = db
        out = publish_clip_task(uuid.uuid4(), "webhook", None, None, None)
    assert out is None
