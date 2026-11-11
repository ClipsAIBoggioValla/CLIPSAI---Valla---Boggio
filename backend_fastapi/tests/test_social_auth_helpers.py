from __future__ import annotations

import base64
import json
import os
from unittest.mock import patch

from backend_fastapi.app.routers.social_auth import _get_frontend_base, _decode_tiktok_state


def test_get_frontend_base_default() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert _get_frontend_base().startswith("http")


def test_get_frontend_base_env() -> None:
    with patch.dict(os.environ, {"FRONTEND_URL": "https://app.x.com"}, clear=True):
        assert _get_frontend_base() == "https://app.x.com"


def test_decode_tiktok_state_none() -> None:
    assert _decode_tiktok_state(None) == (None, None)


def test_decode_tiktok_state_valid() -> None:
    data = {"user_id": "u1", "code_verifier": "cv"}
    state = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    uid, cv = _decode_tiktok_state(state)
    assert uid == "u1"
    assert cv == "cv"


def test_decode_tiktok_state_invalid() -> None:
    uid, cv = _decode_tiktok_state("!!!@@@")
    # may return None or fallback; just ensure no crash
    assert cv is None
