from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend_fastapi.app import main as app_main
from backend_fastapi.app.main import app


def test_health():
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    client.close()


def test_docs():
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/docs")
    assert r.status_code == 200
    client.close()


def test_openapi():
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    client.close()


def test_lifespan_no_db():
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/health")
        assert r.status_code == 200


def test_middleware_options_preflight_allowed():
    client = TestClient(app, raise_server_exceptions=False)
    r = client.options(
        "/health",
        headers={
            "Origin": "https://api.clipsai.xyz",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert "GET" in r.headers.get("access-control-allow-methods", "")
    client.close()


def test_middleware_options_preflight_disallowed():
    client = TestClient(app, raise_server_exceptions=False)
    r = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") is None
    client.close()


def test_log_routes():
    import asyncio

    asyncio.get_event_loop_policy()
    # call directly
    coro = app_main.log_routes()
    # async function; run via asyncio
    import asyncio as _a

    loop = _a.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()
    assert True


def test_login_alias():
    payload = MagicMock()
    db = MagicMock()
    with patch("backend_fastapi.app.routers.auth.login", return_value={"access_token": "t"}) as m:
        out = app_main._login_alias(payload, db)
    assert out == {"access_token": "t"}
    m.assert_called()


def test_registro_alias():
    payload = MagicMock()
    db = MagicMock()
    with patch("backend_fastapi.app.routers.auth.registro", return_value={"access_token": "t"}) as m:
        out = app_main._registro_alias(payload, db)
    assert out == {"access_token": "t"}
    m.assert_called()
