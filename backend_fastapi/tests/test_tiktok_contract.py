"""Contrato end-to-end de la integración TikTok (FastAPI).

Valida:
1. `/auth/social/status` expone youtube/instagram/tiktok con connected/username/expires_at/configured.
2. `/auth/social/tiktok/connect` sin credenciales → 503 con mensaje claro (no 500 genérico).
3. `/auth/social/tiktok/connect` con credenciales → auth_url válida de TikTok con state
   PKCE reversible (user_id + code_verifier) y redirect_uri no vacía.
4. Consistencia: la redirect_uri de la auth_url == la que usará el exchange del callback
   (`_redirect_uri_tiktok()`) — el bug del mismatch connect↔exchange.
"""

from __future__ import annotations

import urllib.parse
from typing import Any
from unittest.mock import patch

import pytest

from _fixtures import make_usuario
from _fixtures import FakeSession

from backend_fastapi.app.services import tiktok_service as tt


@pytest.fixture()
def usuario():
    return make_usuario()


@pytest.fixture()
def api_client(db: FakeSession, usuario):
    from backend_fastapi.app.deps import get_current_user, get_db
    from backend_fastapi.app.main import app
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: usuario
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def _limpiar_env_tiktok(monkeypatch: Any) -> None:
    for clave in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REDIRECT_URI"):
        monkeypatch.delenv(clave, raising=False)


class TestStatusContrato:
    def test_claves_y_campos_por_plataforma(self, api_client) -> None:
        res = api_client.get("/auth/social/status")
        assert res.status_code == 200
        data = res.json()
        for plataforma in ("youtube", "instagram", "tiktok"):
            assert plataforma in data, f"falta {plataforma} en /status"
            entrada = data[plataforma]
            for campo in ("connected", "username", "expires_at", "configured"):
                assert campo in entrada, f"falta {campo} en {plataforma}"
            assert entrada["connected"] is False

    def test_configured_refleja_env_tiktok(self, api_client, monkeypatch) -> None:
        _limpiar_env_tiktok(monkeypatch)
        sin_config = api_client.get("/auth/social/status").json()
        assert sin_config["tiktok"]["configured"] is False

        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "sb_test_key")
        monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "sb_test_secret")
        con_config = api_client.get("/auth/social/status").json()
        assert con_config["tiktok"]["configured"] is True


class TestTiktokConnect:
    def test_sin_credenciales_503_mensaje_claro(self, api_client, monkeypatch) -> None:
        _limpiar_env_tiktok(monkeypatch)
        res = api_client.get("/auth/social/tiktok/connect")
        assert res.status_code == 503
        detalle = res.json()["detail"]
        assert "TIKTOK_CLIENT_KEY" in detalle
        assert "TIKTOK_CLIENT_SECRET" in detalle or "configurado" in detalle.lower()

    def test_service_no_disponible_503(self, api_client) -> None:
        from backend_fastapi.app.routers import social_auth as sa_router

        with patch.object(sa_router, "tt_get_tiktok_auth_url", None):
            res = api_client.get("/auth/social/tiktok/connect")
        assert res.status_code == 503
        assert "no disponible" in res.json()["detail"]

    def test_con_credenciales_200_auth_url_valida(self, api_client, monkeypatch) -> None:
        _limpiar_env_tiktok(monkeypatch)
        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "sb_test_key")
        monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "sb_test_secret")
        res = api_client.get("/auth/social/tiktok/connect")
        assert res.status_code == 200
        data = res.json()
        auth_url = data.get("auth_url") or data.get("url")
        assert auth_url and auth_url.startswith("https://www.tiktok.com/v2/auth/authorize/")
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(auth_url).query)
        assert qs["client_key"] == ["sb_test_key"]
        assert qs["code_challenge_method"] == ["S256"]
        assert qs["code_challenge"][0]  # challenge no vacío
        assert qs["redirect_uri"][0].startswith("https://")

    def test_state_pkce_reversible(self, api_client, monkeypatch, usuario) -> None:
        from backend_fastapi.app.routers import social_auth as sa_router

        _limpiar_env_tiktok(monkeypatch)
        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "sb_test_key")
        monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "sb_test_secret")
        auth_url = (api_client.get("/auth/social/tiktok/connect").json())["auth_url"]
        state = urllib.parse.parse_qs(urllib.parse.urlparse(auth_url).query)["state"][0]

        user_id, code_verifier = sa_router._user_id_y_verifier_de_state(state)
        assert user_id == str(usuario.id)
        assert code_verifier  # el callback puede completar el exchange PKCE


class TestConsistenciaRedirect:
    def test_redirect_uri_de_connect_igual_a_la_del_exchange(self, api_client, monkeypatch) -> None:
        """La auth_url y el exchange del callback deben usar la MISMA redirect_uri."""
        _limpiar_env_tiktok(monkeypatch)
        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "sb_test_key")
        monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "sb_test_secret")
        auth_url = (api_client.get("/auth/social/tiktok/connect").json())["auth_url"]
        redirect_connect = urllib.parse.parse_qs(urllib.parse.urlparse(auth_url).query)["redirect_uri"][0]

        _client_key, _secret, redirect_exchange = tt._get_tiktok_config()
        assert redirect_connect == redirect_exchange == tt._redirect_uri_tiktok()

    def test_exchange_http_error_se_propaga(self, monkeypatch) -> None:
        import requests as requests_mod

        _limpiar_env_tiktok(monkeypatch)
        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "k")
        monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "s")
        with patch(
            "backend_fastapi.app.services.tiktok_service.requests.post",
            side_effect=requests_mod.exceptions.HTTPError("400 Client Error: redirect_uri mismatch"),
        ):
            with pytest.raises(requests_mod.exceptions.HTTPError):
                tt.exchange_tiktok_code("codigo", "verificador")
