from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from backend_fastapi.app.routers.auth import _autenticar, registro, login
from backend_fastapi.app.deps import _unauthorized, get_current_user


def test_autenticar_no_user() -> None:
    db = MagicMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    try:
        _autenticar(db, "a@b.com", "pw")
        raise AssertionError("expected HTTPException")
    except HTTPException:
        pass


def test_autenticar_bad_password() -> None:
    u = SimpleNamespace(hashed_password="hashed")
    db = MagicMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: u)
    with patch("backend_fastapi.app.routers.auth.verify_password", return_value=False):
        try:
            _autenticar(db, "a@b.com", "pw")
            raise AssertionError("expected HTTPException")
        except HTTPException:
            pass


def test_autenticar_ok() -> None:
    u = SimpleNamespace(hashed_password="hashed")
    db = MagicMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: u)
    with patch("backend_fastapi.app.routers.auth.verify_password", return_value=True):
        out = _autenticar(db, "a@b.com", "pw")
    assert out is u


def test_unauthorized() -> None:
    e = _unauthorized("x")
    assert e.status_code == 401


def test_get_current_user_no_token() -> None:
    pass


def test_get_current_user_invalid_token() -> None:
    creds = SimpleNamespace(credentials="bad")
    db = MagicMock()
    try:
        get_current_user(creds, db)
        raise AssertionError("expected HTTPException")
    except HTTPException:
        pass


def test_get_current_user_valid() -> None:
    from backend_fastapi.app.security.jwt import create_access_token
    import uuid as _u
    uid = _u.uuid4()
    tok = create_access_token(uid)
    creds = SimpleNamespace(credentials=tok)
    db = MagicMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: SimpleNamespace(id=uid))
    out = get_current_user(creds, db)
    assert out is not None
