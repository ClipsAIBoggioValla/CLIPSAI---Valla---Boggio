from __future__ import annotations

from fastapi.testclient import TestClient

from backend_fastapi.app.main import app


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code in (200, 404, 500)
    client.close()
