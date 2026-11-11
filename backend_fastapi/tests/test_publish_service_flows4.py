from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend_fastapi.app.services import publish_service as ps
from backend_fastapi.app.models import Clip, SocialAccount


def _mk_account(platform="tiktok", token="tok"):
    return SocialAccount(
        user_id=uuid.uuid4(),
        platform=platform,
        platform_account_id="pid",
        platform_username="user",
        access_token=token,
        refresh_token="ref",
    )


def _mk_clip():
    return Clip(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        video_id=None,
        title="T",
        start_time=0.0,
        end_time=5.0,
        score=8.0,
        status="ready",
        storage_path="/tmp/c.mp4",
        tags={},
    )


def test_validate_public_url_ok(monkeypatch):
    class R:
        status_code = 200

    monkeypatch.setattr("httpx.get", lambda *a, **k: R())
    ps._validate_public_url("https://api.clipsai.xyz/clips/x/descarga")
    assert True


def test_validate_public_url_bad(monkeypatch):
    class R:
        status_code = 500

    monkeypatch.setattr("httpx.get", lambda *a, **k: R())
    with pytest.raises(HTTPException) as ei:
        ps._validate_public_url("https://api.clipsai.xyz/clips/x/descarga")
    assert ei.value.status_code == 400


def test_resolve_instagram_business_id_fail():
    acc = _mk_account(platform="instagram")
    with patch.object(ps.requests, "get", side_effect=Exception("network down")):
        with pytest.raises(HTTPException) as ei:
            ps._resolve_instagram_business_id(acc)
    assert ei.value.status_code == 400


def test_lookup_social_account_raw_success(db_session=None):
    acc = MagicMock()
    db = MagicMock()
    row = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "platform": "tiktok",
        "platform_account_id": "pid",
        "access_token": "tok",
        "refresh_token": "ref",
    }
    db.execute.return_value.mappings.return_value.first.return_value = row
    out = ps._lookup_social_account_raw(db, uuid.uuid4(), "tiktok")
    assert out is not None
    assert out.access_token == "tok"


def test_get_public_video_url_format():
    clip = _mk_clip()
    url = ps._get_public_video_url(clip)
    assert url.startswith("https://")
    assert "/clips/" in url
