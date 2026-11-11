from __future__ import annotations

from fastapi.testclient import TestClient

from backend_fastapi.app.main import app


def test_health_endpoint():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
    client.close()


def test_docs_endpoint():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/docs")
    assert resp.status_code == 200
    client.close()
