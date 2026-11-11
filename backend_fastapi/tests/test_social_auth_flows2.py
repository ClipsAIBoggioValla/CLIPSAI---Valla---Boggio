from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend_fastapi.app.main import app
from backend_fastapi.app.deps import get_current_user, get_db
from backend_fastapi.app.models import Usuario, Video, Job, Clip, SocialAccount


@pytest.fixture
def soc_client(db_session):
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()

    def _get_db():
        yield db_session

    def _get_user():
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    client = TestClient(app, raise_server_exceptions=False)
    yield client, u
    app.dependency_overrides.clear()
    client.close()


def test_social_youtube_connect(soc_client):
    client, u = soc_client
    with patch("backend_fastapi.app.routers.social_auth.yt_get_youtube_auth_url", return_value="https://auth.example/yt"):
        resp = client.get("/auth/social/youtube/connect")
    assert resp.status_code == 200
    assert resp.json().get("auth_url") == "https://auth.example/yt"


def test_social_instagram_connect_unavailable(soc_client):
    client, u = soc_client
    with patch("backend_fastapi.app.routers.social_auth.ig_get_instagram_auth_url", None):
        resp = client.get("/auth/social/instagram/connect")
    assert resp.status_code == 500


def test_social_tiktok_connect(soc_client, monkeypatch):
    client, u = soc_client
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "ck")
    with patch("backend_fastapi.app.routers.social_auth.tt_get_tiktok_auth_url", return_value="https://auth.example/tt"), patch(
        "backend_fastapi.app.routers.social_auth.tt_generate_pkce_pair", return_value=("verifier", "challenge")
    ):
        resp = client.get("/auth/social/tiktok/connect")
    assert resp.status_code == 200
