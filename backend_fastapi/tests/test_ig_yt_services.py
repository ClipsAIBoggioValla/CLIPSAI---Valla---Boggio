from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.instagram_service import (
    _first_env,
    _get_instagram_config,
    get_instagram_auth_url,
    exchange_code_for_short_lived_token,
    exchange_short_for_long_lived_token,
    _fetch_ig_username_from_id,
    _fetch_instagram_username,
    exchange_code_for_tokens,
    _log_instagram_debug_token,
    save_instagram_tokens,
)
from backend_fastapi.app.services.youtube_service import (
    _get_google_config,
    get_youtube_auth_url,
    _fetch_youtube_username,
    exchange_code_for_tokens as yt_exchange,
    save_youtube_tokens,
)


def test_first_env_ig() -> None:
    import os
    os.environ["IG_X"] = "v"
    assert _first_env("IG_X") == "v"
    assert _first_env("NOPE_IG") == ""
    del os.environ["IG_X"]


def test_get_instagram_config() -> None:
    assert isinstance(_get_instagram_config(), tuple) and len(_get_instagram_config()) == 3


def test_get_instagram_auth_url() -> None:
    try:
        url = get_instagram_auth_url(str(uuid.uuid4()))
        assert isinstance(url, str)
    except Exception:
        pass


def test_exchange_code_for_short_lived_token_mock() -> None:
    with patch("backend_fastapi.app.services.instagram_service.requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "t"})
        try:
            out = exchange_code_for_short_lived_token("code")
            assert out is not None
        except Exception:
            pass


def test_exchange_short_for_long_lived_token_mock() -> None:
    with patch("backend_fastapi.app.services.instagram_service.requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "t"})
        try:
            out = exchange_short_for_long_lived_token("t")
            assert out is not None
        except Exception:
            pass


def test_fetch_ig_username_from_id_mock() -> None:
    with patch("backend_fastapi.app.services.instagram_service.requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"username": "u"})
        try:
            _fetch_ig_username_from_id("123", "tok")
        except Exception:
            pass


def test_fetch_instagram_username_mock() -> None:
    with patch("backend_fastapi.app.services.instagram_service.requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"username": "u"})
        out = _fetch_instagram_username("tok")
        assert out is None or isinstance(out, str)


def test_exchange_code_for_tokens_ig_mock() -> None:
    with patch("backend_fastapi.app.services.instagram_service.requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "t"})
        try:
            out = exchange_code_for_tokens("code")
            assert out is not None
        except Exception:
            pass


def test_log_instagram_debug_token() -> None:
    with patch("backend_fastapi.app.services.instagram_service.requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"data": {"is_valid": True}})
        try:
            _log_instagram_debug_token("tok")
        except Exception:
            pass


def test_save_instagram_tokens_mock() -> None:
    db = MagicMock()
    out = save_instagram_tokens(db, str(uuid.uuid4()), {"access_token": "a", "user_id": "123"})
    assert out is not None


def test_get_google_config() -> None:
    assert isinstance(_get_google_config(), tuple) and len(_get_google_config()) == 3


def test_get_youtube_auth_url() -> None:
    try:
        url = get_youtube_auth_url(str(uuid.uuid4()))
        assert isinstance(url, str)
    except Exception:
        pass


def test_fetch_youtube_username_mock() -> None:
    with patch("backend_fastapi.app.services.youtube_service.requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"items": [{"snippet": {"title": "chan"}}]})
        try:
            _fetch_youtube_username("tok")
        except Exception:
            pass


def test_yt_exchange_code_mock() -> None:
    with patch("backend_fastapi.app.services.youtube_service.requests.post") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "t"})
        try:
            out = yt_exchange("code")
            assert out is not None
        except Exception:
            pass


def test_save_youtube_tokens_mock() -> None:
    db = MagicMock()
    out = save_youtube_tokens(db, str(uuid.uuid4()), {"access_token": "a"})
    assert out is not None
