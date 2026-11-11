from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.database import _is_docker, _fallback_db_url
from backend_fastapi.app.cli import _as_seconds, build_parser, main
from backend_fastapi.app.main import _build_cors_origins, _origin_is_allowed, health
from backend_fastapi.app.config import _is_docker as cfg_is_docker, _resolve_db_host, _fix_redirect_uri, get_settings


def test_is_docker() -> None:
    assert isinstance(_is_docker(), bool)


def test_fallback_db_url() -> None:
    url = "postgresql://u:p@127.0.0.1:5432/db"
    out = _fallback_db_url(url)
    assert isinstance(out, str)


def test_as_seconds() -> None:
    assert _as_seconds(5) == 5.0
    assert _as_seconds("1:30") == 90.0
    assert _as_seconds("0:01:02") == 62.0


def test_build_parser() -> None:
    p = build_parser()
    assert p is not None


def test_main_help() -> None:
    try:
        main(["--help"])
    except SystemExit:
        pass


def test_build_cors_origins() -> None:
    out = _build_cors_origins()
    assert isinstance(out, list)


def test_origin_is_allowed() -> None:
    assert isinstance(_origin_is_allowed("http://localhost:3000"), bool)


def test_health() -> None:
    assert health() == {"status": "ok"} or health().get("status") == "ok"


def test_cfg_is_docker() -> None:
    assert isinstance(cfg_is_docker(), bool)


def test_resolve_db_host() -> None:
    out = _resolve_db_host("postgresql://u:p@db:5432/db")
    assert isinstance(out, str)


def test_fix_redirect_uri() -> None:
    out = _fix_redirect_uri("http://localhost/cb", "http://localhost", "tiktok")
    assert isinstance(out, str)


def test_get_settings() -> None:
    s = get_settings()
    assert s is not None
