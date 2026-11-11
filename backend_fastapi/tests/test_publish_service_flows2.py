from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend_fastapi.app.services import publish_service as ps
from backend_fastapi.app.models import SocialAccount


def _mk_account(platform="tiktok", token="tok", refresh="ref", expires=None):
    return SocialAccount(
        user_id=uuid.uuid4(),
        platform=platform,
        platform_account_id="pid",
        platform_username="user",
        access_token=token,
        refresh_token=refresh,
        token_expires_at=expires or (datetime.now(timezone.utc) + timedelta(hours=1)),
    )


def _tiktok_creds_ok():
    s = MagicMock()
    s.tiktok_client_key = "ck"
    s.tiktok_client_secret = "cs"
    return s


def _tiktok_creds_empty():
    s = MagicMock()
    s.tiktok_client_key = ""
    s.tiktok_client_secret = ""
    return s


def _insta_creds_empty():
    s = MagicMock()
    s.facebook_client_id = ""
    s.facebook_client_secret = ""
    s.instagram_client_id = ""
    s.instagram_client_secret = ""
    return s


def test_handle_token_expired_401():
    with pytest.raises(HTTPException) as ei:
        ps._handle_token_expired("tiktok", MagicMock(status_code=401))
    assert ei.value.status_code == 400


def test_handle_token_expired_ok():
    assert ps._handle_token_expired("tiktok", MagicMock(status_code=200)) is None


def test_refresh_tiktok_no_creds(db_session=None):
    acc = _mk_account()
    with patch.object(ps, "get_settings", return_value=_tiktok_creds_empty()), patch.dict(
        "os.environ", {"TIKTOK_CLIENT_KEY": "", "TIKTOK_CLIENT_SECRET": ""}
    ):
        assert ps._refresh_tiktok_token(acc, "ref", db_session) is False


def test_refresh_tiktok_success(db_session=None):
    acc = _mk_account()
    resp = MagicMock(status_code=200, text="ok", json=lambda: {"access_token": "newtok", "refresh_token": "newref", "expires_in": 3600})
    dbm = MagicMock()
    with patch.object(ps, "get_settings", return_value=_tiktok_creds_ok()), patch.object(ps.requests, "post", return_value=resp):
        ok = ps._refresh_tiktok_token(acc, "ref", dbm)
    assert ok is True
    assert acc.access_token == "newtok"
    assert dbm.add.called


def test_refresh_tiktok_fail(db_session=None):
    acc = _mk_account()
    resp = MagicMock(status_code=401, text="unauthorized", json=lambda: {"error": "x"})
    with patch.object(ps, "get_settings", return_value=_tiktok_creds_ok()), patch.object(ps.requests, "post", return_value=resp):
        with pytest.raises(Exception):
            ps._refresh_tiktok_token(acc, "ref", db_session)


def test_refresh_youtube_no_creds(db_session=None):
    acc = _mk_account(platform="youtube")
    with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}):
        res = ps._refresh_youtube_token(acc, "ref", db_session)
    assert res is False or res is None


def test_refresh_instagram_no_creds(db_session=None):
    acc = _mk_account(platform="instagram")
    res = ps._refresh_instagram_token(acc, "ref", db_session)
    assert res is False or res is None


def test_refresh_account_token_dispatch(db_session=None):
    acc = _mk_account()
    with patch.object(ps, "get_settings", return_value=_tiktok_creds_empty()), patch.dict(
        "os.environ", {"TIKTOK_CLIENT_KEY": "", "TIKTOK_CLIENT_SECRET": ""}
    ):
        assert ps._refresh_account_token(acc, "tiktok", db_session) is False
    acc2 = _mk_account(platform="youtube")
    with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}):
        assert ps._refresh_account_token(acc2, "youtube", db_session) is False
    acc3 = _mk_account(platform="instagram")
    with patch.dict(
        "os.environ",
        {"FACEBOOK_CLIENT_ID": "", "FACEBOOK_CLIENT_SECRET": "", "INSTAGRAM_CLIENT_ID": "", "INSTAGRAM_CLIENT_SECRET": ""},
    ):
        res3 = ps._refresh_account_token(acc3, "instagram", db_session)
    assert res3 is None or res3 is False
    assert ps._refresh_account_token(acc, "unknown", db_session) is None or ps._refresh_account_token(acc, "unknown", db_session) is False


def test_is_token_expired_error_true_false():
    assert ps._is_token_expired_error(Exception("token expirado")) is True
    assert ps._is_token_expired_error(Exception("everything fine")) is False


def test_ensure_token_fresh_no_action(db_session=None):
    acc = _mk_account()
    acc.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    ps._ensure_token_fresh(acc, "tiktok", db_session)
    assert acc.access_token == "tok"


def test_generate_fake_id(db_session=None):
    fid = ps._generate_fake_id()
    assert isinstance(fid, str) and len(fid) > 0
