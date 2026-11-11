"""Fase 3 de cobertura — restos de `services/publish_service.py`.

Cubre: `_get_ngrok_domain` (branches de env), `_get_social_account` (fallbacks
ORM/query/SQL crudo), `_refresh_account_token` (tiktok/youtube/instagram),
`_ensure_token_fresh`, `_publish_youtube`, `_resolve_instagram_business_id`
(capa 1 y 2), `_publish_instagram` (pre-validación de URL, container + polling
+ publish), `_publish_tiktok` (FILE_UPLOAD) y `publish_clip_task` (webhook,
refresh/retry, desconexión tiktok). HTTP 100% mockeado.
"""

from __future__ import annotations

import sys
import types
import uuid as uuid_lib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

import _fixtures
from _fixtures import FakeResult, FakeSession, make_clip, make_job, make_video, now_utc

from backend_fastapi.app.services import publish_service as ps
from backend_fastapi.app.services.publish_service import (
    PLATFORM_URLS,
    _ensure_token_fresh,
    _get_ngrok_domain,
    _get_public_video_url,
    _get_social_account,
    _publish_instagram,
    _publish_tiktok,
    _publish_youtube,
    _refresh_account_token,
    _resolve_instagram_business_id,
    publish_clip_task,
)


def _resp(status: int = 200, payload: dict | None = None, text: str = "") -> Mock:
    mock = Mock()
    mock.status_code = status
    if payload is not None:
        mock.json = Mock(return_value=payload)
        mock.text = str(payload) if not text else text
    else:
        mock.json = Mock(side_effect=ValueError("no json"))
        mock.text = text
    return mock


def _clip(db: FakeSession, user: Any, **overrides: Any) -> Any:
    video = make_video(user.id)
    job = make_job(video.id)
    clip = make_clip(job.id, video.id, **overrides)
    db.seed(video, job, clip)
    return clip


def _sin_env_ngrok(monkeypatch: Any) -> None:
    for key in (
        "PUBLIC_BACKEND_URL",
        "BACKEND_URL",
        "API_BASE_URL",
        "NGROK_DOMAIN",
        "FACEBOOK_APP_ID",
        "META_APP_ID",
        "FACEBOOK_APP_SECRET",
        "META_APP_SECRET",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "TIKTOK_CLIENT_KEY",
        "TIKTOK_CLIENT_SECRET",
        "FACEBOOK_CLIENT_ID",
        "FACEBOOK_CLIENT_SECRET",
        "INSTAGRAM_CLIENT_ID",
        "INSTAGRAM_CLIENT_SECRET",
        "PUBLISH_WEBHOOK_URL",
    ):
        monkeypatch.delenv(key, raising=False)


# ------------------------------------------------------------------ helpers


class TestGetNgrokDomain:
    def test_public_backend_url_primero(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("PUBLIC_BACKEND_URL", "https://api.clipsai.xyz/")
        assert _get_ngrok_domain() == "api.clipsai.xyz"

    def test_backend_url_filtrado_por_ngrok(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("BACKEND_URL", "https://algo.ngrok-free.dev")
        monkeypatch.setenv("NGROK_DOMAIN", "otro-dominio.com")
        assert _get_ngrok_domain() == "otro-dominio.com"

    def test_ngrok_domain_con_decorator_filtrado(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("NGROK_DOMAIN", "decorator-tunel.ngrok.dev")
        assert _get_ngrok_domain() == "api.clipsai.xyz"

    def test_sin_nada_usa_default(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        assert _get_ngrok_domain() == "api.clipsai.xyz"

    def test_backend_url_sin_ngrok_es_valido(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("BACKEND_URL", "https://api.midominio.com")
        assert _get_ngrok_domain() == "api.midominio.com"


class TestGetPublicVideoUrl:
    def test_url_publica_con_storage(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("PUBLIC_BACKEND_URL", "https://api.clipsai.xyz")
        clip = make_clip(uuid_lib.uuid4(), storage_path="/app/storage/clips/clip.mp4")
        url = _get_public_video_url(clip)
        assert url == f"https://api.clipsai.xyz/clips/{clip.id}/descarga"


# ------------------------------------------------------------- get account


class TestGetSocialAccount:
    def test_orm_falla_y_sql_crudo_devuelve_fila(self, user) -> None:
        fila = {
            "id": "x",
            "user_id": str(user.id),
            "platform": "tiktok",
            "platform_account_id": "ig-123",
            "access_token": "tok",
            "refresh_token": "ref",
        }
        db = Mock()
        db.execute = Mock(side_effect=[RuntimeError("orm roto"), FakeResult(rows=[fila])])
        db.query = Mock(return_value=SimpleNamespace(first=Mock(return_value=None)))
        cuenta = _get_social_account(db, user.id, "TikTok ")
        assert cuenta.access_token == "tok"
        assert cuenta.platform_account_id == "ig-123"

    def test_orm_devuelve_cuenta(self, db, user) -> None:
        cuenta = _fixtures.make_social_account(user.id, platform="youtube")
        db.push_result(FakeResult(scalar=cuenta))
        assert _get_social_account(db, user.id, "youtube") is cuenta

    def test_sin_cuenta_lanza_400(self, user) -> None:
        db = Mock()
        db.execute = Mock(return_value=FakeResult(scalar=None))
        db.query = Mock(return_value=SimpleNamespace(first=Mock(return_value=None)))
        with pytest.raises(HTTPException, match="no vinculada"):
            _get_social_account(db, user.id, "tiktok")

    def test_uid_no_uuid_lanza_400(self) -> None:
        db = Mock()
        db.execute = Mock(return_value=FakeResult(scalar=None))
        db.query = Mock(return_value=SimpleNamespace(first=Mock(return_value=None)))
        with pytest.raises(HTTPException, match="no vinculada"):
            _get_social_account(db, "no-es-uuid", "tiktok")

    def test_sql_crudo_tambien_falla_lanza_400(self, user) -> None:
        db = Mock()
        db.execute = Mock(side_effect=[RuntimeError("orm roto"), RuntimeError("sql roto")])
        db.query = Mock(return_value=SimpleNamespace(first=Mock(return_value=None)))
        with pytest.raises(HTTPException, match="no vinculada"):
            _get_social_account(db, user.id, "tiktok")

    def test_cuenta_sin_access_token_lanza_400(self, user) -> None:
        cuenta = _fixtures.make_social_account(user.id, access_token=None)
        db = Mock()
        db.execute = Mock(return_value=FakeResult(scalar=cuenta))
        with pytest.raises(HTTPException, match="no vinculada"):
            _get_social_account(db, user.id, "tiktok")


# ------------------------------------------------------- refresh de tokens


def _settings_vacios() -> Any:
    return SimpleNamespace(
        tiktok_client_key="",
        tiktok_client_secret="",
        facebook_client_id="",
        facebook_client_secret="",
        instagram_client_id="",
        instagram_client_secret="",
    )


class TestRefreshAccountToken:
    def test_sin_refresh_token(self) -> None:
        cuenta = SimpleNamespace(user_id="u", refresh_token="")
        assert _refresh_account_token(cuenta, "tiktok", FakeSession()) is False

    def test_tiktok_sin_credenciales_en_settings(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(ps, "get_settings", _settings_vacios)
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref-token")
        assert _refresh_account_token(cuenta, "tiktok", FakeSession()) is False

    def test_tiktok_refresh_exitoso(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(
            ps,
            "get_settings",
            lambda: SimpleNamespace(tiktok_client_key="ck", tiktok_client_secret="cs"),
        )
        cuenta = _fixtures.make_social_account(uuid_lib.uuid4(), platform="tiktok", refresh_token="ref-token")
        resp = _resp(200, {"access_token": "nuevo", "refresh_token": "", "expires_in": "3600"})
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            assert _refresh_account_token(cuenta, "tiktok", db) is True
        assert cuenta.access_token == "nuevo"
        assert cuenta.refresh_token == "ref-token"  # vacío → se conserva el viejo
        assert cuenta.token_expires_at is not None

    def test_tiktok_expires_in_invalido(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(
            ps,
            "get_settings",
            lambda: SimpleNamespace(tiktok_client_key="ck", tiktok_client_secret="cs"),
        )
        cuenta = _fixtures.make_social_account(uuid_lib.uuid4(), platform="tiktok", refresh_token="ref")
        resp = _resp(200, {"access_token": "nuevo", "expires_in": "no-numero"})
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            assert _refresh_account_token(cuenta, "tiktok", db) is True

    def test_tiktok_json_invalido_sin_access_token_relanza(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(
            ps,
            "get_settings",
            lambda: SimpleNamespace(tiktok_client_key="ck", tiktok_client_secret="cs"),
        )
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        resp = _resp(200, None, text="basura")
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            with pytest.raises(Exception, match="TikTok refresh failed"):
                _refresh_account_token(cuenta, "tiktok", db)

    def test_tiktok_error_en_body_relanza(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(
            ps,
            "get_settings",
            lambda: SimpleNamespace(tiktok_client_key="ck", tiktok_client_secret="cs"),
        )
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        resp = _resp(200, {"error": "boom", "error_code": 100500})
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            with pytest.raises(Exception, match="TikTok refresh error"):
                _refresh_account_token(cuenta, "tiktok", db)

    def test_tiktok_error_en_data_relanza(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(
            ps,
            "get_settings",
            lambda: SimpleNamespace(tiktok_client_key="ck", tiktok_client_secret="cs"),
        )
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        resp = _resp(200, {"data": {"error_code": 7}})
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            with pytest.raises(Exception, match="TikTok refresh error"):
                _refresh_account_token(cuenta, "tiktok", db)

    def test_tiktok_status_malo_relanza(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(
            ps,
            "get_settings",
            lambda: SimpleNamespace(tiktok_client_key="ck", tiktok_client_secret="cs"),
        )
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        resp = _resp(403, {"error": "forbidden"})
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            with pytest.raises(Exception, match="TikTok refresh failed"):
                _refresh_account_token(cuenta, "tiktok", db)

    def test_youtube_sin_credenciales(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        assert _refresh_account_token(cuenta, "youtube", FakeSession()) is False

    def test_youtube_refresh_exitoso(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        resp = _resp(200, {"access_token": "yt-nuevo", "refresh_token": "yt-ref", "expires_in": "abc"})
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            assert _refresh_account_token(cuenta, "youtube", db) is True
        assert cuenta.access_token == "yt-nuevo"
        assert cuenta.refresh_token == "yt-ref"

    def test_youtube_json_invalido(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        resp = _resp(200, None, text="raro")
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            assert _refresh_account_token(cuenta, "youtube", db) is False

    def test_youtube_status_malo(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        with patch.object(ps.requests, "post", Mock(return_value=_resp(400, {"e": 1}))):
            assert _refresh_account_token(cuenta, "youtube", db) is False

    def test_youtube_excepcion_rollback(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        with patch.object(ps.requests, "post", Mock(side_effect=RuntimeError("red caída"))):
            assert _refresh_account_token(cuenta, "youtube", db) is False

    def test_instagram_sin_credenciales(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(ps, "get_settings", _settings_vacios)
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        assert _refresh_account_token(cuenta, "instagram", FakeSession()) is False

    def test_instagram_refresh_exitoso_con_expires_invalido(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(
            ps,
            "get_settings",
            lambda: SimpleNamespace(
                facebook_client_id="fb",
                facebook_client_secret="fs",
                instagram_client_id="",
                instagram_client_secret="",
            ),
        )
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        resp = _resp(200, {"access_token": "ig-nuevo", "expires_in": "no-num"})
        with patch.object(ps.requests, "get", Mock(return_value=resp)):
            assert _refresh_account_token(cuenta, "instagram", db) is True
        assert cuenta.access_token == "ig-nuevo"
        assert cuenta.refresh_token == "ref"

    def test_instagram_refresh_sin_expires_usa_60_dias(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(
            ps,
            "get_settings",
            lambda: SimpleNamespace(
                facebook_client_id="fb",
                facebook_client_secret="fs",
                instagram_client_id="",
                instagram_client_secret="",
            ),
        )
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        resp = _resp(200, {"access_token": "ig-nuevo2"})
        with patch.object(ps.requests, "get", Mock(return_value=resp)):
            assert _refresh_account_token(cuenta, "instagram", db) is True
        restante = cuenta.token_expires_at - datetime.now(timezone.utc)
        assert timedelta(days=59) < restante <= timedelta(days=60, minutes=5)

    def test_instagram_status_malo(self, monkeypatch, db) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setattr(
            ps,
            "get_settings",
            lambda: SimpleNamespace(
                facebook_client_id="fb",
                facebook_client_secret="fs",
                instagram_client_id="",
                instagram_client_secret="",
            ),
        )
        cuenta = SimpleNamespace(user_id="u", refresh_token="ref")
        with patch.object(ps.requests, "get", Mock(return_value=_resp(500, {"e": 1}))):
            assert _refresh_account_token(cuenta, "instagram", db) is False


class TestEnsureTokenFresh:
    def test_expira_en_breve_con_naive_y_refresh_roto(self, monkeypatch) -> None:
        cuenta = SimpleNamespace(token_expires_at=datetime.now() + timedelta(minutes=2))
        refresh = Mock()
        db = Mock()
        db.refresh = Mock(side_effect=RuntimeError("no"))
        with patch.object(ps, "_refresh_account_token", refresh):
            _ensure_token_fresh(cuenta, "tiktok", db)
        refresh.assert_called_once()

    def test_token_expires_at_que_explota(self, monkeypatch) -> None:
        cuenta = _CuentaTokenExplota()
        with patch.object(ps, "_refresh_account_token", Mock()) as refresh:
            _ensure_token_fresh(cuenta, "tiktok", Mock())
        refresh.assert_not_called()


class _CuentaTokenExplota:
    @property
    def token_expires_at(self) -> Any:
        raise RuntimeError("token roto")


# ----------------------------------------------------------------- youtube


class TestPublishYoutube:
    def test_archivo_valido_publica(self, monkeypatch, tmp_path, db, user) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"video-bytes")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        cuenta = _fixtures.make_social_account(uuid_lib.uuid4(), platform="youtube")
        resp = _resp(200, {"id": "yt123"})
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            out = _publish_youtube(cuenta, clip, "Caption")
        assert out == {
            "status": "published",
            "platform": "youtube",
            "post_id": "yt123",
            "url": "https://www.youtube.com/watch?v=yt123",
        }

    def test_sin_id_usa_fake_y_url_shorts(self, monkeypatch, tmp_path, db, user) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        cuenta = _fixtures.make_social_account(uuid_lib.uuid4(), platform="youtube")
        resp = _resp(200, {})
        with patch.object(ps.requests, "post", Mock(return_value=resp)):
            out = _publish_youtube(cuenta, clip, None)
        assert out["url"].startswith("https://www.youtube.com/shorts/")
        assert len(out["post_id"]) == 12

    def test_archivo_ilegible_500(self, monkeypatch, tmp_path, db, user) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        cuenta = _fixtures.make_social_account(uuid_lib.uuid4(), platform="youtube")
        with patch("builtins.open", Mock(side_effect=OSError("archivo bloqueado"))):
            with pytest.raises(HTTPException, match="Error leyendo archivo"):
                _publish_youtube(cuenta, clip, None)

    def test_401_token_expirado(self, monkeypatch, tmp_path, db, user) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        cuenta = _fixtures.make_social_account(uuid_lib.uuid4(), platform="youtube")
        with patch.object(ps.requests, "post", Mock(return_value=_resp(401, {"e": 1}))):
            with pytest.raises(HTTPException, match="expirado"):
                _publish_youtube(cuenta, clip, None)

    def test_error_api_400(self, monkeypatch, tmp_path, db, user) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        cuenta = _fixtures.make_social_account(uuid_lib.uuid4(), platform="youtube")
        with patch.object(ps.requests, "post", Mock(return_value=_resp(403, {"error": "quota"}))):
            with pytest.raises(HTTPException, match="YouTube API error 403"):
                _publish_youtube(cuenta, clip, None)

    def test_respuesta_no_json(self, monkeypatch, tmp_path, db, user) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        cuenta = _fixtures.make_social_account(uuid_lib.uuid4(), platform="youtube")
        with patch.object(ps.requests, "post", Mock(return_value=_resp(200, None, text="ok"))):
            out = _publish_youtube(cuenta, clip, None)
        assert out["status"] == "published"

    def test_sin_archivo_fisico_404(self, monkeypatch, db, user) -> None:
        _sin_env_ngrok(monkeypatch)
        clip = make_clip(uuid_lib.uuid4(), storage_path="/no/existe/clip.mp4")
        cuenta = _fixtures.make_social_account(uuid_lib.uuid4(), platform="youtube")
        with pytest.raises(HTTPException, match="no encontrado para YouTube"):
            _publish_youtube(cuenta, clip, None)


# ------------------------------------------------------- instagram business id


class TestResolveInstagramBusinessId:
    def test_capa1_encuentra_ig_id(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        cuenta = SimpleNamespace(access_token="tok")
        resp = Mock()
        resp.json = Mock(
            return_value={
                "data": [{"name": "Página", "instagram_business_account": {"id": "1789"}}]
            }
        )
        with patch.object(ps.requests, "get", Mock(return_value=resp)):
            assert _resolve_instagram_business_id(cuenta) == "1789"

    def test_capa2_por_granular_scopes(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        monkeypatch.setenv("FACEBOOK_APP_ID", "appid")
        monkeypatch.setenv("FACEBOOK_APP_SECRET", "appsec")
        cuenta = SimpleNamespace(access_token="tok")

        me_accounts = Mock()
        me_accounts.json = Mock(return_value={"data": []})
        debug = Mock()
        debug.json = Mock(
            return_value={
                "data": {
                    "granular_scopes": [
                        {"scope": "pages_show_list", "target_ids": ["111", "222"]}
                    ]
                }
            }
        )
        paginas = [
            Mock(),  # target 111 sin IG
            None,
        ]
        pag1 = Mock()
        pag1.json = Mock(return_value={"instagram_business_account": {}})
        pag2 = Mock()
        pag2.json = Mock(return_value={"instagram_business_account": {"id": "9g"}})

        with patch.object(ps.requests, "get", Mock(side_effect=[me_accounts, debug, pag1, pag2])):
            assert _resolve_instagram_business_id(cuenta) == "9g"

    def test_nada_encontrado_lanza_400(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        cuenta = SimpleNamespace(access_token="tok")
        me_accounts = Mock()
        me_accounts.json = Mock(return_value={"data": []})
        with patch.object(ps.requests, "get", Mock(side_effect=RuntimeError("red"))):
            with pytest.raises(HTTPException, match="Instagram Business"):
                _resolve_instagram_business_id(cuenta)


# ---------------------------------------------------------------- instagram


def _parches_instagram(monkeypatch: Any) -> None:
    """Cuelga los mocks comunes de _publish_instagram sobre ps.requests."""
    monkeypatch.setattr(ps, "_resolve_instagram_business_id", Mock(return_value="ig-user"))


class TestPublishInstagram:
    def _cuenta(self) -> Any:
        return _fixtures.make_social_account(uuid_lib.uuid4(), platform="instagram")

    def test_url_publica_http_se_corriga_a_https(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="http://dominio.com/clips/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        crear = _resp(200, {"id": "cont1"})
        st1 = _resp(200, {"status_code": "FINISHED"})
        publicar = _resp(200, {"id": "post9", "permalink": "https://www.instagram.com/reel/post9"})
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(
                ps.requests,
                "post",
                Mock(side_effect=[crear, publicar]),
            ),
            patch.object(ps.requests, "get", Mock(return_value=st1)),
        ):
            out = _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), "cap")
        assert out["url"] == "https://www.instagram.com/reel/post9"

    def test_prevalidacion_url_no_responde(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://caido.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=502))
        with patch.dict(sys.modules, {"httpx": httpx}):
            with pytest.raises(HTTPException, match="no accesible"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_prevalidacion_excepcion(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://caido.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(side_effect=RuntimeError("dns"))
        with patch.dict(sys.modules, {"httpx": httpx}):
            with pytest.raises(HTTPException, match="no accesible"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_httpx_ausente_y_requests_falla(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://caido.com/x.mp4"))
        with (
            patch.dict(sys.modules, {"httpx": None}),
            patch.object(ps.requests, "get", Mock(side_effect=RuntimeError("red"))),
        ):
            with pytest.raises(HTTPException, match="no accesible"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_httpx_ausente_y_requests_status_malo(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://caido.com/x.mp4"))
        with (
            patch.dict(sys.modules, {"httpx": None}),
            patch.object(ps.requests, "get", Mock(return_value=SimpleNamespace(status_code=404))),
        ):
            with pytest.raises(HTTPException, match="404"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_container_401(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(return_value=_resp(401, {"e": 1}))),
        ):
            with pytest.raises(HTTPException, match="expirado"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_container_error_api(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(return_value=_resp(500, {"e": 1}))),
        ):
            with pytest.raises(HTTPException, match="crear container"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_container_sin_creation_id(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(return_value=_resp(200, None, text="ok"))),
        ):
            with pytest.raises(HTTPException, match="creation_id"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_polling_in_progress_luego_finished(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        crear = _resp(200, {"id": "cont2"})
        st_in = _resp(200, {"status_code": "IN_PROGRESS"})
        st_fin = _resp(200, {"status_code": "FINISHED"})
        publicar = _resp(200, {"id": "post8"})
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(side_effect=[crear, publicar])),
            patch.object(ps.requests, "get", Mock(side_effect=[st_in, st_fin])),
            patch.object(ps.asyncio, "run", Mock()),
        ):
            out = _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)
        assert out["post_id"] == "post8"

    def test_polling_error_de_container(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        crear = _resp(200, {"id": "cont3"})
        st_err = _resp(200, {"status_code": "ERROR"})
        detalle = _resp(200, {"status": "video no procesable"})
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(return_value=crear)),
            patch.object(ps.requests, "get", Mock(return_value=st_err)),
            patch.object(ps.asyncio, "run", Mock()),
        ):
            # la 2ª llamada GET (detalle del error) usa requests.get también
            with patch.object(ps.requests, "get", Mock(side_effect=[st_err, detalle])):
                with pytest.raises(HTTPException, match="container error"):
                    _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_polling_estado_desconocido_hasta_timeout(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        crear = _resp(200, {"id": "cont4"})
        st_raro = _resp(200, {"status_code": "WEIRD"})
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(return_value=crear)),
            patch.object(ps.requests, "get", Mock(return_value=st_raro)),
            patch.object(ps.asyncio, "run", Mock(side_effect=RuntimeError("loop"))),
            patch("time.sleep", Mock()),
        ):
            with pytest.raises(HTTPException, match="container timeout"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_polling_http_no_200(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        crear = _resp(200, {"id": "cont5"})
        st_malo = _resp(503, None, text="x")
        st_fin = _resp(200, {"status_code": "FINISHED"})
        publicar = _resp(200, {"id": "post7"})
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(side_effect=[crear, publicar])),
            patch.object(ps.requests, "get", Mock(side_effect=[st_malo, st_fin])),
            patch.object(ps.asyncio, "run", Mock()),
        ):
            out = _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)
        assert out["post_id"] == "post7"

    def test_polling_excepcion_tolerada(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        crear = _resp(200, {"id": "cont6"})
        st_fin = _resp(200, {"status_code": "FINISHED"})
        publicar = _resp(200, {"id": "post6"})
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(side_effect=[crear, publicar])),
            patch.object(ps.requests, "get", Mock(side_effect=[RuntimeError("net"), st_fin])),
            patch.object(ps.asyncio, "run", Mock()),
        ):
            out = _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)
        assert out["post_id"] == "post6"

    def test_publicar_401(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        crear = _resp(200, {"id": "cont7"})
        st_fin = _resp(200, {"status_code": "FINISHED"})
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(side_effect=[crear, _resp(401, {"e": 1})])),
            patch.object(ps.requests, "get", Mock(return_value=st_fin)),
            patch.object(ps.asyncio, "run", Mock()),
        ):
            with pytest.raises(HTTPException, match="expirado"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_publicar_error_api(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        crear = _resp(200, {"id": "cont8"})
        st_fin = _resp(200, {"status_code": "FINISHED"})
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(side_effect=[crear, _resp(400, {"e": 1})])),
            patch.object(ps.requests, "get", Mock(return_value=st_fin)),
            patch.object(ps.asyncio, "run", Mock()),
        ):
            with pytest.raises(HTTPException, match="Instagram API error"):
                _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)

    def test_publicar_sin_permalink_fallback(self, monkeypatch) -> None:
        _parches_instagram(monkeypatch)
        monkeypatch.setattr(ps, "_get_public_video_url", Mock(return_value="https://ok.com/x.mp4"))
        httpx = Mock()
        httpx.get = Mock(return_value=SimpleNamespace(status_code=200))
        crear = _resp(200, {"id": "cont9"})
        st_fin = _resp(200, {"status_code": "FINISHED"})
        publicar = _resp(200, None, text="ok")  # sin JSON → fallback permalink
        with (
            patch.dict(sys.modules, {"httpx": httpx}),
            patch.object(ps.requests, "post", Mock(side_effect=[crear, publicar])),
            patch.object(ps.requests, "get", Mock(return_value=st_fin)),
            patch.object(ps.asyncio, "run", Mock()),
        ):
            out = _publish_instagram(self._cuenta(), make_clip(uuid_lib.uuid4()), None)
        assert out["post_id"] == "cont9"
        assert out["url"] == PLATFORM_URLS["instagram"] + "cont9"


# ------------------------------------------------------------------ tiktok


class _CuentaAuditoriaExplota:
    @property
    def access_token(self) -> str:
        raise RuntimeError("token roto")

    @property
    def platform_account_id(self) -> str:
        raise RuntimeError("roto")


class TestPublishTiktok:
    def _cuenta(self) -> Any:
        return _fixtures.make_social_account(uuid_lib.uuid4(), platform="tiktok")

    def test_archivo_no_encontrado_404(self, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        clip = make_clip(uuid_lib.uuid4(), storage_path="/no/existe/clip.mp4")
        with pytest.raises(HTTPException, match="no encontrado para TikTok"):
            _publish_tiktok(self._cuenta(), clip, None)

    def test_archivo_por_candidatos_de_storage(self, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        clip = make_clip(uuid_lib.uuid4(), storage_path="clip1.mp4")
        candidato = tmp_path / "clip1.mp4"
        candidato.write_bytes(b"v")
        with (
            patch("os.path.exists", side_effect=lambda p: str(p) == str(candidato) or p == "clip1.mp4"),
            patch("os.path.getsize", Mock(return_value=1024)),
            patch.object(ps.requests, "post", Mock(return_value=_resp(200, {"data": {"publish_id": "p1", "upload_url": "https://up"}}))),
            patch.object(ps.requests, "put", Mock(return_value=_resp(200, {"ok": 1}))),
            patch("builtins.open", MagicMock(return_value=MagicMock(read=MagicMock(return_value=b"v")))),
        ):
            out = _publish_tiktok(self._cuenta(), clip, None)
        assert out["post_id"] == "p1"

    def test_getsize_explota(self, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        # 1ª llamada (loop de candidatos) ok; la de `file_size` explota
        with patch("os.path.getsize", Mock(side_effect=[10, OSError("bloqueado")])):
            with pytest.raises(HTTPException, match="No se pudo leer archivo"):
                _publish_tiktok(self._cuenta(), clip, None)

    def test_archivo_vacio(self, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        # en el loop de candidatos responde >0, al leer file_size responde 0
        with patch("os.path.getsize", Mock(side_effect=[10, 0])):
            with pytest.raises(HTTPException, match="vacío"):
                _publish_tiktok(self._cuenta(), clip, None)

    def test_init_401(self, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        with patch.object(ps.requests, "post", Mock(return_value=_resp(401, {"e": 1}))):
            with pytest.raises(HTTPException, match="expirado"):
                _publish_tiktok(self._cuenta(), clip, None)

    def test_init_error_api(self, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        with patch.object(ps.requests, "post", Mock(return_value=_resp(400, {"error_code": 1, "message": "bad"}))):
            with pytest.raises(HTTPException, match="TikTok API error 400"):
                _publish_tiktok(self._cuenta(), clip, None)

    def test_init_sin_upload_url(self, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        with patch.object(ps.requests, "post", Mock(return_value=_resp(200, None, text="ok"))):
            with pytest.raises(HTTPException, match="upload_url"):
                _publish_tiktok(self._cuenta(), clip, None)

    def test_upload_put_falla(self, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        init = _resp(200, {"data": {"publish_id": "p2", "upload_url": "https://up"}})
        put = _resp(500, {"e": 1}, text="boom")
        with (
            patch.object(ps.requests, "post", Mock(return_value=init)),
            patch.object(ps.requests, "put", Mock(return_value=put)),
        ):
            with pytest.raises(HTTPException, match="TikTok upload error 500"):
                _publish_tiktok(self._cuenta(), clip, None)

    def test_upload_put_excepcion(self, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        init = _resp(200, {"data": {"publish_id": "p3", "upload_url": "https://up"}})
        with (
            patch.object(ps.requests, "post", Mock(return_value=init)),
            patch.object(ps.requests, "put", Mock(side_effect=RuntimeError("red"))),
        ):
            with pytest.raises(HTTPException, match="Error subiendo archivo"):
                _publish_tiktok(self._cuenta(), clip, None)

    def test_share_url_preferida(self, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        cuenta = self._cuenta()
        cuenta.platform_username = "elcanal"
        init = _resp(
            200,
            {"data": {"publish_id": "p4", "upload_url": "https://up", "share_url": "https://tiktok.com/@x/v/99"}},
        )
        with (
            patch.object(ps.requests, "post", Mock(return_value=init)),
            patch.object(ps.requests, "put", Mock(return_value=_resp(201, {"ok": 1}))),
        ):
            out = _publish_tiktok(cuenta, clip, "cap")
        assert out["url"] == "https://tiktok.com/@x/v/99"

    def test_auditoria_explota_luego_token_roto(self, monkeypatch, tmp_path) -> None:
        """La auditoría inicial se tolera (670-671) pero el access_token roto
        explota más adelante al leer el token real (673)."""
        _sin_env_ngrok(monkeypatch)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = make_clip(uuid_lib.uuid4(), storage_path=str(archivo))
        with pytest.raises(RuntimeError, match="token roto"):
            _publish_tiktok(_CuentaAuditoriaExplota(), clip, None)


# ------------------------------------------------------------ publish_clip_task


class TestPublishClipTask:
    def _db_con_clip(self, user: Any, **clip_overrides: Any) -> tuple[FakeSession, Any]:
        db = FakeSession()
        clip = _clip(db, user, **clip_overrides)
        return db, clip

    def test_webhook_exitoso(self, db, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        fake_db, clip = self._db_con_clip(user)
        resp = _resp(200, {"id": "wh1", "url": "https://hook.com/wh1"})
        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps.requests, "post", Mock(return_value=resp)),
        ):
            out = publish_clip_task(clip.id, "webhook", "cap", webhook_url="https://hook.com")
        assert out["status"] == "published"
        assert clip.status == "PUBLISHED"
        assert clip.social_post_id == "wh1"

    def test_webhook_json_invalido(self, db, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        fake_db, clip = self._db_con_clip(user)
        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps.requests, "post", Mock(return_value=_resp(200, None, text="ok"))),
        ):
            out = publish_clip_task(clip.id, "webhook", None, webhook_url="https://hook.com")
        assert out["status"] == "published"

    def test_webhook_error_http_tambien_publica(self, db, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        fake_db, clip = self._db_con_clip(user)
        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps.requests, "post", Mock(return_value=_resp(500, None, text="caído"))),
        ):
            out = publish_clip_task(clip.id, "webhook", None, webhook_url="https://hook.com")
        assert out["status"] == "published"  # fallback con id fake

    def test_webhook_sin_url_genera_directo(self, db, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        fake_db, clip = self._db_con_clip(user)
        with patch.object(ps, "SessionLocal", lambda: fake_db):
            out = publish_clip_task(clip.id, "webhook", None)
        assert out["status"] == "published"
        assert out["url"].startswith(PLATFORM_URLS["webhook"])

    def test_plataforma_sin_cuenta_marca_failed(self, db, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        video = make_video(user.id)
        job = make_job(video.id)
        clip = make_clip(job.id, video_id=None)  # sin video_id → sin user_id resuelto
        db.seed(video, job, clip)
        with patch.object(ps, "SessionLocal", lambda: db):
            out = publish_clip_task(clip.id, "tiktok", "cap")
        assert out["status"] == "failed"
        assert out["code"] == 400
        assert clip.status == "FAILED"

    def test_plataforma_no_soportada_marca_failed(self, db, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        fake_db, clip = self._db_con_clip(user)
        with patch.object(ps, "SessionLocal", lambda: fake_db):
            out = publish_clip_task(clip.id, "snapchat", "cap", user_id=str(user.id))
        assert out["status"] == "failed"
        assert "snapchat" in out["error"]

    def test_plataforma_no_soportada_con_commit_roto(self, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        db = _CommitFailSession(fail_from=2)
        clip = _clip(db, user)
        with patch.object(ps, "SessionLocal", lambda: db):
            out = publish_clip_task(clip.id, "snapchat", "cap", user_id=str(user.id))
        assert out["status"] == "failed"

    def test_publicacion_generico_con_commit_roto(self, user, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        db = _CommitFailSession(fail_from=2)
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = _clip(db, user, storage_path=str(archivo))
        cuenta = _fixtures.make_social_account(user.id, platform="tiktok")
        db.push_result(FakeResult(scalar=cuenta))
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_tiktok", Mock(side_effect=RuntimeError("boom tiktok"))),
        ):
            out = publish_clip_task(clip.id, "tiktok", "cap", user_id=str(user.id))
        assert out["status"] == "failed"
        assert "boom tiktok" in out["error"]

    def test_refresh_explota_tiktok_desconecta(self, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        clip = _clip(db, user)
        cuenta = _fixtures.make_social_account(user.id, platform="tiktok", refresh_token="ref")
        db.push_result(FakeResult(scalar=cuenta))
        expirado = HTTPException(status_code=400, detail="Token de tiktok expirado, reconecta")
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_tiktok", Mock(side_effect=expirado)),
            patch.object(ps, "_refresh_account_token", Mock(side_effect=RuntimeError("refresh roto"))),
            patch.object(sys, "stdout", SimpleNamespace(flush=Mock(side_effect=ValueError("no")))),
        ):
            out = publish_clip_task(clip.id, "tiktok", "cap", user_id=str(user.id))
        assert out["status"] == "failed"
        assert "TikTok refresh failed" in out["error"]

    def test_refresh_explota_y_delete_falla_usa_sql(self, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        clip = _clip(db, user)
        cuenta = _fixtures.make_social_account(user.id, platform="tiktok", refresh_token="ref")
        db.push_result(FakeResult(scalar=cuenta))
        db.delete = Mock(side_effect=RuntimeError("delete roto"))
        expirado = HTTPException(status_code=400, detail="Token de tiktok expirado, reconecta")
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_tiktok", Mock(side_effect=expirado)),
            patch.object(ps, "_refresh_account_token", Mock(side_effect=RuntimeError("refresh roto"))),
        ):
            out = publish_clip_task(clip.id, "tiktok", "cap", user_id=str(user.id))
        assert out["status"] == "failed"

    def test_refresh_exitoso_reintenta_y_falla_de_nuevo(self, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        clip = _clip(db, user)
        cuenta = _fixtures.make_social_account(user.id, platform="youtube", refresh_token="ref")
        db.push_result(FakeResult(scalar=cuenta))
        expirado = HTTPException(status_code=400, detail="Token de youtube expirado")
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_youtube", Mock(side_effect=expirado)),
            patch.object(ps, "_refresh_account_token", Mock(return_value=True)),
        ):
            out = publish_clip_task(clip.id, "youtube", "cap", user_id=str(user.id))
        assert out["status"] == "failed"

    def test_refresh_falla_tiktok_desconecta(self, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        clip = _clip(db, user)
        cuenta = _fixtures.make_social_account(user.id, platform="tiktok", refresh_token="ref")
        db.push_result(FakeResult(scalar=cuenta))
        expirado = HTTPException(status_code=400, detail="Token de tiktok expirado")
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_tiktok", Mock(side_effect=expirado)),
            patch.object(ps, "_refresh_account_token", Mock(return_value=False)),
        ):
            out = publish_clip_task(clip.id, "tiktok", "cap", user_id=str(user.id))
        assert out["status"] == "failed"
        assert "desconecta" in out["error"]

    def test_refresh_falla_tiktok_y_delete_roto_usa_sql(self, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        clip = _clip(db, user)
        cuenta = _fixtures.make_social_account(user.id, platform="tiktok", refresh_token="ref")
        db.push_result(FakeResult(scalar=cuenta))
        db.delete = Mock(side_effect=RuntimeError("delete roto"))
        expirado = HTTPException(status_code=400, detail="Token de tiktok expirado")
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_tiktok", Mock(side_effect=expirado)),
            patch.object(ps, "_refresh_account_token", Mock(return_value=False)),
        ):
            out = publish_clip_task(clip.id, "tiktok", "cap", user_id=str(user.id))
        assert out["status"] == "failed"

    def test_refresh_falla_youtube_relanza(self, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        clip = _clip(db, user)
        cuenta = _fixtures.make_social_account(user.id, platform="youtube")
        db.push_result(FakeResult(scalar=cuenta))
        expirado = HTTPException(status_code=400, detail="Token de youtube expirado")
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_youtube", Mock(side_effect=expirado)),
            patch.object(ps, "_refresh_account_token", Mock(return_value=False)),
        ):
            out = publish_clip_task(clip.id, "youtube", "cap", user_id=str(user.id))
        assert out["status"] == "failed"
        assert "expirado" in out["error"]

    def test_sin_refresh_token_tiktok_desconecta(self, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        clip = _clip(db, user)
        cuenta = _fixtures.make_social_account(user.id, platform="tiktok", refresh_token=None)
        db.push_result(FakeResult(scalar=cuenta))
        expirado = HTTPException(status_code=400, detail="Token de tiktok expirado")
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_tiktok", Mock(side_effect=expirado)),
        ):
            out = publish_clip_task(clip.id, "tiktok", "cap", user_id=str(user.id))
        assert out["status"] == "failed"

    def test_sin_refresh_token_youtube_relanza(self, user, monkeypatch) -> None:
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        clip = _clip(db, user)
        cuenta = _fixtures.make_social_account(user.id, platform="youtube", refresh_token=None)
        db.push_result(FakeResult(scalar=cuenta))
        expirado = HTTPException(status_code=400, detail="Token de youtube expirado")
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_youtube", Mock(side_effect=expirado)),
        ):
            out = publish_clip_task(clip.id, "youtube", "cap", user_id=str(user.id))
        assert out["status"] == "failed"

    def test_publica_exitoso(self, user, monkeypatch, tmp_path) -> None:
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = _clip(db, user, storage_path=str(archivo))
        cuenta = _fixtures.make_social_account(user.id, platform="tiktok")
        db.push_result(FakeResult(scalar=cuenta))
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(
                ps,
                "_publish_tiktok",
                Mock(return_value={"status": "published", "post_id": "p9", "url": "https://tt.com/v/p9"}),
            ),
        ):
            out = publish_clip_task(clip.id, "tiktok", "cap", user_id=str(user.id))
        assert out["status"] == "published"
        assert clip.status == "PUBLISHED"
        assert clip.social_post_url == "https://tt.com/v/p9"
        assert clip.error_log is None

    def test_publica_exitoso_con_setters_rotos(self, user, monkeypatch, tmp_path) -> None:
        """social_network / error_log con setter roto → se tolera (1001-1002, 1010-1011)."""
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = _clip(db, user, storage_path=str(archivo))

        cls = type("Clip", (), {})
        stub = cls()
        stub.id = clip.id
        stub.status = clip.status
        stub.publication_status = clip.publication_status
        stub.published_platform = None
        stub.social_post_id = None
        stub.social_post_url = None
        stub.published_at = None
        stub.video_id = clip.video_id
        stub.job_id = clip.job_id
        stub.storage_path = clip.storage_path
        stub.title = clip.title

        def _setter_social(self: Any, value: Any) -> None:
            raise RuntimeError("social_network roto")

        def _setter_error(self: Any, value: Any) -> None:
            raise RuntimeError("error_log roto")

        cls.social_network = property(lambda self: None, _setter_social)
        cls.error_log = property(lambda self: None, _setter_error)
        db.seed(stub)

        cuenta = _fixtures.make_social_account(user.id, platform="youtube")
        db.push_result(FakeResult(scalar=cuenta))
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_youtube", Mock(return_value={"status": "published", "post_id": "p10", "url": "u"})),
        ):
            out = publish_clip_task(clip.id, "youtube", "cap", user_id=str(user.id))
        assert out["status"] == "published"

    def test_audit_con_cuenta_explota_marca_failed(self, user, monkeypatch, tmp_path) -> None:
        """La auditoría de BD tolera el error (897-898), pero el token roto
        explota al publicar → el job termina FAILED."""
        _sin_env_ngrok(monkeypatch)
        db = FakeSession()
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"v")
        clip = _clip(db, user, storage_path=str(archivo))
        db.push_result(FakeResult(scalar=_CuentaAuditoriaExplota()))
        with (
            patch.object(ps, "SessionLocal", lambda: db),
            patch.object(ps, "_publish_tiktok", Mock(return_value={"status": "published", "post_id": "p", "url": "u"})),
        ):
            out = publish_clip_task(clip.id, "tiktok", "cap", user_id=str(user.id))
        assert out["status"] == "failed"
        assert "token roto" in out["error"]


class _CommitFailSession(FakeSession):
    def __init__(self, fail_from: int = 2) -> None:
        super().__init__()
        self._n = 0
        self.fail_from = fail_from

    def commit(self) -> None:
        self._n += 1
        if self._n >= self.fail_from:
            raise RuntimeError("commit roto")
        return super().commit()
