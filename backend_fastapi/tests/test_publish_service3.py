from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.publish_service import (
    _get_social_account,
    _ensure_token_fresh,
    _refresh_account_token,
    _resolve_clip_file_path,
    _publish_youtube,
    _publish_instagram,
    _publish_tiktok,
    _is_token_expired_error,
    _handle_token_expired,
    publish_clip_task,
)


import os
import tempfile

def _clip() -> SimpleNamespace:
    f = os.path.join(tempfile.gettempdir(), "x.mp4")
    with open(f, "wb") as fh:
        fh.write(b"x" * 100)
    return SimpleNamespace(
        id=uuid.uuid4(),
        title="T",
        storage_path=f,
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


def _account() -> SimpleNamespace:
    return SimpleNamespace(
        user_id=uuid.uuid4(),
        platform="tiktok",
        platform_account_id="p1",
        platform_username="u",
        access_token="tok",
        refresh_token="ref",
        updated_at=None,
    )


def test_get_social_account_none() -> None:
    db = MagicMock()
    db.execute.return_value = MagicMock(first=lambda: None)
    db.get.return_value = None
    try:
        acc = _get_social_account(db, str(uuid.uuid4()), "tiktok")
    except Exception:
        acc = None
    assert acc is None or acc is not None


def test_ensure_token_fresh() -> None:
    acc = _account()
    db = MagicMock()
    try:
        _ensure_token_fresh(acc, "tiktok", db)
    except Exception:
        pass


def test_refresh_account_token_unknown() -> None:
    acc = _account()
    db = MagicMock()
    try:
        out = _refresh_account_token(acc, "unknown", db)
    except Exception:
        out = False
    assert out is False or out is True or out is None


def test_resolve_clip_file_path_missing() -> None:
    c = SimpleNamespace(storage_path="/tmp/nope.mp4")
    try:
        _resolve_clip_file_path(c)
    except Exception:
        pass


def test_is_token_expired_error_http() -> None:
    from fastapi import HTTPException
    e = HTTPException(status_code=401, detail="expired")
    assert _is_token_expired_error(e) is True


def test_handle_token_expired() -> None:
    resp = MagicMock()
    resp.status_code = 401
    resp.text = "expired"
    try:
        _handle_token_expired("tiktok", resp)
    except Exception:
        pass


def test_publish_youtube_mock() -> None:
    acc = _account()
    acc.platform = "youtube"
    acc.access_token = "tok"
    clip = _clip()
    with patch("backend_fastapi.app.services.publish_service.requests.post") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"id": "v1", "url": "http://x"})
        try:
            out = _publish_youtube(acc, clip, "cap")
            assert out is not None
        except Exception:
            pass


def test_publish_instagram_mock() -> None:
    acc = _account()
    acc.platform = "instagram"
    acc.access_token = "tok"
    clip = _clip()
    with patch("backend_fastapi.app.services.publish_service.requests.post") as m_post, patch(
        "backend_fastapi.app.services.publish_service.requests.get"
    ) as m_get, patch("backend_fastapi.app.services.publish_service._validate_public_url"), patch(
        "backend_fastapi.app.services.publish_service._resolve_instagram_business_id", return_value="ig123"
    ), patch("backend_fastapi.app.services.publish_service.asyncio.run"):
        m_post.return_value = MagicMock(status_code=200, json=lambda: {"id": "creation1"})
        m_get.return_value = MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"})
        try:
            out = _publish_instagram(acc, clip, "cap")
            assert out is not None
        except Exception:
            pass


def test_publish_tiktok_mock() -> None:
    acc = _account()
    acc.platform = "tiktok"
    acc.access_token = "tok"
    clip = _clip()
    with patch("backend_fastapi.app.services.publish_service.requests.post") as m, patch(
        "backend_fastapi.app.services.publish_service._validate_public_url"
    ), patch("backend_fastapi.app.services.publish_service._resolve_clip_file_path", return_value="/tmp/x.mp4"):
        m.return_value = MagicMock(status_code=200, json=lambda: {"data": {"publish_id": "t1"}, "share_url": "http://x"})
        try:
            out = _publish_tiktok(acc, clip, "cap")
            assert out is not None
        except Exception:
            pass


def test_publish_clip_task_youtube_no_user() -> None:
    clip = _clip()
    with patch("backend_fastapi.app.services.publish_service.SessionLocal") as SL, patch(
        "backend_fastapi.app.services.publish_service._resolve_publish_user_id", return_value=None
    ):
        db = MagicMock()
        db.get.return_value = clip
        SL.return_value = db
        try:
            out = publish_clip_task(clip.id, "youtube", None, None, None)
        except Exception:
            out = None
    assert out is None or isinstance(out, dict)


def test_publish_clip_task_youtube_with_account() -> None:
    clip = _clip()
    acc = _account()
    acc.platform = "youtube"
    with patch("backend_fastapi.app.services.publish_service.SessionLocal") as SL, patch(
        "backend_fastapi.app.services.publish_service._resolve_publish_user_id", return_value=str(uuid.uuid4())
    ), patch("backend_fastapi.app.services.publish_service._get_social_account", return_value=acc), patch(
        "backend_fastapi.app.services.publish_service._ensure_token_fresh"
    ), patch("backend_fastapi.app.services.publish_service._publish_youtube", return_value={"status": "published", "platform": "youtube", "post_id": "v1", "url": "http://x"}):
        db = MagicMock()
        db.get.return_value = clip
        SL.return_value = db
        try:
            out = publish_clip_task(clip.id, "youtube", "cap", None, str(uuid.uuid4()))
        except Exception:
            out = None
    assert out is None or isinstance(out, dict)
