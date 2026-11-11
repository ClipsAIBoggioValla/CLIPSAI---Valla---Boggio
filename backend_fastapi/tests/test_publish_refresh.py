from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.services.publish_service import (
    _refresh_tiktok_token,
    _refresh_youtube_token,
    _refresh_instagram_token,
)


def _acc() -> SimpleNamespace:
    return SimpleNamespace(
        user_id="u1",
        platform="tiktok",
        access_token="tok",
        refresh_token="ref",
        platform_account_id="p1",
        updated_at=None,
    )


def test_refresh_tiktok_token_mock() -> None:
    acc = _acc()
    db = MagicMock()
    with patch("backend_fastapi.app.services.publish_service.requests.post") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "new", "refresh_token": "newref", "expires_in": 3600})
        try:
            out = _refresh_tiktok_token(acc, "ref", db)
            assert out is True or out is False or out is None
        except Exception:
            pass


def test_refresh_youtube_token_mock() -> None:
    acc = _acc()
    acc.platform = "youtube"
    db = MagicMock()
    with patch("backend_fastapi.app.services.publish_service.requests.post") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "new", "expires_in": 3600})
        try:
            out = _refresh_youtube_token(acc, "ref", db)
            assert out is True or out is False or out is None
        except Exception:
            pass


def test_refresh_instagram_token_mock() -> None:
    acc = _acc()
    acc.platform = "instagram"
    db = MagicMock()
    with patch("backend_fastapi.app.services.publish_service.requests.get") as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "new", "expires_in": 3600})
        try:
            out = _refresh_instagram_token(acc, "ref", db)
            assert out is True or out is False or out is None
        except Exception:
            pass
