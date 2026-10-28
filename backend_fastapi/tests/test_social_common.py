from __future__ import annotations

import uuid

from backend_fastapi.app.services.social_common import (
    decode_state,
    encode_state,
    require_access_token,
    validate_user_id,
)


def test_encode_decode_state_roundtrip() -> None:
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    state = encode_state(user_id)
    assert decode_state(state) == user_id


def test_decode_state_invalid_returns_none_or_original() -> None:
    assert decode_state("") is None


def test_validate_user_id_ok() -> None:
    uid = "123e4567-e89b-12d3-a456-426614174000"
    assert validate_user_id(uid) == uuid.UUID(uid)


def test_validate_user_id_invalid_raises() -> None:
    try:
        validate_user_id("not-a-uuid")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_require_access_token_ok() -> None:
    assert require_access_token({"access_token": "tok"}) == "tok"


def test_require_access_token_missing_raises() -> None:
    try:
        require_access_token({})
    except ValueError:
        return
    raise AssertionError("expected ValueError")
