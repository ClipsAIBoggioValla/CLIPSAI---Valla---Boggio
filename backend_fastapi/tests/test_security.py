from __future__ import annotations

import uuid
from datetime import timedelta

from backend_fastapi.app.security.hashing import hash_password, verify_password
from backend_fastapi.app.security.jwt import (
    TokenDecodeError,
    TokenExpiredError,
    create_access_token,
    decode_access_token,
)


def test_hash_and_verify():
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_hash_truncates_long_password():
    long_pw = "a" * 200
    h = hash_password(long_pw)
    assert verify_password(long_pw, h) is True


def test_create_and_decode_token():
    uid = uuid.uuid4()
    tok = create_access_token(uid)
    payload = decode_access_token(tok)
    assert payload["sub"] == str(uid)
    assert payload["type"] == "access"


def test_decode_expired_token():
    uid = uuid.uuid4()
    tok = create_access_token(uid, expires_delta=timedelta(seconds=-10))
    try:
        decode_access_token(tok)
    except TokenExpiredError:
        return
    raise AssertionError("expected TokenExpiredError")


def test_decode_invalid_token():
    try:
        decode_access_token("not.a.token")
    except TokenDecodeError:
        return
    raise AssertionError("expected TokenDecodeError")


def test_decode_token_without_sub():
    from jose import jwt as jose_jwt
    from backend_fastapi.app.config import get_settings
    s = get_settings()
    bad = jose_jwt.encode({"foo": "bar", "exp": 9999999999}, s.jwt_secret, algorithm=s.jwt_algorithm)
    try:
        decode_access_token(bad)
    except TokenDecodeError:
        return
    raise AssertionError("expected TokenDecodeError")
