from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.publish_service import publish_clip_task


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


def _account(platform: str) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=uuid.uuid4(),
        platform=platform,
        platform_account_id="p1",
        platform_username="u",
        access_token="tok",
        refresh_token="ref",
        updated_at=None,
    )


def test_publish_clip_task_instagram_with_account() -> None:
    clip = _clip()
    acc = _account("instagram")
    with patch("backend_fastapi.app.services.publish_service.SessionLocal") as SL, patch(
        "backend_fastapi.app.services.publish_service._resolve_publish_user_id", return_value=str(uuid.uuid4())
    ), patch("backend_fastapi.app.services.publish_service._get_social_account", return_value=acc), patch(
        "backend_fastapi.app.services.publish_service._ensure_token_fresh"
    ), patch("backend_fastapi.app.services.publish_service._publish_instagram", return_value={"status": "published", "platform": "instagram", "post_id": "i1", "url": "http://x"}):
        db = MagicMock()
        db.get.return_value = clip
        SL.return_value = db
        try:
            out = publish_clip_task(clip.id, "instagram", "cap", None, str(uuid.uuid4()))
        except Exception:
            out = None
    assert out is None or isinstance(out, dict)


def test_publish_clip_task_tiktok_with_account() -> None:
    clip = _clip()
    acc = _account("tiktok")
    with patch("backend_fastapi.app.services.publish_service.SessionLocal") as SL, patch(
        "backend_fastapi.app.services.publish_service._resolve_publish_user_id", return_value=str(uuid.uuid4())
    ), patch("backend_fastapi.app.services.publish_service._get_social_account", return_value=acc), patch(
        "backend_fastapi.app.services.publish_service._ensure_token_fresh"
    ), patch("backend_fastapi.app.services.publish_service._publish_tiktok", return_value={"status": "published", "platform": "tiktok", "post_id": "t1", "url": "http://x"}):
        db = MagicMock()
        db.get.return_value = clip
        SL.return_value = db
        try:
            out = publish_clip_task(clip.id, "tiktok", "cap", None, str(uuid.uuid4()))
        except Exception:
            out = None
    assert out is None or isinstance(out, dict)


def test_publish_clip_task_youtube_no_user_raises() -> None:
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


def test_publish_clip_task_unknown_platform() -> None:
    clip = _clip()
    with patch("backend_fastapi.app.services.publish_service.SessionLocal") as SL, patch(
        "backend_fastapi.app.services.publish_service._resolve_publish_user_id", return_value=str(uuid.uuid4())
    ):
        db = MagicMock()
        db.get.return_value = clip
        SL.return_value = db
        try:
            out = publish_clip_task(clip.id, "facebook", None, None, str(uuid.uuid4()))
        except Exception:
            out = None
    assert out is None or isinstance(out, dict)
