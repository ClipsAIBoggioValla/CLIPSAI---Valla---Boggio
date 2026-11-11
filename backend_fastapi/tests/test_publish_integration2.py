from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services.publish_service import _get_social_account, _resolve_publish_user_id, _lookup_social_account_raw


def test_resolve_publish_user_id_no_video(db_session):
    clip = SimpleNamespace(video_id=None, job_id=None)
    out = _resolve_publish_user_id(db_session, clip)
    assert out is None


def test_resolve_publish_user_id_with_video(db_session):
    from backend_fastapi.app.models import Usuario, Video
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    v = Video(user_id=u.id, filename="v.mp4", filepath="/tmp/v.mp4")
    db_session.add(v)
    db_session.commit()
    clip = SimpleNamespace(video_id=v.id, job_id=None)
    out = _resolve_publish_user_id(db_session, clip)
    assert out == str(u.id)


def test_get_social_account_none_integration(db_session):
    from fastapi import HTTPException
    try:
        out = _get_social_account(db_session, str(uuid.uuid4()), "tiktok")
    except HTTPException:
        out = None
    assert out is None


def test_lookup_social_account_raw_none(db_session):
    out = _lookup_social_account_raw(db_session, uuid.uuid4(), "tiktok")
    assert out is None
