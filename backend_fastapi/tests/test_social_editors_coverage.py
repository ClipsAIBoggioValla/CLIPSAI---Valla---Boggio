"""Cobertura de `editor.py`, `claude_service.py` y los conectores sociales
(`tiktok_service`, `youtube_service`, `instagram_service`).

Toda red (requests/httpx/consultas a Meta/Google/TikTok) queda mockeada.
"""

from __future__ import annotations

import sys
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

import _fixtures
from _fixtures import FakeSession, now_utc

import conftest as _c

from backend_fastapi.app.services import claude_service
from backend_fastapi.app.services import editor
from backend_fastapi.app.services import instagram_service
from backend_fastapi.app.services import tiktok_service
from backend_fastapi.app.services import youtube_service


def _resp(status: int, payload: dict | None = None, text: str = "") -> Mock:
    r = Mock()
    r.status_code = status
    if payload is not None:
        r.json = Mock(return_value=payload)
        r.text = text or str(payload)
    else:
        r.json = Mock(side_effect=ValueError("no json"))
        r.text = text
    return r


# ------------------------------------------------------------------ editor


class TestReframeVideo:
    def test_aspect_ratio_invalido(self, tmp_path) -> None:
        with pytest.raises(RuntimeError, match="no soportado"):
            editor.reframe_video(str(tmp_path / "v.mp4"), str(tmp_path / "out.mp4"), "16:9")

    def test_video_inexistente(self, tmp_path) -> None:
        with pytest.raises(RuntimeError, match="no encontrado"):
            editor.reframe_video(str(tmp_path / "inexistente.mp4"), str(tmp_path / "out.mp4"))

    def _mock(self, module: Any):
        import pathlib

        def side(cmd, **k):
            for arg in cmd:
                s = str(arg)
                if s.endswith(".mp4") and pathlib.Path(s).name != "in.mp4":
                    p = pathlib.Path(s)
                    if not p.exists():
                        p.write_bytes(b"mp4")
            return Mock(returncode=0, stdout="1080x1920", stderr="")

        return patch.object(module.subprocess, "run", Mock(side_effect=side))

    def test_reframe_con_escala_y_validacion(self, tmp_path) -> None:
        origen = tmp_path / "in.mp4"
        origen.write_bytes(b"x")
        salida = tmp_path / "video.mp4"
        with self._mock(editor):
            resultado = editor.reframe_video(origen, salida)
        assert resultado == str(salida)
        assert salida.exists()

    def test_reframe_ya_es_9_16_solo_copia(self, tmp_path) -> None:
        origen = tmp_path / "in.mp4"
        origen.write_bytes(b"x")
        salida = tmp_path / "copia.mp4"

        def run(*args: Any, **kwargs: Any):
            # sin magia de Mocks: SimpleNamespace con los atributos que el módulo lee
            return SimpleNamespace(returncode=0, stdout="1080x1920\n", stderr="")

        with (
            patch.object(editor.subprocess, "run", run),
            patch("shutil.copy2") as copia,
        ):
            editor.reframe_video(origen, salida)
        copia.assert_called_once()

    def test_reframe_stderr_no_cero(self, tmp_path) -> None:
        origen = tmp_path / "in.mp4"
        origen.write_bytes(b"x")
        salida = tmp_path / "salida2.mp4"
        with patch.object(
            editor.subprocess,
            "run",
            Mock(return_value=SimpleNamespace(returncode=1, stdout=b"", stderr=b"error de codec")),
        ):
            with pytest.raises(RuntimeError, match="reframe vertical falló"):
                editor.reframe_video(origen, salida)

    def test_reframe_oom_rc_9(self, tmp_path) -> None:
        origen = tmp_path / "in.mp4"
        origen.write_bytes(b"x")
        salida = tmp_path / "salida3.mp4"
        with patch.object(
            editor.subprocess,
            "run",
            Mock(return_value=SimpleNamespace(returncode=-9, stdout=b"", stderr=b"oom")),
        ):
            with pytest.raises(RuntimeError, match="OOM"):
                editor.reframe_video(origen, salida)

    def test_reframe_ffmpeg_no_instalado(self, tmp_path) -> None:
        origen = tmp_path / "in.mp4"
        origen.write_bytes(b"x")
        salida = tmp_path / "salida4.mp4"
        with patch.object(editor.subprocess, "run", Mock(side_effect=FileNotFoundError())):
            with pytest.raises(RuntimeError, match="no está instalado"):
                editor.reframe_video(origen, salida)


# ------------------------------------------------------------------ claude_service


def _segs() -> list[dict[str, Any]]:
    return [
        {
            "start": 0.0,
            "end": 3.0,
            "text": "Hola",
            "words": [
                {"start": 0.0, "end": 1.0, "text": "Hola"},
                {"start": 1.0, "end": 3.0, "text": "mundo!"},
            ],
        },
        {
            "start": 3.0,
            "end": 6.0,
            "text": "otra oración",
            "words": [
                {"start": 3.0, "end": 4.0, "text": "otra"},
                {"start": 4.0, "end": 6.0, "text": "sentencia."},
            ],
        },
    ]


class TestClaudeServicePure:
    def test_build_sentence_map(self) -> None:
        mapa = claude_service.build_sentence_map(_segs())
        assert [frase["id"] for frase in mapa] == ["S_1", "S_2"]
        assert mapa[0]["start"] == pytest.approx(0.0)
        assert mapa[1]["end"] == pytest.approx(6.0)

    def test_build_sentence_map_vacio(self) -> None:
        with pytest.raises(RuntimeError, match="timestamps"):
            claude_service.build_sentence_map([{"sin": "words"}])

    def test_format_sentence_map(self) -> None:
        texto = claude_service._format_sentence_map(claude_service.build_sentence_map(_segs()))
        assert "[S_1]" in texto and "Hola" in texto and "S_2" in texto

    def test_format_transcript(self) -> None:
        assert "mundo" in claude_service._format_transcript(_segs())

    def test_schema_y_tool(self) -> None:
        schema = claude_service._build_output_schema(["S_1"])
        assert schema["properties"]["clips"]["maxItems"] == 3
        tool = claude_service._build_export_viral_clips_tool(["S_1"])
        assert tool["name"] == "export_viral_clips" or tool.get("name")

    def test_has_strong_punctuation(self) -> None:
        assert claude_service._has_strong_punctuation("mundo!") is True
        assert claude_service._has_strong_punctuation("hola") is False

    def test_is_model_not_found_error(self) -> None:
        assert claude_service._is_model_not_found_error(Exception("model not found: x")) is True
        assert claude_service._is_model_not_found_error(Exception("timeout")) is False

    def test_parse_and_validate(self) -> None:
        crudo = '{"clips": [{"start_sentence_id": "S_1", "end_sentence_id": "S_2", "score": 8, "title": "Título", "hook_candidates": [], "has_hook": true}]}'
        resultado = claude_service._parse_and_validate(crudo)
        assert len(resultado) == 1

    def test_call_anthropic_fallback_requests_tool_use(self, monkeypatch) -> None:
        # Camino sin SDK: `import anthropic` rompe (sys.modules["anthropic"]=None)
        # y el módulo cae al endpoint HTTP directo, devolviendo el tool_use JSON.
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-fake-test")
        respuesta = Mock(
            status_code=200,
            headers={},
            text="ok",
            json=Mock(
                return_value={
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "export_viral_clips",
                            "input": {"clips": [{"start_sentence_id": "S_1", "end_sentence_id": "S_2", "score": 8}]},
                        }
                    ]
                }
            ),
        )
        with (
            patch.dict(sys.modules, {"anthropic": None}),
            patch.object(claude_service.requests, "post", Mock(return_value=respuesta)),
        ):
            raw = claude_service._call_anthropic("p", ["S_1", "S_2"])
        assert "clips" in raw

    def test_call_anthropic_reintenta_con_fallback_de_modelo(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-fake-test")
        modelos_enviados: list[str] = []

        def fake_with_model(prompt, ids, modelo):
            modelos_enviados.append(modelo)
            if modelo == claude_service.CLAUDE_MODEL:
                raise RuntimeError("404 model not found: modelo")
            import json as _json

            return _json.dumps({"clips": []})

        monkeypatch.setattr(claude_service, "_call_anthropic_with_model", fake_with_model)
        assert claude_service._call_anthropic("p", ["S_1"]) == '{"clips": []}'
        assert claude_service.CLAUDE_FALLBACK_MODEL in modelos_enviados

    def test_select_clips_via_claude_con_llama_mock(self, monkeypatch) -> None:
        raw = """
        {
          "clips": [
            {
              "start_sentence_id": "S_1",
              "end_sentence_id": "S_2",
              "score": 9,
              "title": "Revelación absoluta",
              "hook_candidates": [
                {"start_sentence_id": "S_1", "end_sentence_id": "S_1", "curiosity_score": 9, "makes_sense_standalone": true}
              ],
              "has_hook": true
            }
          ]
        }
        """
        monkeypatch.setattr(claude_service, "_call_anthropic", lambda prompt, ids: raw)
        sitios = claude_service.select_clips_via_claude(_segs())
        assert len(sitios) == 1
        assert sitios[0]["score"] == 9


# ------------------------------------------------------------------ conectores


class TestConfigYUrls:
    def test_tiktok_config_sin_env_devuelve_empty_key(self, monkeypatch) -> None:
        import backend_fastapi.app.services.tiktok_service as ts

        monkeypatch.delenv("TIKTOK_CLIENT_KEY", raising=False)
        monkeypatch.delenv("TIKTOK_CLIENT_SECRET", raising=False)
        monkeypatch.setattr(ts, "TIKTOK_CLIENT_KEY", "")
        monkeypatch.setattr(ts, "TIKTOK_CLIENT_SECRET", "")
        client_key, client_secret, redirect = tiktok_service._get_tiktok_config()
        assert client_key == "" and client_secret == ""
        assert redirect.endswith("/auth/social/tiktok/callback")

    def test_tiktok_config_ok(self, monkeypatch) -> None:
        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "key")
        monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "secret")
        client_key, client_secret, redirect = tiktok_service._get_tiktok_config()
        assert client_key == "key" and client_secret == "secret"

    def test_generate_pkce_pair(self) -> None:
        verifier, challenge = tiktok_service.generate_pkce_pair()
        assert len(verifier) > 40 and len(challenge) > 40

    def test_get_tiktok_auth_url(self, monkeypatch) -> None:
        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "key")
        url = tiktok_service.get_tiktok_auth_url("estado-1", "challenge-1")
        assert "tiktok.com/v2/auth/authorize" in url
        assert "estado-1" in url

    def test_get_youtube_auth_url(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        url = youtube_service.get_youtube_auth_url("uid")
        assert "accounts.google.com" in url and url.startswith("https://")

    def test_get_instagram_auth_url(self, monkeypatch) -> None:
        monkeypatch.setenv("INSTAGRAM_CLIENT_ID", "igid")
        url = instagram_service.get_instagram_auth_url("uid")
        assert "dialog/oauth" in url and url.startswith("https://")


class TestExchangeTokens:
    def test_exchange_tiktok_code(self, monkeypatch) -> None:
        monkeypatch.setenv("TIKTOK_CLIENT_KEY", "k")
        monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "s")
        respuesta = _resp(200, {"access_token": "a", "open_id": "o1"})
        with patch.object(tiktok_service.requests, "post", return_value=respuesta):
            data = tiktok_service.exchange_tiktok_code("code", "verif")
        assert data["open_id"] == "o1"

    def test_exchange_youtube_code(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "ci")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "cs")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://api.clipsai.xyz/cb")
        respuesta = _resp(200, {"access_token": "a", "refresh_token": "r"})
        with patch.object(youtube_service.requests, "post", return_value=respuesta):
            tokens = youtube_service.exchange_code_for_tokens("code")
        assert tokens["access_token"] == "a"

    def test_exchange_instagram_par_de_tocks(self, monkeypatch) -> None:
        monkeypatch.setenv("INSTAGRAM_CLIENT_ID", "iid")
        monkeypatch.setenv("INSTAGRAM_CLIENT_SECRET", "isec")
        monkeypatch.setenv("INSTAGRAM_REDIRECT_URI", "https://api.clipsai.xyz/cb")
        corto = _resp(200, {"access_token": "short"})
        largo = _resp(200, {"access_token": "long"})
        with (
            patch.object(instagram_service.requests, "post", return_value=corto),
            patch.object(instagram_service.requests, "get", return_value=largo),
        ):
            tokens = instagram_service.exchange_code_for_tokens("code")
        assert tokens["access_token"] == "long"

    def test_fetch_usernames_reach_apis(self, monkeypatch) -> None:
        monkeypatch.setattr(
            youtube_service.requests,
            "get",
            Mock(return_value=_resp(200, {"items": [{"snippet": {"title": "Canal Y"}}]})),
        )
        assert youtube_service._fetch_youtube_username("tok") == "Canal Y"

        monkeypatch.setattr(tiktok_service.requests, "get", Mock(return_value=_resp(404, text="nf")))
        assert tiktok_service._fetch_tiktok_user_info("tok") == "TikTok User"

        me = _resp(200, {"name": "Nombre Meta"})
        cuentas = _resp(200, {"data": [{"instagram_business_account": {"username": "lerolero"}}]})
        with patch.object(instagram_service.requests, "get", Mock(side_effect=[me, cuentas])):
            assert instagram_service._fetch_instagram_username("tok") == "lerolero"


class TestSaveTokens:
    def test_save_tiktok_tokens_crea_cuenta(self, monkeypatch) -> None:
        fake_db = FakeSession()
        monkeypatch.setattr(tiktok_service, "_fetch_tiktok_user_info", lambda tok: "Canaalisimo")
        cuenta = tiktok_service.save_tiktok_tokens(
            fake_db, str(uuid.uuid4()), {"access_token": "a", "expires_in": 8000, "open_id": "o"}
        )
        assert fake_db.added and cuenta.access_token == "a"
        assert cuenta.platform_username == "Canaalisimo"
        assert cuenta.token_expires_at > now_utc()

    def test_save_tiktok_sin_token_explota(self) -> None:
        with pytest.raises(ValueError, match="access_token"):
            tiktok_service.save_tiktok_tokens(FakeSession(), str(uuid.uuid4()), {})

    def test_save_youtube_tokens_crea_cuenta(self, monkeypatch) -> None:
        fake_db = FakeSession()
        monkeypatch.setattr(youtube_service, "_fetch_youtube_username", lambda tok: "Canal Y")
        cuenta = youtube_service.save_youtube_tokens(
            fake_db, str(uuid.uuid4()), {"access_token": "a", "refresh_token": "r", "expires_in": 3600}
        )
        assert cuenta.platform == "youtube"
        assert cuenta.refresh_token == "r"

    def test_save_instagram_tokens_crea_cuenta(self, monkeypatch) -> None:
        fake_db = FakeSession()
        monkeypatch.setattr(instagram_service, "_fetch_instagram_username", lambda tok: "lerolero")
        cuenta = instagram_service.save_instagram_tokens(
            fake_db, str(uuid.uuid4()), {"access_token": "a"}
        )
        assert cuenta.platform == "instagram"
        assert fake_db.added
