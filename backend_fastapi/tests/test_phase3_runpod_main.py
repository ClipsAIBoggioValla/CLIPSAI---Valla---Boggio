"""Fase 3 de cobertura: `services/runpod_service.py` (polling/normalización) y
`app/main.py` (lifespan, middleware OPTIONS y helpers de CORS).

Sin red real: `requests` y boto3 mockeados. El lifespan corre una sola vez en
modo DB-less (`DATABASE_URL` vacío, ver `conftest.py`) con `cleanup_storage`
mockeado.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests

from _fixtures import FakeSession

from backend_fastapi.app.services import runpod_service as rs
from backend_fastapi.app.services.runpod_service import (
    RunPodError,
    _decode_response,
    _normalize_transcription_segments,
    _raise_for_job_failure,
    _settings,
    is_runpod_configured,
    process_local_video_via_runpod,
    process_video_via_runpod,
)

_SIZE = SimpleNamespace  # alias corto para stat() falsos


def _env_runpod(monkeypatch: Any, **extra: str) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "clave-test")
    monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "endp-123")
    monkeypatch.setenv("RUNPOD_POLL_INTERVAL_SECONDS", "0.01")
    for key, value in extra.items():
        monkeypatch.setenv(key, value)


def _resp(status: int = 200, payload: dict | None = None, text: str = "") -> Mock:
    mock = Mock(spec=requests.Response)
    mock.status_code = status
    if payload is not None:
        mock.json = Mock(return_value=payload)
        mock.text = str(payload) if not text else text
    else:
        mock.json = Mock(side_effect=ValueError("no json"))
        mock.text = text
    return mock


def _fake_boto3(upload_error: Exception | None = None) -> Any:
    client = Mock()
    if upload_error is not None:
        client.upload_file = Mock(side_effect=upload_error)
    else:
        client.upload_file = Mock()
    client.generate_presigned_url = Mock(return_value="https://r2/videos.mp4")
    mod = types.ModuleType("boto3")
    mod.client = Mock(return_value=client)
    mod._client = client
    return mod


def _fake_botocore() -> Any:
    botocore = types.ModuleType("botocore")
    config_mod = types.ModuleType("botocore.config")
    config_mod.Config = Mock()
    botocore.config = config_mod
    sys.modules.setdefault("botocore", botocore)
    sys.modules.setdefault("botocore.config", config_mod)
    return botocore


# ------------------------------------------------------------------ _settings


class TestSettings:
    def test_sin_api_key(self, monkeypatch) -> None:
        monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
        monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "e1")
        with pytest.raises(RunPodError, match="RUNPOD_API_KEY"):
            _settings()

    def test_sin_endpoint_id(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_API_KEY", "k")
        monkeypatch.delenv("RUNPOD_ENDPOINT_ID", raising=False)
        with pytest.raises(RunPodError, match="RUNPOD_ENDPOINT_ID"):
            _settings()

    def test_timeout_no_numerico(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        monkeypatch.setenv("RUNPOD_REQUEST_TIMEOUT_SECONDS", "abc")
        with pytest.raises(RunPodError, match="timeouts"):
            _settings()

    def test_timeout_no_positivo(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS", "0")
        with pytest.raises(RunPodError, match="mayores que cero"):
            _settings()

    def test_ok_con_endpoint_explicito_y_base_url(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        monkeypatch.setenv("RUNPOD_API_BASE_URL", "https://api.runpod.ai/v2/")
        api_key, eid, req_t, total_t, poll, base = _settings("otro-endpoint")
        assert eid == "otro-endpoint"
        assert base == "https://api.runpod.ai/v2"
        assert req_t == 95 and total_t == 1800 and poll > 0

    def test_is_runpod_configured(self, monkeypatch) -> None:
        monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
        monkeypatch.delenv("RUNPOD_ENDPOINT_ID", raising=False)
        assert is_runpod_configured() is False
        monkeypatch.setenv("RUNPOD_API_KEY", "k")
        monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "e")
        assert is_runpod_configured() is True


# ------------------------------------------------------- normalize segments


class TestNormalizeSegments:
    def test_no_lista(self) -> None:
        assert _normalize_transcription_segments("no-soy-lista") == []

    def test_items_no_dict_y_sin_texto(self) -> None:
        res = _normalize_transcription_segments([42, None, {"start": 0, "end": 1}, {"text": "  "}])
        assert res == []

    def test_formato_nuevo_valido(self) -> None:
        res = _normalize_transcription_segments([{"start": 1.234, "end": 4.567, "text": "hola"}])
        assert res == [{"start": 1.23, "end": 4.57, "text": "hola"}]

    def test_formato_nuevo_invalido(self) -> None:
        # end <= start, tiempos no numéricos y tiempos negativos
        res = _normalize_transcription_segments(
            [
                {"start": 5, "end": 2, "text": "x"},
                {"start": "a", "end": 3, "text": "y"},
                {"start": -1, "end": 3, "text": "z"},
            ]
        )
        assert res == []

    def test_formato_timestamp_dos_partes(self) -> None:
        res = _normalize_transcription_segments(
            [
                {"timestamp": "1:05", "text": "primero"},
                {"timestamp": "1:10", "text": "segundo"},
            ]
        )
        assert res[0] == {"start": 65.0, "end": 70.0, "text": "primero"}
        assert res[1]["start"] == 70.0

    def test_formato_timestamp_tres_partes(self) -> None:
        res = _normalize_transcription_segments([{"timestamp": "0:01:05", "text": "hora"}])
        assert res[0]["start"] == pytest.approx(65.0)

    def test_formato_timestamp_unico_numero(self) -> None:
        res = _normalize_transcription_segments([{"timestamp": "12", "text": "crudo"}])
        assert res[0]["start"] == 12.0
        assert res[0]["end"] == 15.0

    def test_formato_timestamp_negativo_y_basura(self) -> None:
        res = _normalize_transcription_segments(
            [
                {"timestamp": "-1:00", "text": "negativo"},
                {"timestamp": "z:z", "text": "basura"},
            ]
        )
        assert res == []

    def test_formato_timestamp_fin_estimado_3s(self) -> None:
        res = _normalize_transcription_segments([{"timestamp": "0:30", "text": "final"}])
        assert res[0] == {"start": 30.0, "end": 33.0, "text": "final"}

    def test_next_segment_sin_timestamp(self) -> None:
        res = _normalize_transcription_segments(
            [
                {"timestamp": "0:10", "text": "a"},
                {"text": "sin timestamp"},
            ]
        )
        assert res[0]["end"] == 13.0

    def test_next_segment_timestamp_invalido(self) -> None:
        res = _normalize_transcription_segments(
            [
                {"timestamp": "0:10", "text": "a"},
                {"timestamp": "n:n", "text": "b"},
            ]
        )
        assert res[0]["end"] == 13.0


# ----------------------------------------------------------------- decodificar


class TestDecodeAndFailure:
    def test_decode_json_invalido(self) -> None:
        resp = _resp(200, None, text="<html>error</html>")
        with pytest.raises(RunPodError, match="no es JSON"):
            _decode_response(resp)

    def test_decode_json_no_dict(self) -> None:
        resp = _resp(200)
        resp.json = Mock(return_value=[1, 2])
        with pytest.raises(RunPodError, match="JSON inesperada"):
            _decode_response(resp)

    def test_job_failure_estados(self) -> None:
        for estado in ("FAILED", "CANCELLED", "TIMED_OUT"):
            with pytest.raises(RunPodError, match=estado):
                _raise_for_job_failure({"status": estado, "error": "detalle"})
        # sin status problemático no levanta
        assert _raise_for_job_failure({"status": "COMPLETED"}) is None


# --------------------------------------------------------- runsync + polling


class TestProcessVideoViaRunpod:
    def test_video_url_vacio(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with pytest.raises(ValueError, match="video_url"):
            process_video_via_runpod("   ")

    def test_transcripcion_doble_fuente(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with pytest.raises(ValueError, match="no ambos"):
            process_video_via_runpod(
                "https://v.mp4", transcription_url="https://t.txt", transcription_text="hola"
            )

    def test_exitoso_con_url_y_video_id(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        post = Mock(return_value=_resp(200, {"status": "COMPLETED", "id": "j1", "output": {"clips": []}}))
        with patch.object(rs.requests, "post", post):
            out = process_video_via_runpod(
                "https://v.mp4", transcription_url="https://t.txt", video_id="v-1"
            )
        assert out["clips"] == []
        assert out["transcription_segments"] == []  # normalización aplicada
        body = post.call_args.kwargs["json"]["input"]
        assert body["transcription_url"] == "https://t.txt"
        assert body["video_id"] == "v-1"

    def test_output_no_dict(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with patch.object(
            rs.requests,
            "post",
            Mock(return_value=_resp(200, {"status": "SUCCEEDED", "id": "j1", "output": "texto"})),
        ):
            out = process_video_via_runpod("https://v.mp4")
        assert out["status"] == "SUCCEEDED"

    def test_post_timeout(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with patch.object(rs.requests, "post", Mock(side_effect=requests.Timeout("t"))):
            with pytest.raises(RunPodError, match="Timeout esperando"):
                process_video_via_runpod("https://v.mp4")

    def test_post_request_exception(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with patch.object(rs.requests, "post", Mock(side_effect=requests.ConnectionError("c"))):
            with pytest.raises(RunPodError, match="No se pudo llamar"):
                process_video_via_runpod("https://v.mp4")

    def test_respuesta_inicial_fallida(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with patch.object(
            rs.requests, "post", Mock(return_value=_resp(200, {"status": "FAILED", "error": "GPU"}))
        ):
            with pytest.raises(RunPodError, match="FAILED"):
                process_video_via_runpod("https://v.mp4")

    def test_in_progress_sin_job_id(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with patch.object(
            rs.requests, "post", Mock(return_value=_resp(200, {"status": "IN_PROGRESS"}))
        ):
            with pytest.raises(RunPodError, match="sin salida ni job id"):
                process_video_via_runpod("https://v.mp4")

    def test_polling_completa(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        post = Mock(return_value=_resp(200, {"status": "IN_PROGRESS", "id": "j9"}))
        get = Mock(
            side_effect=[
                _resp(200, {"status": "IN_PROGRESS", "id": "j9"}),
                _resp(
                    200,
                    {
                        "status": "COMPLETED",
                        "id": "j9",
                        "output": {
                            "clips": [],
                            "transcription_segments": [{"timestamp": "0:05", "text": "poll"}],
                        },
                    },
                ),
            ]
        )
        with patch.object(rs.requests, "post", post), patch.object(rs.requests, "get", get):
            out = process_video_via_runpod("https://v.mp4")
        assert out["clips"] == []
        # segmentos en formato timestamp quedaron normalizados
        assert out["transcription_segments"][0]["start"] == 5.0

    def test_polling_get_timeout(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with (
            patch.object(rs.requests, "post", Mock(return_value=_resp(200, {"status": "IN_PROGRESS", "id": "j2"}))),
            patch.object(rs.requests, "get", Mock(side_effect=requests.Timeout("t"))),
        ):
            with pytest.raises(RunPodError, match="Timeout consultando el job RunPod j2"):
                process_video_via_runpod("https://v.mp4")

    def test_polling_get_request_exception(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with (
            patch.object(rs.requests, "post", Mock(return_value=_resp(200, {"status": "IN_PROGRESS", "id": "j3"}))),
            patch.object(rs.requests, "get", Mock(side_effect=requests.ConnectionError("c"))),
        ):
            with pytest.raises(RunPodError, match="No se pudo consultar el job RunPod j3"):
                process_video_via_runpod("https://v.mp4")

    def test_polling_job_fallido(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with (
            patch.object(rs.requests, "post", Mock(return_value=_resp(200, {"status": "IN_PROGRESS", "id": "j4"}))),
            patch.object(rs.requests, "get", Mock(return_value=_resp(200, {"status": "TIMED_OUT", "error": "gpu"}))),
        ):
            with pytest.raises(RunPodError, match="TIMED_OUT"):
                process_video_via_runpod("https://v.mp4")

    def test_polling_se_agota_el_deadline(self, monkeypatch) -> None:
        _env_runpod(monkeypatch, RUNPOD_TIMEOUT_SECONDS="1")
        en_progreso = _resp(200, {"status": "IN_PROGRESS", "id": "j5"})
        with (
            patch.object(rs.requests, "post", Mock(return_value=en_progreso)),
            patch.object(rs.requests, "get", Mock(return_value=en_progreso)),
        ):
            with pytest.raises(RunPodError, match="no terminó en"):
                process_video_via_runpod("https://v.mp4")


# ------------------------------------------------------- video local → RunPod


class TestProcessLocalVideo:
    def test_video_inexistente(self, monkeypatch) -> None:
        _env_runpod(monkeypatch)
        with pytest.raises(RunPodError, match="inexistente o vacío"):
            process_local_video_via_runpod("no-existe.mp4")

    def test_video_vacio(self, monkeypatch, tmp_path: Path) -> None:
        _env_runpod(monkeypatch)
        vacio = tmp_path / "v.mp4"
        vacio.write_bytes(b"")
        with pytest.raises(RunPodError, match="inexistente o vacío"):
            process_local_video_via_runpod(vacio)

    def test_stat_oserror(self, monkeypatch, tmp_path: Path) -> None:
        _env_runpod(monkeypatch)
        fuente = tmp_path / "v.mp4"
        fuente.write_bytes(b"x")
        # en Python 3.14 `Path.is_file()` no pasa por `Path.stat()`: solo se consume
        # la llamada explícita a `source.stat()`.
        with patch("pathlib.Path.stat", side_effect=OSError("disco roto")):
            with pytest.raises(RunPodError, match="No se pudo leer el video fuente"):
                process_local_video_via_runpod(fuente)

    def test_transcripcion_demasiado_grande(self, monkeypatch, tmp_path: Path) -> None:
        _env_runpod(monkeypatch)
        fuente = tmp_path / "v.mp4"
        fuente.write_bytes(b"x")
        grande = tmp_path / "t.txt"
        grande.write_text("x" * 1024, encoding="utf-8")
        # llamadas: fuente.stat (ok) y luego grande.stat (demasiado grande)
        with patch(
            "pathlib.Path.stat",
            side_effect=[_SIZE(st_size=10), _SIZE(st_size=11 * 1024 * 1024)],
        ):
            with pytest.raises(RunPodError, match="10 MB"):
                process_local_video_via_runpod(fuente, transcription_path=grande)

    def test_transcripcion_se_lee_y_delega(self, monkeypatch, tmp_path: Path) -> None:
        _env_runpod(monkeypatch)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sk")
        fuente = tmp_path / "v.mp4"
        fuente.write_bytes(b"x")
        texto = tmp_path / "t.txt"
        texto.write_text("0:00 hola", encoding="utf-8")
        with (
            patch(
                "pathlib.Path.stat",
                side_effect=[_SIZE(st_size=10), _SIZE(st_size=9)],
            ),
            patch.dict(sys.modules, {"boto3": _fake_boto3(), "botocore": _fake_botocore()}),
            patch.object(rs, "process_video_via_runpod", Mock(return_value={"ok": True})) as delegado,
        ):
            res = process_local_video_via_runpod(fuente, transcription_path=texto, video_id="v1")
        assert res == {"ok": True}
        assert delegado.call_args.kwargs["transcription_text"] == "0:00 hola"
        assert delegado.call_args.kwargs["video_id"] == "v1"

    def test_boto3_ausente(self, monkeypatch, tmp_path: Path) -> None:
        _env_runpod(monkeypatch)
        fuente = tmp_path / "v.mp4"
        fuente.write_bytes(b"x")
        with patch.dict(sys.modules, {"boto3": None, "botocore": None}):
            with pytest.raises(RunPodError, match="boto3 no está instalado"):
                process_local_video_via_runpod(fuente)

    def test_faltan_aws_keys(self, monkeypatch, tmp_path: Path) -> None:
        _env_runpod(monkeypatch)
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        fuente = tmp_path / "v.mp4"
        fuente.write_bytes(b"x")
        with patch.dict(sys.modules, {"boto3": _fake_boto3(), "botocore": _fake_botocore()}):
            with pytest.raises(RunPodError, match="AWS_ACCESS_KEY_ID"):
                process_local_video_via_runpod(fuente)

    def test_upload_falla_envuelve_error(self, monkeypatch, tmp_path: Path) -> None:
        _env_runpod(monkeypatch)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sk")
        fuente = tmp_path / "v.mp4"
        fuente.write_bytes(b"x")
        fake = _fake_boto3(upload_error=RuntimeError("R2 caída"))
        with patch.dict(sys.modules, {"boto3": fake, "botocore": _fake_botocore()}):
            with pytest.raises(RunPodError, match="No se pudo subir/procesar"):
                process_local_video_via_runpod(fuente)
        # uploaded=False → no intenta borrar el objeto
        fake._client.delete_object.assert_not_called()

    def test_delegacion_falla_con_runpod_error_relanza_y_borra(self, monkeypatch, tmp_path: Path) -> None:
        _env_runpod(monkeypatch)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sk")
        fuente = tmp_path / "v.mp4"
        fuente.write_bytes(b"x")
        fake = _fake_boto3()
        with (
            patch.dict(sys.modules, {"boto3": fake, "botocore": _fake_botocore()}),
            patch.object(rs, "process_video_via_runpod", Mock(side_effect=RunPodError("job murió"))),
            pytest.raises(RunPodError, match="job murió"),
        ):
            process_local_video_via_runpod(fuente)
        # finally: el objeto temporal se borra de R2
        fake._client.delete_object.assert_called_once()

    def test_delete_en_finally_tolerante(self, monkeypatch, tmp_path: Path) -> None:
        _env_runpod(monkeypatch)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sk")
        fuente = tmp_path / "v.mp4"
        fuente.write_bytes(b"x")
        fake = _fake_boto3()
        fake._client.delete_object = Mock(side_effect=RuntimeError("delete roto"))
        with (
            patch.dict(sys.modules, {"boto3": fake, "botocore": _fake_botocore()}),
            patch.object(rs, "process_video_via_runpod", Mock(return_value={"ok": 1})),
        ):
            assert process_local_video_via_runpod(fuente) == {"ok": 1}


# ------------------------------------------------------------------- main.py


class TestMainApp:
    def test_lifespan_db_less_cleanup_y_options_middleware(self) -> None:
        """Un solo arranque con lifespan cubre migraciones salteadas + cleanup + log de rutas."""
        from fastapi.testclient import TestClient

        from backend_fastapi.app.deps import get_db
        from backend_fastapi.app.main import app as fastapi_app

        cleanup = Mock(return_value=5 * 1024 * 1024)
        with patch("backend_fastapi.app.services.storage_cleanup.cleanup_storage", cleanup):
            fastapi_app.dependency_overrides[get_db] = lambda: FakeSession()
            try:
                with TestClient(fastapi_app) as tc:
                    # OPTIONS con origen permitido por lista
                    r = tc.options("/health", headers={"Origin": "http://localhost:3000"})
                    assert r.status_code == 200
                    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
                    assert r.headers["access-control-allow-credentials"] == "true"
                    # OPTIONS con origen permitido por regex
                    r2 = tc.options("/health", headers={"Origin": "https://mi-app.vercel.app"})
                    assert r2.headers["access-control-allow-origin"] == "https://mi-app.vercel.app"
                    # OPTIONS con origen NO permitido → 200 sin ACAO
                    r3 = tc.options("/health", headers={"Origin": "https://malo.example.com"})
                    assert r3.status_code == 200
                    assert "access-control-allow-origin" not in r3.headers
                    # GET normal atraviesa el middleware (call_next)
                    r4 = tc.get("/health")
                    assert r4.status_code == 200 and r4.json() == {"status": "ok"}
            finally:
                fastapi_app.dependency_overrides.pop(get_db, None)
        cleanup.assert_called_once()

    def test_build_cors_origins_con_extras(self, monkeypatch) -> None:
        from backend_fastapi.app import main as main_mod

        monkeypatch.setenv("CORS_EXTRA_ORIGINS", "https://extra1.example.com, https://extra2.example.com/")
        origenes = main_mod._build_cors_origins()
        assert "https://extra1.example.com" in origenes
        assert "https://extra2.example.com" in origenes  # sin trailing slash
        assert origenes.count("https://extra1.example.com") == 1

    def test_origin_is_allowed_variantes(self) -> None:
        from backend_fastapi.app import main as main_mod

        assert main_mod._origin_is_allowed("") is False
        assert main_mod._origin_is_allowed("http://localhost:3000") is True
        assert main_mod._origin_is_allowed("https://algo.ngrok-free.dev") is True
        assert main_mod._origin_is_allowed("https://nope.example.com") is False

    def test_health_route(self, client) -> None:
        assert client.get("/health").json() == {"status": "ok"}
