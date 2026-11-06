from __future__ import annotations

import os
from unittest.mock import MagicMock

from backend_fastapi.app.services.publish_service import (
    _first_env,
    _generate_fake_id,
    _get_ngrok_domain,
    _get_public_video_url,
    _is_token_expired_error,
)


def test_first_env():
    os.environ["FOO_BAR_X"] = "val"
    assert _first_env("FOO_BAR_X", "NOPE") == "val"
    assert _first_env("NOPE_XYZ") == ""
    del os.environ["FOO_BAR_X"]


def test_generate_fake_id():
    fid = _generate_fake_id()
    assert isinstance(fid, str) and len(fid) > 0


def test_get_ngrok_domain():
    d = _get_ngrok_domain()
    assert isinstance(d, str)


def test_get_public_video_url():
    clip = MagicMock()
    clip.storage_path = "http://example.com/clip.mp4"
    url = _get_public_video_url(clip)
    assert isinstance(url, str)


def test_is_token_expired_error():
    from fastapi import HTTPException
    e = HTTPException(status_code=401, detail="expired")
    assert _is_token_expired_error(e) is True
    e2 = HTTPException(status_code=400, detail="bad")
    assert _is_token_expired_error(e2) is False
    assert _is_token_expired_error(Exception("x")) is False
