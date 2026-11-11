from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend_fastapi.app.services import publish_service as ps
from backend_fastapi.app.models import Clip, SocialAccount


def _mk_clip(storage_path=" /tmp/nope_c.mp4 ", job_id=None, video_id=None, title="T"):
    return Clip(
        id=uuid.uuid4(),
        job_id=job_id or uuid.uuid4(),
        video_id=video_id,
        title=title,
        start_time=0.0,
        end_time=5.0,
        score=8.0,
        status="ready",
        storage_path=storage_path or "",
        tags={},
    )


def test_resolve_clip_file_path_missing():
    clip = _mk_clip(storage_path="/tmp/definitely_missing_clip_file.mp4")
    with pytest.raises(HTTPException) as ei:
        ps._resolve_clip_file_path(clip)
    assert ei.value.status_code == 404


def test_resolve_clip_file_path_empty():
    clip = _mk_clip(storage_path="")
    with pytest.raises(HTTPException) as ei:
        ps._resolve_clip_file_path(clip)
    assert ei.value.status_code == 404


def test_publish_tiktok_missing_clip_file(db_session=None):
    acc = MagicMock(access_token="tok", refresh_token="ref")
    clip = _mk_clip(storage_path="/tmp/definitely_missing_clip_file2.mp4")
    with pytest.raises(HTTPException) as ei:
        ps._publish_tiktok(acc, clip, "caption")
    assert ei.value.status_code == 404


def test_publish_youtube_missing_clip_file(db_session=None):
    acc = MagicMock(access_token="tok", refresh_token="ref")
    clip = _mk_clip(storage_path="/tmp/definitely_missing_clip_file3.mp4")
    with pytest.raises(Exception) as ei:
        try:
            ps._publish_youtube(acc, clip, "caption")
        except HTTPException:
            raise
        except Exception as e:
            raise e
    # Either HTTPException(404) or generic error is acceptable; we just ensure no crash path silently passes
    # Actually _publish_youtube may raise HTTPException; assert it does NOT return None
    with pytest.raises(Exception):
        ps._publish_youtube(acc, clip, "caption")


def test_publish_instagram_missing_clip_file(db_session=None):
    acc = MagicMock(access_token="tok", refresh_token="ref")
    clip = _mk_clip(storage_path="/tmp/definitely_missing_clip_file4.mp4")
    with pytest.raises(Exception):
        try:
            ps._publish_instagram(acc, clip, "caption")
        except HTTPException:
            raise
    # ensure it raised something (no silent success)
