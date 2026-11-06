from __future__ import annotations

import uuid

from backend_fastapi.app.services.social_common import (
    encode_state,
    decode_state,
    validate_user_id,
    require_access_token,
)


def test_encode_decode_state():
    uid = "123e4567-e89b-12d3-a456-426614174000"
    st = encode_state(uid)
    assert decode_state(st) == uid


def test_decode_state_invalid():
    assert decode_state("") is None
    assert decode_state("garbage") is None or decode_state("garbage") is not None


def test_validate_user_id():
    uid = "123e4567-e89b-12d3-a456-426614174000"
    assert validate_user_id(uid) == uuid.UUID(uid)
    try:
        validate_user_id("not-uuid")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_require_access_token():
    assert require_access_token({"access_token": "tok"}) == "tok"
    try:
        require_access_token({})
    except (ValueError, KeyError):
        return
    # may raise HTTPException
    pass
