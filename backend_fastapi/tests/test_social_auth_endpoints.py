from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.routers import social_auth as sa


def test_youtube_connect() -> None:
    user = SimpleNamespace(id="u1")
    with patch("backend_fastapi.app.routers.social_auth.yt_get_youtube_auth_url", return_value="http://auth"):
        out = sa.youtube_connect(user)
    assert out == {"auth_url": "http://auth"}


def test_instagram_connect() -> None:
    user = SimpleNamespace(id="u1")
    with patch.dict(os.environ, {"INSTAGRAM_CLIENT_ID": "cid"}, clear=False), patch(
        "backend_fastapi.app.routers.social_auth.ig_get_instagram_auth_url", return_value="http://auth"
    ):
        out = sa.instagram_connect(user)
    assert out["auth_url"] == "http://auth"
    assert out["url"] == "http://auth"


def test_tiktok_connect() -> None:
    user = SimpleNamespace(id="u1")
    with patch("backend_fastapi.app.routers.social_auth.tt_generate_pkce_pair", return_value=("v", "c")), patch(
        "backend_fastapi.app.routers.social_auth.tt_get_tiktok_auth_url", return_value="http://auth"
    ), patch("backend_fastapi.app.routers.social_auth.tt_encode_state", return_value="state"):
        out = sa.tiktok_connect(user)
    assert "auth_url" in out


def test_youtube_callback_error() -> None:
    db = MagicMock()
    resp = sa.youtube_callback(request=MagicMock(), db=db, code=None, state=None, error="boom")
    assert resp.status_code == 302


def test_youtube_callback_missing_code() -> None:
    db = MagicMock()
    resp = sa.youtube_callback(request=MagicMock(), db=db, code=None, state=None, error=None)
    assert resp.status_code == 302


def test_youtube_callback_success() -> None:
    db = MagicMock()
    with patch("backend_fastapi.app.routers.social_auth.yt_exchange_code_for_tokens", return_value={"access_token": "t"}), patch(
        "backend_fastapi.app.routers.social_auth.yt_decode_state", return_value="u1"
    ), patch("backend_fastapi.app.routers.social_auth.yt_save_youtube_tokens"):
        resp = sa.youtube_callback(request=MagicMock(), db=db, code="code", state="state", error=None)
    assert resp.status_code == 302


def test_instagram_callback_error() -> None:
    db = MagicMock()
    resp = sa.instagram_callback(request=MagicMock(), db=db, code=None, state=None, error="boom")
    assert resp.status_code == 302


def test_tiktok_callback_error() -> None:
    db = MagicMock()
    resp = sa.tiktok_callback(request=MagicMock(), db=db, code=None, state=None, error="boom")
    assert resp.status_code == 302
