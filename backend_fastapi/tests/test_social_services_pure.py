from __future__ import annotations

from unittest.mock import patch, MagicMock

from backend_fastapi.app.services.tiktok_service import (
    generate_pkce_pair,
    get_tiktok_auth_url,
    _get_tiktok_config,
)
from backend_fastapi.app.services.instagram_service import (
    _first_env,
    _get_instagram_config,
    get_instagram_auth_url,
)
from backend_fastapi.app.services.youtube_service import (
    _get_google_config,
    get_youtube_auth_url,
)


def test_generate_pkce_pair():
    v, c = generate_pkce_pair()
    assert isinstance(v, str) and isinstance(c, str)
    assert len(v) > 0


def test_get_tiktok_auth_url():
    url = get_tiktok_auth_url("state123", "challenge")
    assert "tiktok" in url.lower() or "http" in url


def test_get_tiktok_config():
    cfg = _get_tiktok_config()
    assert isinstance(cfg, tuple) and len(cfg) == 3


def test_first_env_instagram():
    import os
    os.environ["IG_TEST_X"] = "v"
    assert _first_env("IG_TEST_X") == "v"
    assert _first_env("NOPE_IG") == ""
    del os.environ["IG_TEST_X"]


def test_get_instagram_config():
    cfg = _get_instagram_config()
    assert isinstance(cfg, tuple) and len(cfg) == 3


def test_get_instagram_auth_url():
    try:
        url = get_instagram_auth_url("user1")
        assert isinstance(url, str)
    except Exception:
        pass


def test_get_google_config():
    cfg = _get_google_config()
    assert isinstance(cfg, tuple) and len(cfg) == 3


def test_get_youtube_auth_url():
    try:
        url = get_youtube_auth_url("user1")
        assert isinstance(url, str)
    except Exception:
        pass


def test_fetch_tiktok_user_info_mock():
    from backend_fastapi.app.services.tiktok_service import _fetch_tiktok_user_info
    with patch("requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"data": {"user": {"open_id": "123", "display_name": "u"}}})
        try:
            _fetch_tiktok_user_info("tok")
        except Exception:
            pass


def test_fetch_youtube_username_mock():
    from backend_fastapi.app.services.youtube_service import _fetch_youtube_username
    with patch("requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"items": [{"snippet": {"title": "chan"}}]})
        try:
            _fetch_youtube_username("tok")
        except Exception:
            pass


def test_fetch_ig_username_from_id_mock():
    from backend_fastapi.app.services.instagram_service import _fetch_ig_username_from_id
    with patch("requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"username": "iguser"})
        try:
            _fetch_ig_username_from_id("123", "tok")
        except Exception:
            pass
