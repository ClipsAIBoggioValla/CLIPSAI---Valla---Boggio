"""Cobertura de los stubs del paquete desacoplado `backend/` (tracks + security + handler).

Son módulos diseñados para funcionar sin FFmpeg ni keys: se testean con mocks
de subprocess/requests/sys.modules. Sin PostgreSQL ni red.
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

from backend.core.schemas import (
    AudioFeatures,
    AutopilotJob,
    RenderConfig,
    ScheduledPost,
    TranscriptData,
    ViralClipCandidate,
    WordToken,
)


def _transcript(n_words: int = 12, raw: str = "consulta") -> TranscriptData:
    words = [WordToken(word=f"w{i}", start=i * 0.5, end=i * 0.5 + 0.5) for i in range(n_words)]
    return TranscriptData(video_id="vid-1", language="es", words=words, raw_text=raw)


def _viral_report() -> dict[str, Any]:
    """El schema exige estas 5 claves en el reporte del candidato."""
    return {
        "clarity": 85,
        "emotional_trigger": "revelación",
        "hook_strength": 90,
        "trend_alignment": 80,
        "viral_reason": "giro inesperado que retiene",
    }


def _candidate(size_hint: float = 20.0) -> ViralClipCandidate:
    return ViralClipCandidate(
        clip_id="clip-1",
        start_time=0.0,
        end_time=size_hint,
        score=80,
        headline="Momento revelador",
        viral_report=_viral_report(),
    )


def _audio() -> AudioFeatures:
    return AudioFeatures(video_id="vid-1", duration_seconds=60.0, events=[], viral_moments=[])


# ---------------------------------------------------------------- schemas


class TestSchemas:
    def test_transcript_y_words(self) -> None:
        tr = _transcript()
        assert tr.words[1].word == "w1"

    def test_score_fuera_de_rango_rechazado(self) -> None:
        # el schema no clampea: score > 100 es ValidationError explícito
        with pytest.raises(Exception):
            ViralClipCandidate(
                clip_id="c", start_time=1, end_time=10, score=150,
                headline="titulo largo", viral_report=_viral_report(),
            )
        valido = ViralClipCandidate(
            clip_id="c", start_time=1, end_time=10, score=100,
            headline="otro titulo", viral_report=_viral_report(),
        )
        assert valido.score == 100

    def test_headline_minimo(self) -> None:
        with pytest.raises(Exception):
            ViralClipCandidate(clip_id="c", start_time=0, end_time=5, score=1, headline="x")

    def test_scheduled_post(self) -> None:
        post = ScheduledPost(
            clip_id="c1", platforms=["tiktok"], scheduled_at="2026-01-01", caption="hola"
        )
        assert post.platforms == ["tiktok"]

    def test_autopilot_job_default(self) -> None:
        job = AutopilotJob(job_id="j1", video_id="v1")
        assert job.status == "pending"
        assert job.candidates == []


# ---------------------------------------------------------------- interfaces


class TestInterfaces:
    def test_absractas_no_se_instatian(self) -> None:
        from backend.core.interfaces import ITranscriber, IViralityEngine

        with pytest.raises(TypeError):
            ITranscriber()
        with pytest.raises(TypeError):
            IViralityEngine()

    def test_fakes_cumplen_contrato(self) -> None:
        from backend.core.interfaces import IPublisher

        class Fake(IPublisher):
            async def publish(self, clip_path: str, post: ScheduledPost) -> dict:
                return {}

            async def schedule(self, post: ScheduledPost) -> str:
                return "ok"

        fake = Fake()
        assert isinstance(fake, IPublisher)


# ---------------------------------------------------------------- ssrf_guard


class TestSSRFGuard:
    _DNS_PUBLICA = [((2, 1, 0, "", ("8.8.8.8", 0)))]  # getaddrinfo -> ip pública

    def test_url_publica_valida(self, monkeypatch) -> None:
        from unittest.mock import patch as _patch

        from backend.core.security import ssrf_guard as sg

        # Sin red real: resolviendo a una IP pública el hostname es válido.
        with _patch.object(sg.socket, "getaddrinfo", lambda *a, **k: self._DNS_PUBLICA):
            assert (
                sg.validate_url("https://media.example.com/video.mp4")
                == "https://media.example.com/video.mp4"
            )

    def test_scheme_invalido(self) -> None:
        from backend.core.security import ssrf_guard as sg

        with pytest.raises(sg.SSRFError, match="Scheme not allowed"):
            sg.validate_url("ftp://media.example.com/x")

    def test_hostname_bloqueado(self) -> None:
        from backend.core.security import ssrf_guard as sg

        with pytest.raises(sg.SSRFError):
            sg.validate_url("http://localhost/video.mp4")
        with pytest.raises(sg.SSRFError):
            sg.validate_url("http://metadata.google.internal/")

    def test_ip_de_metadatos_bloqueada(self) -> None:
        from backend.core.security import ssrf_guard as sg

        with pytest.raises(sg.SSRFError):
            sg.validate_url("http://169.254.169.254/latest/meta-data/")

    def test_dns_fallido(self, monkeypatch) -> None:
        import socket

        from backend.core.security import ssrf_guard as sg

        calls = Mock(side_effect=socket.gaierror("dns"))
        monkeypatch.setattr(sg.socket, "getaddrinfo", calls)
        with pytest.raises(sg.SSRFError, match="DNS resolution failed"):
            sg.validate_url("https://media.example.com/x")

    def test_hostname_con_ip_privada_resuelta(self, monkeypatch) -> None:
        from backend.core.security import ssrf_guard as sg

        infos = [(2, 1, 0, "", ("10.0.0.5", 0))]
        monkeypatch.setattr(sg.socket, "getaddrinfo", lambda *a, **k: infos)
        with pytest.raises(sg.SSRFError, match="Resolved IP blocked"):
            sg.validate_url("https://media.example.com/x")

    def test_assert_safe_url_delega(self, monkeypatch) -> None:
        from unittest.mock import patch as _patch

        from backend.core.security import ssrf_guard as sg

        with _patch.object(sg.socket, "getaddrinfo", lambda *a, **k: self._DNS_PUBLICA):
            assert sg.assert_safe_url("https://media.example.com/x") is None


# ---------------------------------------------------------------- rate_limiter


class TestRateLimiter:
    def test_excede_y_libera_ventana(self, monkeypatch) -> None:
        import time

        from backend.core.security.rate_limiter import RateLimiter

        reloj = [1000.0]
        monkeypatch.setattr(time, "time", lambda: reloj[0])

        limiter = RateLimiter(max_requests=2, window_seconds=10)
        limiter.check("k")
        limiter.check("k")
        with pytest.raises(Exception):
            limiter.check("k")  # excedido dentro de la ventana

        reloj[0] += 20
        limiter.check("k")  # ventana expirada -> no levanta

    def test_quota_diaria(self, monkeypatch) -> None:
        from backend.core.security.rate_limiter import MinutesQuota, QuotaExceeded

        quota = MinutesQuota(max_minutes_per_day=10)
        quota.consume("user", 9.0)
        with pytest.raises(QuotaExceeded):
            quota.consume("user", 2.0)
        assert quota.remaining("user") == pytest.approx(1.0)


# ---------------------------------------------------------------- storage_guard


class TestStorageGuard:
    def test_roundtrip_presign(self, monkeypatch) -> None:
        from backend.core.security.storage_guard import generate_presigned_url, verify_presigned_url

        monkeypatch.setenv("STORAGE_SIGN_KEY", "clave-de-test-fija-32bytes-0000000000")
        url = generate_presigned_url("vid/clips/a.mp4", expires_in=3600)
        assert "expires=" in url and "sig=" in url
        assert verify_presigned_url(url, "vid/clips/a.mp4") is True
        assert verify_presigned_url(url, "vid/clips/otro.mp4") is False

    def test_url_firmada_expirada(self, monkeypatch) -> None:
        from backend.core.security.storage_guard import generate_presigned_url, verify_presigned_url

        monkeypatch.setenv("STORAGE_SIGN_KEY", "clave-de-test-fija-32bytes-0000000000")
        url = generate_presigned_url("key/a.mp4", expires_in=-1)
        assert verify_presigned_url(url, "key/a.mp4") is False

    def test_url_invalida_es_falsa(self, monkeypatch) -> None:
        from backend.core.security.storage_guard import verify_presigned_url

        monkeypatch.setenv("STORAGE_SIGN_KEY", "clave-de-test-fija-32bytes-0000000000")
        assert verify_presigned_url("https://x/?sig=truchas&expires=123", "key/a.mp4") is False


# ---------------------------------------------------------------- vault


class TestVault:
    def test_roundtrip_aes_con_clave_fija(self) -> None:
        from backend.core.security.vault import decrypt_token, encrypt_token

        clave = b"\x00" * 32
        token = encrypt_token("access-token-secreto", key=clave)
        assert decrypt_token(token, key=clave) == "access-token-secreto"

    def test_fallback_sin_crypto_is_determinista(self, monkeypatch) -> None:
        from backend.core.security import vault

        monkeypatch.setattr(vault, "_HAS_CRYPTO", False)  # camino fallback (sin AESGCM)
        fallback = base64.b64encode(b"vault:plano").decode()
        assert vault.decrypt_token(fallback) == "plano"
        cifrado = vault.encrypt_token("otro")
        assert vault.decrypt_token(cifrado) == "otro"


# ---------------------------------------------------------------- core schemas consumers (tracks)


class TestTrackA:
    def test_stt_transcribe_con_mock_e_incluye_seed(self, monkeypatch) -> None:
        from backend.track_a.transcription import stt as stt_module

        fake_words = [{"word": "uno", "start": 0.0, "end": 0.4}, {"word": "dos", "start": 0.4, "end": 0.8}]

        class FakeLegacy:
            async def transcribir_video(self, path: str) -> list[dict]:
                return fake_words

        legacy = types.ModuleType("whisper_transcriber")
        legacy.transcribir_video = FakeLegacy().transcribir_video
        with patch.dict(sys.modules, {"whisper_transcriber": legacy}):
            transcript = asyncio.run(stt_module.WhisperTranscriber().transcribe("/x/v.mp4", "es"))
        assert transcript.video_id == "stub"
        assert [w.word for w in transcript.words] == ["uno", "dos"]

    def test_stt_seed_si_legacy_falla(self, monkeypatch) -> None:
        from backend.track_a.transcription import stt as stt_module

        legacy = types.ModuleType("whisper_transcriber")
        async def rompida(_path):
            raise RuntimeError("sin modelo")

        legacy.transcribir_video = rompida
        with patch.dict(sys.modules, {"whisper_transcriber": legacy}):
            transcript = asyncio.run(stt_module.WhisperTranscriber().transcribe("/x/v.mp4"))
        assert transcript.words[0].word == "hola"

    def test_analyzer_con_modulo_mock(self, monkeypatch) -> None:
        from backend.track_a.audio import analyzer as analyzer_module

        legacy = types.ModuleType("audio_analyzer")
        legacy.analizar_audio = Mock(return_value=[{"tipo": "grito", "momento": 3.0}])
        with patch.dict(sys.modules, {"audio_analyzer": legacy}):
            features = asyncio.run(analyzer_module.AudioAnalyzer().analyze("/x/v.mp4", "vid-9"))
        assert features.video_id == "vid-9"
        assert features.events == [{"tipo": "grito", "momento": 3.0}]

    def test_ingestion_validacion_y_move(self, tmp_path) -> None:
        from backend.track_a.ingestion.service import IngestionService

        origen = tmp_path / "clip.mp4"
        origen.write_bytes(b"video")
        transcript = tmp_path / "subs.txt"
        transcript.write_text("0:00 hola", encoding="utf-8")

        svc = IngestionService(upload_dir=str(tmp_path / "uploads"))
        video_id = asyncio.run(svc.ingest(str(origen), "clip.mp4", str(transcript)))
        assert len(video_id) == 36  # uuid4
        assert (tmp_path / "uploads" / f"{video_id}.mp4").exists()

    def test_ingestion_400_extensiones_malas(self, tmp_path) -> None:
        from backend.track_a.ingestion.service import IngestionService

        svc = IngestionService(upload_dir=str(tmp_path / "uploads"))
        with pytest.raises(ValueError, match="video"):
            asyncio.run(svc.ingest(str(tmp_path / "x.exe"), "x.exe"))
        # transcript invalido
        vid_ok = tmp_path / "clip2.mp4"
        vid_ok.write_bytes(b"v")
        transcript_mal = tmp_path / "subs.bin"
        transcript_mal.write_bytes(b"1")
        with pytest.raises(ValueError, match="transcript"):
            asyncio.run(svc.ingest(str(vid_ok), "clip2.mp4", str(transcript_mal)))

    def test_ingestion_video_excede_max(self, tmp_path, monkeypatch) -> None:
        from backend.track_a.ingestion import service as ingestion_service

        monkeypatch.setattr(ingestion_service, "MAX_BYTES", 8)
        svc = ingestion_service.IngestionService(upload_dir=str(tmp_path / "uploads"))
        grande = tmp_path / "grande.mp4"
        grande.write_bytes(b"v" * 64)
        with pytest.raises(ValueError, match="500MB"):
            asyncio.run(svc.ingest(str(grande), "grande.mp4"))


class TestTrackB:
    def test_ffmpeg_renderer_es_identidad_diferida(self) -> None:
        from backend.track_b.rendering.ffmpeg import FFmpegRenderer

        out = "storage/renders/salida.mp4"
        assert asyncio.run(FFmpegRenderer().render("/v.mp4", _candidate(), _transcript(), RenderConfig(), out)) == out

    def test_mock_publisher_publishers_y_schedule(self) -> None:
        from backend.track_b.publishing.scheduler import MockPublisher

        pub = MockPublisher()
        post = ScheduledPost(clip_id="c9", platforms=["tiktok", "youtube"], scheduled_at="2026-01-01T00:00:00", caption="hi")
        resultado = asyncio.run(pub.publish("/tmp/clip.mp4", post))
        assert resultado["status"] == "published"
        assert set(resultado["platforms"]) == {"tiktok", "youtube"}
        assert "scheduled:c9:2026-01-01T00:00:00" in asyncio.run(pub.schedule(post))

    def test_words_to_ass_estilo_y_fallback(self, tmp_path) -> None:
        from backend.track_b.rendering.captions import STYLE_MAP, words_to_ass, write_ass

        transcripto = _transcript()
        contenido = words_to_ass(transcripto, style="karaoke_yellow")
        assert "[Script Info]" in contenido
        assert "Dialogue" in contenido and "w3" in contenido

        # estilo desconocido -> fallback silencioso al default
        fallback = words_to_ass(transcripto, style="estilo_inexistente")
        assert "w0" in fallback

        destino = tmp_path / "salida.ass"
        assert write_ass(transcripto, str(destino)) == str(destino)
        assert STYLE_MAP["minimal_white"] != STYLE_MAP["karaoke_yellow"]


# ---------------------------------------------------------------- services (wrappers)


class TestServicesWrappers:
    def test_loudnorm_filter_args(self) -> None:
        from backend.services.audio_processor.processor import loudnorm_filter_args

        args = asyncio.run(loudnorm_filter_args())
        assert args[0] == "-filter:a"
        assert args[1].startswith("loudnorm=I=-14.0:TP=-1.5:LRA=11.0")

    def test_normalize_audio_fallback_silencioso(self, monkeypatch) -> None:
        from backend.services.audio_processor import processor as proc
        from backend.track_a.audio import analyzer as analyzer_module

        class Reventado:
            async def analyze(self, *a: Any, **k: Any) -> AudioFeatures:
                raise RuntimeError("sin librosa")

        monkeypatch.setattr(analyzer_module, "AudioAnalyzer", Reventado)
        features = asyncio.run(proc.normalize_audio("/v.mp4", "vid-fallback"))
        assert features.video_id == "vid-fallback"
        assert features.duration_seconds == 0.0
        assert features.events == []

    def test_normalize_audio_via_analyzer_mock(self, monkeypatch) -> None:
        from backend.services.audio_processor import processor as proc
        from backend.track_a.audio import analyzer as analyzer_module

        esperado = AudioFeatures(video_id="vid-ok", duration_seconds=90.0, events=[{"x": 1}])

        class Bien:
            async def analyze(self, *a: Any, **k: Any) -> AudioFeatures:
                return esperado

        monkeypatch.setattr(analyzer_module, "AudioAnalyzer", Bien)
        features = asyncio.run(proc.normalize_audio("/v.mp4", "vid-ok"))
        assert features is esperado

    def test_transcribe_stub_servicios(self, monkeypatch) -> None:
        from backend.services.transcription import stt as stt_services

        class FakeWhisper:
            async def transcribe(self, path: str, language: str = "es"):
                return _transcript()

        monkeypatch.setattr(
            __import__("backend.track_a.transcription.stt", fromlist=["WhisperTranscriber"]),
            "WhisperTranscriber",
            FakeWhisper,
        )
        transcripto = asyncio.run(stt_services.transcribe_stub("/v.mp4", "vid-envuelto"))
        assert transcripto.video_id == "vid-envuelto"
        assert transcripto.language == "es"

    def test_ingest_upload_validaciones(self, tmp_path, monkeypatch) -> None:
        from backend.services.ingestion import service as services_ingestion

        with pytest.raises(ValueError, match="no soportada"):
            asyncio.run(services_ingestion.ingest_upload(str(tmp_path / "x.exe"), "x.exe"))

        monkeypatch.setattr(services_ingestion, "MAX_BYTES", 8)
        grande = tmp_path / "grande.mp4"
        grande.write_bytes(b"v" * 32)
        with pytest.raises(ValueError, match="excede 500MB"):
            asyncio.run(services_ingestion.ingest_upload(str(grande), "grande.mp4"))

    def test_ingest_upload_happy(self, tmp_path, monkeypatch) -> None:
        from backend.services.ingestion import service as services_ingestion

        upload_dir = tmp_path / "subidas"
        uploads = tmp_path / "origen"
        uploads.mkdir()
        video = uploads / "v.mp4"
        video.write_bytes(b"contenido")
        video_id = asyncio.run(
            services_ingestion.ingest_upload(str(video), "v.mp4", upload_dir=str(upload_dir))
        )
        assert len(video_id) == 36
        assert (upload_dir / f"{video_id}.mp4").exists()

    def test_ingest_ytdlp_propaga_ssrf_y_reporta_stub(self, monkeypatch) -> None:
        from backend.core.security.ssrf_guard import SSRFError
        from backend.services.ingestion import service as services_ingestion

        monkeypatch.setattr(services_ingestion, "validate_url", Mock(side_effect=SSRFError("blocked")))
        with pytest.raises(SSRFError):
            asyncio.run(services_ingestion.ingest_ytdlp("http://localhost/x"))

        # con URL ok pero yt_dlp no instalable -> RuntimeError descriptivo
        monkeypatch.setattr(services_ingestion, "validate_url", lambda u: u)
        with patch.dict(sys.modules, {"yt_dlp": None}):
            with pytest.raises(RuntimeError, match="yt-dlp no instalado"):
                asyncio.run(services_ingestion.ingest_ytdlp("https://youtu.be/abc"))

    def test_social_publisher_mock_scheduler(self) -> None:
        from backend.services.social_publish.publisher import MockPublisher, SocialScheduler

        scheduler = SocialScheduler(publisher=MockPublisher())
        post = ScheduledPost(clip_id="c1", platforms=["tiktok"], scheduled_at="2026-01-01T09:00", caption="cap")
        programado = asyncio.run(scheduler.schedule_post(post))
        assert programado is post
        assert scheduler.list_scheduled() == [post]
        assert scheduler.get_by_clip("c1") == [post]
        resultado = asyncio.run(scheduler.publish_now("/tmp/c1.mp4", post))
        assert resultado["status"] == "published"
        assert resultado["platforms"] == "tiktok"

    def test_captions_estilos_distintos(self, tmp_path) -> None:
        from backend.services.video_editor.captions import words_to_ass, write_ass

        transcripto = _transcript()
        amarillo = words_to_ass(transcripto, style="karaoke_yellow")
        minimal = wordos = words_to_ass(transcripto, style="minimal_white")
        assert amarillo != minimal
        assert write_ass(transcripto, str(tmp_path / "s.ass")) == str(tmp_path / "s.ass")


class TestRenderer:
    def _run_mock(self, module):
        def side_effect(cmd, **kwargs):
            last = Path(str(cmd[-1]))
            last.parent.mkdir(parents=True, exist_ok=True)
            last.write_bytes(b"mp4")
            return Mock(returncode=0, stdout=b"", stderr=b"")

        return patch.object(module.subprocess, "run", Mock(side_effect=side_effect))

    def test_render_happy(self, tmp_path) -> None:
        from backend.services.video_editor import renderer

        config = RenderConfig()
        with self._run_mock(renderer):
            out = asyncio.run(
                renderer.render_clip(
                    str(tmp_path / "inexistente.mp4"),
                    _candidate(20.0),
                    config,
                    _transcript(),
                    output_dir=str(tmp_path / "renders"),
                )
            )
        assert out.endswith("clip-1.mp4")

    def test_render_validaciones(self) -> None:
        from backend.services.video_editor import renderer

        config = RenderConfig()

        with pytest.raises(ValueError, match="debe ser > start_time"):
            asyncio.run(renderer.render_clip(None, _candidate(0.0), config))

        with pytest.raises(ValueError, match="fuera de rango 5-90s"):
            asyncio.run(renderer.render_clip(None, _candidate(120.0), config))

    def test_render_fm_fm_fails_propagan_runtime(self) -> None:
        import subprocess as subprocess_real

        from backend.services.video_editor import renderer

        # CalledProcessError sí se convierte en RuntimeError con diagnóstico
        error = subprocess_real.CalledProcessError(returncode=2, cmd="cmd")
        with patch.object(renderer.subprocess, "run", Mock(side_effect=error)):
            with pytest.raises(RuntimeError, match="FFmpeg render"):
                asyncio.run(
                    renderer.render_clip(
                        str(Path("storage/clips/otro.mp4")),
                        _candidate(20.0),
                        RenderConfig(),
                        _transcript(),
                    )
                )

    def test_render_clip_legacy_delega(self) -> None:
        from backend.services.video_editor import renderer

        with self._run_mock(renderer):
            out = asyncio.run(
                renderer.render_clip_legacy(
                    str(Path("storage/clips/otro.mp4")),
                    _candidate(20.0),
                    RenderConfig(),
                )
            )
        assert out.endswith("clip-1.mp4")


# ---------------------------------------------------------------- analizador viral + engine LLM


def _main_module(value: Any) -> types.ModuleType:
    mod = types.ModuleType("main")
    mod.obtener_clips_ia = value if callable(value) else Mock(return_value=value)
    return mod


class TestAiViralAnalyzer:
    def test_mock_candidatos_requiere_palabras(self) -> None:
        from backend.services.ai_viral.analyzer import _mock_candidates_from_transcript

        assert _mock_candidates_from_transcript(_transcript(5)) == []

    def test_mock_candidatos_tres_fijos(self) -> None:
        from backend.services.ai_viral.analyzer import _mock_candidates_from_transcript

        candidatos = _mock_candidates_from_transcript(_transcript(12))
        assert [c.score for c in candidatos] == [92, 88, 85]
        assert len({c.clip_id for c in candidatos}) == 3  # ids únicos por seed

    def test_ts_to_seconds_valido(self) -> None:
        from backend.services.ai_viral.analyzer import _ts_to_seconds

        assert _ts_to_seconds("00:01:05") == pytest.approx(65.0)
        assert _ts_to_seconds("no-es-tiempo") == 0.0

    def test_analyze_con_main_mock(self, monkeypatch) -> None:
        from backend.services.ai_viral import analyzer

        raw = [
            {"inicio": "00:00:10", "fin": "00:00:35", "score": 9, "titulo_sugerido": "Revela", "criterio_principal": "revelación"}
        ]
        with patch.dict(sys.modules, {"main": _main_module(raw)}):
            candidatos = asyncio.run(analyzer.analyze_transcript(_transcript()))
        assert len(candidatos) == 1
        assert candidatos[0].score == 90  # 9 * 10

    def test_analyze_propaga_cuando_main_no_devuelve_nada(self, monkeypatch) -> None:
        from backend.services.ai_viral import analyzer

        with patch.dict(sys.modules, {"main": _main_module([])}):
            with pytest.raises(RuntimeError, match="no retornó candidatos"):
                asyncio.run(analyzer.analyze_transcript(_transcript()))

    def test_map_llm_descarta_items_malos(self) -> None:
        from backend.services.ai_viral.analyzer import _map_llm_to_candidates

        raw = [
            {"inicio": "00:00:00", "fin": "00:00:20", "score": "8.5", "titulo_sugerido": "Bien"},
            {"inicio": "basura"},  # descartado en silencio
        ]
        candos = _map_llm_to_candidates(raw)
        assert len(candos) == 1
        # "8.5" no es score entero: el mapa cae al default 70
        assert candos[0].score == 70


class TestViralityEngine:
    def test_score_con_ap_llm_ok(self, monkeypatch) -> None:
        from backend.track_b.virality.engine import ViralityEngine

        raw = [
            {
                "inicio": "00:00:05",
                "fin": "00:00:25",
                "score": 88,
                "titulo_sugerido": "Unga",
                "criterio_principal": "dato",
                "motivo": "bita",
            }
        ]
        with patch.dict(sys.modules, {"main": _main_module(raw)}):
            candidatos = asyncio.run(ViralityEngine().score(_transcript(), _audio()))
        assert len(candidatos) == 1
        assert candidatos[0].score == 88
        assert candidatos[0].headline == "Unga"

    def test_score_sin_candidatos_propaga(self, monkeypatch) -> None:
        from backend.track_b.virality.engine import ViralityEngine

        engine_module = types.ModuleType("main")
        engine_module.obtener_clips_ia = Mock(side_effect=RuntimeError("429"))
        with patch.dict(sys.modules, {"main": engine_module}):
            with pytest.raises(RuntimeError, match="obtener_clips_ia"):
                asyncio.run(ViralityEngine().score(_transcript(), _audio()))

    def test_generate_report_es_identidad(self, monkeypatch) -> None:
        from backend.track_b.virality.engine import ViralityEngine

        cand = _candidate()
        cand.viral_report = {"hook": "algo"}
        assert asyncio.run(ViralityEngine().generate_report(cand)) == {"hook": "algo"}

    def test_ts_to_seconds_extremo(self) -> None:
        from backend.track_b.virality.engine import _ts_to_seconds

        assert _ts_to_seconds("basura total") == 0.0


# ---------------------------------------------------------------- handler.py (ramas restantes)


class TestHandlerRbranches:
    def test_upload_r2_requiere_credenciales(self, monkeypatch) -> None:
        import backend.handler as handler

        # boto3 no está instalado en este entorno: lo simulo para llegar a la
        # validación de credenciales (rama real de producción).
        boto3_mod = types.ModuleType("boto3")
        boto3_mod.client = Mock()
        botocore_mod = types.ModuleType("botocore")
        config_mod = types.ModuleType("botocore.config")
        config_mod.Config = Mock(return_value="sig")
        botocore_mod.config = config_mod
        with (
            patch.dict(sys.modules, {"boto3": boto3_mod, "botocore": botocore_mod, "botocore.config": config_mod}),
            patch.dict(os.environ, {}, clear=False),
        ):
            monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
            monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
            monkeypatch.delenv("BUCKET_NAME", raising=False)
            monkeypatch.delenv("AWS_REGION", raising=False)
            monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
            with pytest.raises(RuntimeError, match="Faltan AWS"):
                handler._upload_to_r2("/tmp/x.mp4", "bucket", "key")

    def test_upload_r2_con_boto3_mock(self, monkeypatch) -> None:
        import backend.handler as handler

        s3 = Mock()
        boto3_mod = types.ModuleType("boto3")
        boto3_mod.client = Mock(return_value=s3)
        config_mod = types.ModuleType("botocore.config")
        config_mod.Config = Mock(return_value="sig")
        botocore_mod = types.ModuleType("botocore")
        botocore_mod.config = config_mod
        with (
            patch.dict(sys.modules, {"boto3": boto3_mod, "botocore": botocore_mod, "botocore.config": config_mod}),
            patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "k", "AWS_SECRET_ACCESS_KEY": "s"}),
        ):
            url = handler._upload_to_r2("/tmp/archivo.mp4", "bucket-ei", "clips/x.mp4")
        assert url.startswith("https://videos.clipsai.xyz/clips/x.mp4")
        s3.upload_file.assert_called_once()

    def test_download_file_respeta_content_length(self, tmp_path, monkeypatch) -> None:
        import requests as requests_real

        import backend.handler as handler

        destino = tmp_path / "video.mp4"
        response = Mock()
        response.headers = {"Content-Length": str(600 * 1024 * 1024)}
        response.iter_content = Mock(return_value=iter([]))
        ctx = Mock()
        ctx.__enter__ = Mock(return_value=response)
        ctx.__exit__ = Mock(return_value=False)
        with patch.dict(sys.modules, {"requests": requests_real}), patch.object(
            handler.requests, "get", return_value=ctx
        ):
            with pytest.raises(ValueError, match="maximo permitido"):
                handler._download_file("https://x/y.mp4", destino, handler.MAX_VIDEO_BYTES)

    def test_download_file_exige_bytes(self, tmp_path, monkeypatch) -> None:
        import backend.handler as handler

        destino = tmp_path / "vacio.mp4"
        response = Mock()
        response.headers = {}
        response.iter_content = Mock(return_value=iter([]))
        ctx = Mock()
        ctx.__enter__ = Mock(return_value=response)
        ctx.__exit__ = Mock(return_value=False)
        with patch.object(handler.requests, "get", return_value=ctx):
            with pytest.raises(ValueError, match="vacio"):
                handler._download_file("https://x/y.mp4", destino, handler.MAX_VIDEO_BYTES)

    def test_get_extension_valida(self) -> None:
        import backend.handler as handler

        assert handler._get_extension("https://x/v.mp4?h=1", handler.VIDEO_EXTENSIONS, ".mp4") == ".mp4"
        with pytest.raises(ValueError, match="Extension no soportada"):
            handler._get_extension("https://x/v.webm", {"mp4"}, None)

    def test_job_payload_invalido(self) -> None:
        from backend.handler import process_video_job

        with pytest.raises(ValueError, match="debe ser un objeto JSON"):
            process_video_job(None)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="job"):
            process_video_job({"input": "no-dict"})

    def test_transcription_url_invalida(self) -> None:
        from backend.handler import process_video_job

        with pytest.raises(ValueError, match="transcription_url"):
            process_video_job({"input": {"video_url": "https://x/v.mp4", "transcription_url": ""}})

    def test_transcription_texto_supera_maximo(self, monkeypatch) -> None:
        import backend.handler as handler
        from backend.handler import process_video_job

        monkeypatch.setattr(handler, "MAX_TRANSCRIPT_BYTES", 16)
        with pytest.raises(ValueError, match="supera el maximo"):
            process_video_job(
                {"input": {"video_url": "https://x/v.mp4", "transcription_text": "x" * 100}}
            )

    def test_vertical_fallida_registra_mensaje(self) -> None:
        import backend.handler as handler
        from backend.handler import process_video_job

        with tempfile.TemporaryDirectory() as directory:
            horizontal = Path(directory) / "c.mp4"
            horizontal.write_bytes(b"h")

            clip = SimpleNamespace(
                inicio="00:00:10", fin="00:00:40", archivo=str(horizontal),
                titulo_sugerido="t", hook_texto="h", score=8,
                criterio_principal="c", primer_segundo="", motivo="",
            )
            resultado = SimpleNamespace(
                exito=True, clips=[clip], carpeta_salida=directory,
                transcription_segments=[{"start": 0, "end": 1, "text": "t"}],
                error=None, error_tipo=None, error_detalle=None,
            )
            engine = types.ModuleType("engine")
            engine.procesar_video = Mock(return_value=resultado)
            videoprocessor = types.ModuleType("video_processor")
            videoprocessor.process_clip_vertical = Mock(return_value=False)

            def fake_download(_u, dest, _m):
                dest.write_bytes(b"d")

            with (
                patch.dict(sys.modules, {"engine": engine, "video_processor": videoprocessor}),
                patch.object(handler, "_download_file", side_effect=fake_download),
            ):
                salida = process_video_job(
                    {"input": {"video_url": "https://x/v.mp4", "transcription_text": "hola", "video_id": "v-8"}}
                )
        assert salida["status"] == "COMPLETED"
        assert salida["clip_count"] == 0
        assert "logs" in salida["message"]

    def test_upload_r2_raises_continua(self) -> None:
        import backend.handler as handler
        from backend.handler import process_video_job

        with tempfile.TemporaryDirectory() as directory:
            horizontal = Path(directory) / "z.mp4"
            horizontal.write_bytes(b"h")

            clip = SimpleNamespace(
                inicio="00:00:00", fin="00:00:25", archivo=str(horizontal),
                titulo_sugerido="t2", hook_texto="", score=7,
                criterio_principal="", primer_segundo="", motivo="",
            )
            resultado = SimpleNamespace(
                exito=True, clips=[clip], carpeta_salida=directory,
                transcription_segments=[], error=None, error_tipo=None, error_detalle=None,
            )
            engine = types.ModuleType("engine")
            engine.procesar_video = Mock(return_value=resultado)
            videoprocessor = types.ModuleType("video_processor")

            def fake_vertical(**kwargs):
                Path(kwargs["output_video"]).write_bytes(b"v")
                return True

            videoprocessor.process_clip_vertical = Mock(side_effect=fake_vertical)

            def fake_download(_u, dest, _m):
                dest.write_bytes(b"d")

            with (
                patch.dict(sys.modules, {"engine": engine, "video_processor": videoprocessor}),
                patch.object(handler, "_download_file", side_effect=fake_download),
                patch.object(handler, "_upload_to_r2", side_effect=RuntimeError("boom")),
            ):
                salida = process_video_job(
                    {"input": {"video_url": "https://x/z.mp4", "transcription_text": "hola", "video_id": "v-9"}}
                )
        assert salida["status"] == "COMPLETED"
        assert salida["clip_count"] == 0
