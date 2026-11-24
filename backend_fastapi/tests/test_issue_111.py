"""Pruebas de vault, límites de solicitudes y guardia JWT de la issue #111."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from backend_fastapi.app.config import Settings
from backend_fastapi.app.routers import videos as videos_router
from backend_fastapi.app.services import publish_service, youtube_service
from backend_fastapi.app.services.token_crypto import cifrar_token, descifrar_token
from _fixtures import make_social_account


def test_vault_save(db, user) -> None:
    access_token = "oauth-access-clear"
    refresh_token = "oauth-refresh-clear"
    account = youtube_service.save_youtube_tokens(
        db,
        str(user.id),
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "username": "canal-prueba",
            "id": "channel-111",
        },
    )

    assert account in db.added
    assert account.access_token != access_token
    assert account.refresh_token != refresh_token
    assert descifrar_token(account.access_token) == access_token
    assert descifrar_token(account.refresh_token) == refresh_token


def test_vault_publish(user, tmp_path) -> None:
    token = "oauth-publish-clear"
    ciphertext = cifrar_token(token)
    account = make_social_account(user.id, access_token=ciphertext)
    video_file = tmp_path / "clip.mp4"
    video_file.write_bytes(b"video")
    response = Mock()

    with patch.object(publish_service.requests, "post", return_value=response) as http_post:
        result = publish_service._publicar_upload_youtube(account, str(video_file), "titulo", "descripcion")

    request_args = http_post.call_args
    assert result is response
    assert request_args.kwargs["headers"]["Authorization"] == f"Bearer {token}"
    assert ciphertext not in str(request_args)


def test_vault_refresh(db, user, monkeypatch) -> None:
    access_token = "oauth-refreshed-clear"
    refresh_token = "oauth-refresh-clear"
    account = make_social_account(
        user.id,
        access_token=cifrar_token("oauth-old-clear"),
        refresh_token=cifrar_token(refresh_token),
    )
    oauth_response = Mock(
        status_code=200,
        text="ok",
        json=Mock(return_value={"access_token": access_token, "refresh_token": "oauth-next-refresh"}),
    )
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")

    with patch.object(publish_service.requests, "post", return_value=oauth_response) as http_post:
        refreshed = publish_service._refresh_account_token(account, "youtube", db)

    assert refreshed is True
    assert http_post.call_args.kwargs["data"]["refresh_token"] == refresh_token
    assert descifrar_token(account.access_token) == access_token
    assert descifrar_token(account.refresh_token) == "oauth-next-refresh"
    assert account.access_token != access_token
    assert account in db.added


def test_auth_rate_limit(client) -> None:
    payload = {"email": "limit@example.com", "password": "WrongPassword123"}
    paths = ("/auth/login", "/login", "/registro", "/auth/login", "/login", "/registro")
    responses = [client.post(path, json=payload) for path in paths]

    assert responses[-1].status_code == 429


def test_upload_rate_limit(client) -> None:
    s3_client = Mock()
    s3_client.generate_presigned_url.return_value = "https://storage.test/upload"
    payload = {"file_name": "video.mp4", "file_type": "video/mp4"}

    with patch.object(videos_router, "get_s3_client", return_value=s3_client):
        responses = [client.post("/api/videos/upload-url", json=payload) for _ in range(11)]

    assert responses[-1].status_code == 429
    assert s3_client.generate_presigned_url.call_count == 10


def test_jwt_production_guard() -> None:
    default_secret = "dev_secret_key_clipsai_2026_super_secure_local"

    with pytest.raises(ValueError):
        Settings(app_env="production", jwt_secret=default_secret)

    assert Settings(app_env="development", jwt_secret="custom-jwt-secret-for-tests").app_env == "development"
    assert Settings(
        app_env="production",
        jwt_secret="custom-jwt-secret-for-tests",
        runpod_webhook_secret="runpod-webhook-secret-for-tests",
    ).app_env == "production"


def test_runpod_webhook_secret_production_guard() -> None:
    with pytest.raises(ValueError, match="RUNPOD_WEBHOOK_SECRET debe configurarse en production"):
        Settings(
            app_env="production",
            jwt_secret="custom-jwt-secret-for-tests",
            runpod_webhook_secret="  ",
        )

    assert Settings(
        app_env="production",
        jwt_secret="custom-jwt-secret-for-tests",
        runpod_webhook_secret="runpod-webhook-secret-for-tests",
    ).runpod_webhook_secret == "runpod-webhook-secret-for-tests"
