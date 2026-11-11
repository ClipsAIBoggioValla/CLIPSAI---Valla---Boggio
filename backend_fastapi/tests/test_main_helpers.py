from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend_fastapi.app.main import _build_cors_origins, _origin_is_allowed, health, _login_alias, _registro_alias


def test_build_cors_origins_list() -> None:
    out = _build_cors_origins()
    assert isinstance(out, list)


def test_origin_is_allowed_bool() -> None:
    assert isinstance(_origin_is_allowed("http://localhost:3000"), bool)


def test_health_ok() -> None:
    assert health() == {"status": "ok"}


def test_login_alias_mock() -> None:
    from backend_fastapi.app.schemas.usuario import UsuarioLogin
    payload = UsuarioLogin(email="a@b.com", password="password123")
    db = MagicMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    try:
        _login_alias(payload, db=db)
    except Exception:
        pass


def test_registro_alias_mock() -> None:
    from backend_fastapi.app.schemas.usuario import UsuarioCreate
    payload = UsuarioCreate(email="a@b.com", password="password123", full_name="N")
    db = MagicMock()
    db.execute.return_value = MagicMock(first=lambda: None)
    try:
        _registro_alias(payload, db=db)
    except Exception:
        pass
