"""Cobertura de `services/publish_service.py` — publicación real a redes.

Todas las llamadas HTTP ("requests") están mockeadas; la DB es FakeSession.
"""

from __future__ import annotations

import asyncio
import sys
import uuid as uuid_lib
from datetime import timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

import _fixtures
from _fixtures import FakeResult, FakeSession, make_clip, make_video, now_utc
import conftest as _c  # helpers del harness (make_social_account, etc.)

from backend_fastapi.app.services import publish_service as ps
from backend_fastapi.app.services.publish_service import (
    PLATFORM_URLS,
    _ensure_token_fresh,
    _get_public_video_url,
    _get_social_account,
    _handle_token_expired,
    _is_token_expired_error,
    publish_clip_task,
    _refresh_account_token,
)

_SOCIAL = _c.make_social_account
_JOB = _c.make_job


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
    job = _JOB(video.id)
    clip = make_clip(job.id, video.id, **overrides)
    db.seed(video, job, clip)
    return clip


def _account(user_id: Any, platform: str = "tiktok") -> Any:
    return _SOCIAL(user_id, platform=platform)


# ------------------------------------------------------------------ helpers


class TestHelpersPublicar:
    def test_is_token_expired_error_variantes(self) -> None:
        positivos = [
            "Token de tiktok expirado, reconecta",
            "status 401 unauthorized",
            "invalid_token en respuesta",
        ]
        for detalle in positivos:
            assert _is_token_expired_error(SimpleNamespace(detail=detalle)) is True
        assert _is_token_expired_error(SimpleNamespace(detail="otro error")) is False
        assert _is_token_expired_error(SimpleNamespace(detail=None)) is False

    def test_handle_token_expired_401(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            _handle_token_expired("youtube", _resp(401))
        assert excinfo.value.status_code == 400
        assert "expirado" in excinfo.value.detail

    def test_get_public_video_url_usa_dominio_publico(self, monkeypatch) -> None:
        monkeypatch.setattr(ps, "_get_ngrok_domain", lambda: "api.clipsai.xyz")
        clip = make_clip(uuid_lib.uuid4())
        url = ps._get_public_video_url(clip)
        assert url.startswith("https://api.clipsai.xyz/clips/")
        assert str(clip.id) in url

    def test_generate_fake_id_formato(self) -> None:
        assert len(ps._generate_fake_id()) >= 12

    def test_ensure_token_fresh_llama_refresh_cuando_vence_pronto(self) -> None:
        cuenta = _SOCIAL(uuid_lib.uuid4(), platform="tiktok")
        cuenta.token_expires_at = now_utc() + timedelta(minutes=2)
        fake_db = FakeSession()
        refresh = Mock()
        with patch.object(ps, "_refresh_account_token", refresh):
            _ensure_token_fresh(cuenta, "tiktok", fake_db)
        refresh.assert_called_once()

    def test_ensure_token_fresh_no_hace_nada_si_vence_lejos(self) -> None:
        cuenta = _SOCIAL(uuid_lib.uuid4(), platform="tiktok")
        cuenta.token_expires_at = now_utc() + timedelta(days=30)
        fake_db = FakeSession()
        refresh = Mock()
        with patch.object(ps, "_refresh_account_token", refresh):
            _ensure_token_fresh(cuenta, "tiktok", fake_db)
        refresh.assert_not_called()


# ------------------------------------------------------------------ get account


class TestGetSocialAccount:
    def test_cuenta_encontrada_por_orm(self, db, user) -> None:
        cuenta = _account(user.id)
        db.push_result(FakeResult(scalar=cuenta))
        assert _get_social_account(db, user.id, "youtube") is cuenta

    def test_400_si_no_hay_cuenta(self, db, user) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException, match="no vinculada"):
            _get_social_account(db, user.id, "youtube")

    def test_400_si_cuenta_sin_token(self, db, user) -> None:
        cuenta = _SOCIAL(user.id, platform="youtube")
        cuenta.access_token = None
        db.push_result(FakeResult(scalar=cuenta))
        from fastapi import HTTPException

        with pytest.raises(HTTPException, match="no vinculada"):
            _get_social_account(db, user.id, "youtube")


# ------------------------------------------------------------------ refresh


class TestRefreshToken:
    def test_sin_refresh_token_devuelve_false(self) -> None:
        cuenta = _SOCIAL(uuid_lib.uuid4())
        cuenta.refresh_token = ""
        assert _refresh_account_token(cuenta, "tiktok", FakeSession()) is False

    def test_tiktok_refresh_exitoso(self, monkeypatch, db) -> None:
        cuenta = _SOCIAL(uuid_lib.uuid4())
        cuenta.refresh_token = "ref-viejo"
        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "tk")
        monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "ks")
        respuesta = _resp(200, {"access_token": "nuevo-token", "refresh_token": "ref-nuevo", "expires_in": 7200})
        with patch.object(ps.requests, "post", return_value=respuesta):
            assert _refresh_account_token(cuenta, "tiktok", db) is True
        assert cuenta.access_token == "nuevo-token"

    def test_tiktok_refresh_status_400(self, monkeypatch, db) -> None:
        cuenta = _SOCIAL(uuid_lib.uuid4())
        cuenta.refresh_token = "ref"
        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "tk")
        monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "ks")
        with patch.object(ps.requests, "post", return_value=_resp(400, text='{"error": "bad"}')):
            with pytest.raises(Exception, match="refresh failed"):
                _refresh_account_token(cuenta, "tiktok", db)

    def test_youtube_refresh_sin_credenciales_devuelve_false(self, monkeypatch) -> None:
        cuenta = _SOCIAL(uuid_lib.uuid4(), platform="youtube")
        cuenta.refresh_token = "ref"
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        assert _refresh_account_token(cuenta, "youtube", FakeSession()) is False

    def test_youtube_refresh_exitoso(self, monkeypatch, db) -> None:
        cuenta = _SOCIAL(uuid_lib.uuid4(), platform="youtube")
        cuenta.refresh_token = "ref"
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "cs")
        respuesta = _resp(200, {"access_token": "yt-nuevo", "expires_in": 3600})
        with patch.object(ps.requests, "post", return_value=respuesta):
            assert _refresh_account_token(cuenta, "youtube", db) is True
        assert cuenta.access_token == "yt-nuevo"

    def test_youtube_refresh_401(self, monkeypatch, db) -> None:
        cuenta = _SOCIAL(uuid_lib.uuid4(), platform="youtube")
        cuenta.refresh_token = "ref"
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "cs")
        with patch.object(ps.requests, "post", return_value=_resp(401, text="unauthorized")):
            assert _refresh_account_token(cuenta, "youtube", db) is False


# ------------------------------------------------------------------ publish por plataforma


class TestPublishPerPlatform:
    def test_youtube_ok_crea_multipart(self, tmp_path, user) -> None:
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"mp4")
        clip = make_clip(_JOB(uuid_lib.uuid4()).id, storage_path=str(archivo))
        cuenta = _SOCIAL(user.id, platform="youtube")

        respuesta = _resp(200, {"id": "vid-123"})
        with patch.object(ps.requests, "post", return_value=respuesta) as post:
            resultado = ps._publish_youtube(cuenta, clip, "Mi caption")
        assert resultado == {"status": "published", "platform": "youtube", "post_id": "vid-123",
                             "url": "https://www.youtube.com/watch?v=vid-123"}
        url = post.call_args[0][0]
        assert "uploadType=multipart" in url
        assert "videos?part" in url or "part=snippet" in url

    def test_youtube_404_sin_archivo(self, user) -> None:
        from fastapi import HTTPException

        clip = make_clip(_JOB(uuid_lib.uuid4()).id, storage_path="/tmp/no/existe.mp4")
        cuenta = _SOCIAL(user.id, platform="youtube")
        with pytest.raises(HTTPException, match="no encontrado para YouTube"):
            ps._publish_youtube(cuenta, clip, None)

    def test_youtube_error_500_api(self, tmp_path, user) -> None:
        from fastapi import HTTPException

        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"mp4")
        clip = make_clip(_JOB(uuid_lib.uuid4()).id, storage_path=str(archivo))
        cuenta = _SOCIAL(user.id, platform="youtube")
        with patch.object(ps.requests, "post", return_value=_resp(500, text="server error")):
            with pytest.raises(HTTPException, match="YouTube API error"):
                ps._publish_youtube(cuenta, clip, None)

    def test_tiktok_flujo_completo(self, tmp_path, user) -> None:
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"mp4-para-tiktok")
        clip = make_clip(_JOB(uuid_lib.uuid4()).id, storage_path=str(archivo))
        cuenta = _SOCIAL(user.id, platform="tiktok")

        init_resp = _resp(200, {"data": {"publish_id": "pub-1", "upload_url": "https://tiktok-upload/x"}})
        put_resp = _resp(200, text='{"ok": true}')

        def put(*a, **k):
            return put_resp

        respuestas = [init_resp]

        def post(*args, **kwargs):
            return respuestas.pop(0)

        with (
            patch.object(ps.requests, "post", side_effect=post),
            patch.object(ps.requests, "put", side_effect=put),
        ):
            resultado = ps._publish_tiktok(cuenta, clip, "cap")
        assert resultado["status"] == "published"
        assert resultado["post_id"] == "pub-1"
        assert "/video/pub-1" in resultado["url"]

    def test_tiktok_404_sin_archivo(self, user) -> None:
        from fastapi import HTTPException

        clip = make_clip(_JOB(uuid_lib.uuid4()).id, storage_path="no/existe.mp4")
        cuenta = _SOCIAL(user.id, platform="tiktok")
        with pytest.raises(HTTPException, match="no encontrado para TikTok"):
            ps._publish_tiktok(cuenta, clip, None)

    def test_tiktok_api_400(self, tmp_path, user) -> None:
        from fastapi import HTTPException

        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"mp4")
        clip = make_clip(_JOB(uuid_lib.uuid4()).id, storage_path=str(archivo))
        cuenta = _SOCIAL(user.id, platform="tiktok")
        with patch.object(ps.requests, "post", return_value=_resp(400, text='{"error_code":1}')):
            with pytest.raises(HTTPException, match="TikTok API error"):
                ps._publish_tiktok(cuenta, clip, None)

    def test_instagram_flujo_completo(self, tmp_path, user, monkeypatch) -> None:
        clip = make_clip(_JOB(uuid_lib.uuid4()).id)
        cuenta = _SOCIAL(user.id, platform="instagram")
        cuenta.platform_account_id = "ig-123"
        monkeypatch.setattr(ps, "_get_ngrok_domain", lambda: "api.clipsai.xyz")
        monkeypatch.setattr(ps, "_resolve_instagram_business_id", lambda acc: "ig-123")

        # httpx pre-check POST 200 (ig_url accesible)
        httpx_mod = types_module = SimpleNamespace(get=Mock(return_value=SimpleNamespace(status_code=200)))
        # respuestas: crear container -> id; polling -> FINISHED; publicar -> permalink
        container = _resp(200, {"id": "cont-1"})
        estado = _resp(200, {"status_code": "FINISHED"})
        publish = _resp(200, {"id": "post-9", "permalink": "https://www.instagram.com/reel/post-9/"})

        respuesta_post = [container, publish]
        respuesta_get = [estado]

        monkeypatch.setattr(ps, "requests", ps.requests)  # noop simbólico
        with (
            patch.dict(sys.modules, {"httpx": httpx_mod}),
            patch.object(ps.requests, "get", side_effect=respuesta_get),
            patch.object(ps.requests, "post", side_effect=respuesta_post),
        ):
            resultado = ps._publish_instagram(cuenta, clip, "cap")

        assert resultado["status"] == "published"
        assert resultado["post_id"] == "post-9"

    def test_instagram_sin_creation_id(self, tmp_path, user, monkeypatch) -> None:
        from fastapi import HTTPException

        clip = make_clip(_JOB(uuid_lib.uuid4()).id)
        cuenta = _SOCIAL(user.id, platform="instagram")
        cuenta.platform_account_id = "ig-1"
        monkeypatch.setattr(ps, "_get_ngrok_domain", lambda: "api.clipsai.xyz")
        monkeypatch.setattr(ps, "_resolve_instagram_business_id", lambda acc: "ig-123")

        httpx_mod = SimpleNamespace(get=Mock(return_value=SimpleNamespace(status_code=200)))
        with (
            patch.dict(sys.modules, {"httpx": httpx_mod}),
            patch.object(ps.requests, "post", return_value=_resp(200, {"sin_id": True})),
        ):
            with pytest.raises(HTTPException, match="creation_id"):
                ps._publish_instagram(cuenta, clip, None)

    def test_instagram_url_publica_caida(self, tmp_path, user, monkeypatch) -> None:
        from fastapi import HTTPException

        clip = make_clip(_JOB(uuid_lib.uuid4()).id)
        cuenta = _SOCIAL(user.id, platform="instagram")
        cuenta.platform_account_id = "ig-1"
        monkeypatch.setattr(ps, "_get_ngrok_domain", lambda: "api.clipsai.xyz")
        monkeypatch.setattr(ps, "_resolve_instagram_business_id", lambda acc: "ig-123")

        httpx_mod = SimpleNamespace(get=Mock(return_value=SimpleNamespace(status_code=503)))
        with patch.dict(sys.modules, {"httpx": httpx_mod}):
            with pytest.raises(HTTPException, match="no accesible"):
                ps._publish_instagram(cuenta, clip, None)


# ------------------------------------------------------------------ publish_clip_task


class TestPublishClipTask:
    def test_clip_inexistente_devuelve_none(self, monkeypatch) -> None:
        fake_db = FakeSession()
        with patch.object(ps, "SessionLocal", lambda: fake_db):
            assert publish_clip_task(uuid_lib.uuid4(), "tiktok", None) is None

    def test_webhook_sin_url_devuelve_publicado_modulo_t(self, monkeypatch, user) -> None:
        fake_db = FakeSession()
        clip = _clip(fake_db, user)
        with patch.object(ps, "SessionLocal", lambda: fake_db):
            result = publish_clip_task(clip.id, "webhook", "cap", webhook_url=None)
        assert result is not None and result["status"] == "published"
        assert clip.status == "PUBLISHED"
        assert clip.publication_status == "PUBLISHED"
        assert clip.social_post_url and str(clip.id)

    def test_webhook_con_url_real(self, monkeypatch, user) -> None:
        fake_db = FakeSession()
        clip = _clip(fake_db, user)
        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps.requests, "post", return_value=_resp(200, {"id": "w-9", "url": "https://hook/x"})),
        ):
            result = publish_clip_task(clip.id, "webhook", "cap", webhook_url="https://hook")
        assert result["post_id"] == "w-9"
        assert result["url"] == "https://hook/x"

    def test_webhook_excepcion_igual_publica(self, monkeypatch, user) -> None:
        fake_db = FakeSession()
        clip = _clip(fake_db, user)
        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps.requests, "post", side_effect=RuntimeError("tunnel down")),
        ):
            result = publish_clip_task(clip.id, "webhook", "cap", webhook_url="https://hook")
        assert result["status"] == "published"  # el webhook tiene fallback tolerante
        assert clip.status == "PUBLISHED"

    def test_plataforma_invalida_devuelve_failed(self, monkeypatch, user) -> None:
        fake_db = FakeSession()
        clip = _clip(fake_db, user)
        with patch.object(ps, "SessionLocal", lambda: fake_db):
            result = publish_clip_task(clip.id, "facebook", "cap")
        assert result["status"] == "failed"
        assert clip.status == "FAILED"

    def test_plataforma_real_ok_tiktok(self, monkeypatch, user) -> None:
        fake_db = FakeSession()
        clip = _clip(fake_db, user)
        cuenta = _account(user.id, "tiktok")
        fake_db.push_result(FakeResult(scalar=cuenta))  # _get_social_account escucha el 1° execute

        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps, "_ensure_token_fresh", Mock()),
            patch.object(ps, "_publish_tiktok", Mock(return_value={"status": "published", "post_id": "tt1", "url": "https://www.tiktok.com/@u/video/tt1"})),
        ):
            result = publish_clip_task(clip.id, "tiktok", "cap")
        assert result["status"] == "published"
        assert clip.status == "PUBLISHED"
        assert clip.social_post_id == "tt1"
        assert clip.error_log is None

    def test_token_expirado_refresca_y_reintenta(self, monkeypatch, user) -> None:
        from fastapi import HTTPException

        fake_db = FakeSession()
        clip = _clip(fake_db, user)
        cuenta = _account(user.id, "youtube")
        cuenta.refresh_token = "ref"
        fake_db.push_result(FakeResult(scalar=cuenta))

        msg = "Token de youtube expirado, reconecta"
        base_llamadas = [
            Mock(side_effect=HTTPException(status_code=400, detail=msg)),  # primer intento
            Mock(return_value={"status": "published", "post_id": "yt", "url": "https://yt/x"}),  # reintentar
        ]
        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps, "_publish_youtube", Mock(side_effect=lambda *a, **k: _pop(base_llamadas)(None, None, None))),
            patch.object(ps, "_is_token_expired_error", Mock(return_value=True)),
            patch.object(ps, "_refresh_account_token", Mock(return_value=True)),
        ):
            result = publish_clip_task(clip.id, "youtube", "cap")
        assert result["status"] == "published"
        assert clip.status == "PUBLISHED"

    def test_token_expirado_sin_refresh_tiktok_marca_failed(self, monkeypatch, user) -> None:
        from fastapi import HTTPException

        fake_db = FakeSession()
        clip = _clip(fake_db, user)
        cuenta = _account(user.id, "tiktok")
        cuenta.refresh_token = ""
        fake_db.push_result(FakeResult(scalar=cuenta))

        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps, "_ensure_token_fresh", Mock()),
            patch.object(ps, "_publish_tiktok", Mock(side_effect=HTTPException(status_code=401, detail="Token de tiktok expirado"))),
        ):
            result = publish_clip_task(clip.id, "tiktok", "cap")
        assert result["status"] == "failed"
        assert clip.status == "FAILED"
        assert clip.error_log and "expirado" in clip.error_log

    def test_publicar_error_generico_marca_failed(self, monkeypatch, user) -> None:
        fake_db = FakeSession()
        clip = _clip(fake_db, user)
        cuenta = _account(user.id, "instagram")
        fake_db.push_result(FakeResult(scalar=cuenta))

        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps, "_ensure_token_fresh", Mock()),
            patch.object(ps, "_publish_instagram", Mock(side_effect=RuntimeError("timeout de Meta"))),
        ):
            result = publish_clip_task(clip.id, "instagram", "cap")
        assert result["status"] == "failed"
        assert clip.status == "FAILED"

    def test_resuelve_user_desde_video(self, monkeypatch, user) -> None:
        fake_db = FakeSession()
        clip = _clip(fake_db, user)
        cuenta = _account(user.id, "tiktok")
        fake_db.push_result(FakeResult(scalar=cuenta))
        capturadas: dict[str, Any] = {}

        def fake_publish(account, clip_arg, caption):
            capturadas["account"] = account
            return {"status": "published", "post_id": "p", "url": "https://u/x"}

        with (
            patch.object(ps, "SessionLocal", lambda: fake_db),
            patch.object(ps, "_ensure_token_fresh", Mock()),
            patch.object(ps, "_publish_tiktok", Mock(side_effect=fake_publish)),
        ):
            publish_clip_task(clip.id, "tiktok", "cap", user_id=None)
        assert str(capturadas["account"].user_id) == str(user.id)


def _pop(pila: list[Mock]) -> Mock:
    return pila.pop(0)
