"""Cobertura de la maquinaria pesada de `routers/jobs.py` (`_run_job` y helpers).

Misma convención que `test_routers_coverage.py`: FakeSession + mocks de
engine/Whisper/FFmpeg — ningún proceso real.

Comportamiento observado del wrapper: `except` global de `_run_job` NO
re-relanza (marca el job FAILED con mensaje descriptivo). La excepción de Claude
sí se re-lanza al wrapper.
"""

from __future__ import annotations

import asyncio
import uuid as uuid_lib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

import _fixtures
from _fixtures import FakeSession, make_job, make_video

from backend_fastapi.app.routers import jobs as jobs_router

ENGINE_PATH = "backend_fastapi.app.services.engine.run_clip_engine"


# ------------------------------------------------------------------ fixtures

def _video_tmp(tmp_path: Path, usuario: Any) -> Any:
    archivo = tmp_path / "source.mp4"
    archivo.write_bytes(b"video-falso-para-ffprobe")
    video = make_video(usuario.id)
    video.filepath = str(archivo)
    video.file_path = str(archivo)
    video.transcription_filepath = None
    video.transcript = "00:00:00 - Hola mundo\n00:00:05 - Mas texto"
    return video


def _job_con(video: Any) -> Any:
    return make_job(video.id, status="pending", progress=0)


def _clip_payload(**overrides: Any) -> dict:
    base = {
        "title": "Buena esquina",
        "inicio": 5.0,
        "fin": 25.0,
        "score": 9,
        "criterio_principal": "revelación",
        "hook_texto": "Nadie lo esperaba",
    }
    base.update(overrides)
    return base


def _ejecutar(fake_db: FakeSession, job: Any, engine: Mock) -> None:
    with (
        patch.object(jobs_router, "SessionLocal", lambda: fake_db),
        patch(ENGINE_PATH, engine),
    ):
        jobs_router._run_job(job.id)  # type: ignore[arg-type]


def _ejecutar_con_render(fake_db: FakeSession, job: Any, engine: Mock, render: Mock):
    with (
        patch.object(jobs_router, "SessionLocal", lambda: fake_db),
        patch(ENGINE_PATH, engine),
        patch.object(jobs_router, "_render_clip_with_ass_and_hook", render),
    ):
        jobs_router._run_job(job.id)  # type: ignore[arg-type]


# ------------------------------------------------------------------ helpers puros


class TestHelpersJobs:
    def test_resolve_storage_dir_respeta_env(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("STORAGE_CLIPS_DIR", str(tmp_path / "clips-env"))
        resuelto = jobs_router._resolve_storage_dir()
        assert resuelto.name == "clips-env"
        assert resuelto.is_dir()

    def test_meets_score_threshold_escalas(self) -> None:
        assert jobs_router._meets_score_threshold(None) is True
        assert jobs_router._meets_score_threshold(9) is True
        assert jobs_router._meets_score_threshold(2) is False        # escala 0-10
        assert jobs_router._meets_score_threshold(70) is True        # escala 0-100
        assert jobs_router._meets_score_threshold(30) is False
        assert jobs_router._meets_score_threshold(0.8) is True       # escala 0-1
        assert jobs_router._meets_score_threshold("texto-raro") is True

    def test_parse_time_to_seconds(self) -> None:
        assert jobs_router._parse_time_to_seconds(None) == 0.0
        assert jobs_router._parse_time_to_seconds(12.5) == pytest.approx(12.5)
        assert jobs_router._parse_time_to_seconds("00:01:10") == pytest.approx(70.0)
        assert jobs_router._parse_time_to_seconds("02:30") == pytest.approx(150.0)
        assert jobs_router._parse_time_to_seconds("15.5") == pytest.approx(15.5)
        assert jobs_router._parse_time_to_seconds("basura") == 0.0

    def test_titulo_largo_se_trunca(self) -> None:
        largo = "palabras " * 20
        resultado = jobs_router._extractmeaningful_title(largo)
        assert len(resultado) <= 60
        assert resultado.endswith(".")

    def test_segments_to_fallback_title(self) -> None:
        titulo = jobs_router._segments_to_fallback_title(
            [{"start": 0.0, "end": 10.0, "text": "esto es un momento revelador"}], 0.0, 10.0
        )
        assert titulo and len(titulo) <= 60
        assert jobs_router._segments_to_fallback_title([], 0, 10) == "Clip destacado"

    def test_fallback_result_esta_deshabilitado(self) -> None:
        with pytest.raises(RuntimeError, match="fallback deshabilitado"):
            jobs_router._fallback_result(None)

    def test_detect_hooks_segments_vacios(self) -> None:
        assert jobs_router._detect_hooks_for_segments([], None) == []

    def test_detect_hooks_propaga_error_normalizado(self) -> None:
        with patch("backend_fastapi.app.services.hook_service.detect_hooks", side_effect=RuntimeError("boom")):
            assert jobs_router._detect_hooks_for_segments([{"start": 0.0, "end": 1.0, "text": "x"}], None) == []

    def test_detect_hooks_exitoso(self, monkeypatch) -> None:
        esperado = [{"title": "h", "hook": {"start_time": 0, "end_time": 3}}]
        monkeypatch.setattr(
            "backend_fastapi.app.services.hook_service.detect_hooks", lambda *a, **k: esperado
        )
        video = SimpleNamespace(duration_seconds=30.0)
        assert jobs_router._detect_hooks_for_segments([{"start": 0.0, "end": 1.0, "text": "x"}], video) == esperado

    def test_set_progress_clampa_100(self, monkeypatch) -> None:
        artificial = SimpleNamespace(id=uuid_lib.uuid4(), progress=0)
        fake_db = FakeSession()
        assert jobs_router._set_progress(fake_db, artificial, 150) is None
        assert artificial.progress == 100
        assert fake_db.commits >= 1

    def test_set_progress_no_explota_con_job_sin_id(self, monkeypatch) -> None:
        fake_db = FakeSession()
        assert jobs_router._set_progress(fake_db, SimpleNamespace(progress=0), 40) is None

    def test_select_hook_clip_corto_sin_teaser(self) -> None:
        hs, he, meta = jobs_router._select_hook_for_clip(10.0, 30.0, None)
        assert (hs, he) == (10.0, 13.0)
        assert meta["mode"] == "in_clip"

    def test_select_hook_clip_menor_a_3s(self) -> None:
        hs, he, meta = jobs_router._select_hook_for_clip(0.0, 1.5, None)
        assert 0.0 < he <= 1.5
        assert meta["source"] == "in_clip_fallback"

    def test_select_hook_rango_invalido(self) -> None:
        hs, he, meta = jobs_router._select_hook_for_clip(100.0, 5.0, None)
        assert (hs, he) == (0.0, 3.0)
        assert meta["source"] == "in_clip_fallback_invalid_range"

    def test_select_hook_teaser_valido(self) -> None:
        valido = {
            "mode": "teaser",
            "start_time": 12.0,
            "end_time": 15.0,
            "curiosity_score": 9,
            "makes_sense_standalone": True,
        }
        hs, he, meta = jobs_router._select_hook_for_clip(10.0, 30.0, valido)
        assert (hs, he) == (12.0, 15.0)
        assert meta["mode"] == "teaser"

    def test_select_hook_teaser_rechazado_por_score_bajo(self) -> None:
        malo = {"mode": "teaser", "start_time": 12.0, "end_time": 15.0,
                "curiosity_score": 2, "makes_sense_standalone": True}
        hs, he, meta = jobs_router._select_hook_for_clip(10.0, 30.0, malo)
        assert (hs, he) == (10.0, 13.0)

    def test_select_hook_teaser_fuera_del_cuerpo_se_devuelve_igual(self) -> None:
        # La validación de contención la hace `_render_clip_with_ass_and_hook`
        # (ver test_render con in_clip fuera del cuerpo), el selector no.
        fuera = {
            "mode": "teaser",
            "start_time": 1.0,
            "end_time": 4.0,
            "curiosity_score": 9,
            "makes_sense_standalone": True,
        }
        hs, he, meta = jobs_router._select_hook_for_clip(10.0, 30.0, fuera)
        assert (hs, he) == (1.0, 4.0)
        assert meta["mode"] == "teaser"

    def test_render_args_validan_hook_in_clip(self, tmp_path, capsys) -> None:
        archivo = tmp_path / "v.mp4"
        archivo.write_bytes(b"x")
        with pytest.raises(ValueError, match="fuera del cuerpo"):
            jobs_router._render_clip_with_ass_and_hook(
                str(archivo), 10.0, 30.0, [], (1.0, 4.0, {"mode": "in_clip"}), uuid_lib.uuid4(), 0, None
            )


# ------------------------------------------------------------------ run_job


class TestRunJobHeavy:
    def test_run_job_sin_job_regresa_silencio(self) -> None:
        fake_db = FakeSession()
        with patch.object(jobs_router, "SessionLocal", lambda: fake_db):
            assert jobs_router._run_job(uuid_lib.uuid4()) is None

    def test_run_job_runpod_r2_completa_sin_render_local(self, tmp_path, db, user) -> None:
        fake_db = _fixtures.FakeSession() if False else FakeSession()  # noqa: F841
        db2 = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_con(video)
        db2.seed(video, job)

        result = {
            "engine": "native",
            "clips": [
                {
                    "url_r2": "https://videos.clipsai.xyz/clips/v/0_vertical.mp4",
                    "titulo": "R2 clip",
                    "inicio": "00:00:05",
                    "fin": "00:00:35",
                    "score": 8,
                    "criterio_principal": "dato",
                    "hook_texto": "hola",
                }
            ],
            "transcription_segments": [{"start": 0, "end": 1, "text": "hola"}],
        }
        with (
            patch.object(jobs_router, "SessionLocal", lambda: db2),
            patch(ENGINE_PATH, Mock(return_value=result)),
        ):
            jobs_router._run_job(job.id)  # type: ignore[arg-type]

        assert job.status == "completed"
        assert job.progress == 100
        assert job.result_metadata["_source"] == "runpod_r2"
        assert job.result_metadata["_r2_clip_count"] == 1
        assert len(db2.added) == 1
        clip_r2 = db2.added[0]
        assert clip_r2.storage_path.startswith("https://")
        assert clip_r2.tags["_render"] == "runpod_r2"
        assert clip_r2.tags["has_ass"] is True

    def test_run_job_render_local_completa(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_con(video)
        fake_db.seed(video, job)

        result = {
            "engine": "engine_real",
            "clips": [_clip_payload(score=9), _clip_payload(title="Baja-home", score=2)],
            "transcription_segments": [
                {"start": 5.0, "end": 10.0, "text": "quién golpea primero"},
                {"start": 12.0, "end": 16.0, "text": "los hechos"},
            ],
        }
        dest_dir = tmp_path / "renders"
        dest_dir.mkdir()

        def fake_render(video_path, clip_start, clip_end, segments, hook_sel, job_id, idx, title):
            salida = dest_dir / f"clip_{idx}.mp4"
            salida.write_bytes(b"rendido")
            return str(salida), {"render": "hook+ass", "hook_applied": True, "ass_applied": True}

        _ejecutar_con_render(
            fake_db, job, Mock(return_value=result), Mock(side_effect=fake_render)
        )

        assert job.status == "completed"
        assert job.progress == 100
        assert job.result_metadata["_render_stats"]["total"] == 1  # score 2 quedó filtrado
        assert job.result_metadata["_render_stats"]["hook+ass"] == 1
        assert job.result_metadata["_segments_count"] == 2
        assert job.result_metadata["_hooks_count"] == 1
        assert len(fake_db.added) == 1
        assert fake_db.added[0].tags["_render"] == "hook+ass"
        assert fake_db.added[0].tags["hook"]["applied"] is True

    def test_run_job_sin_clips_marca_failed(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_con(video)
        fake_db.seed(video, job)

        _ejecutar(fake_db, job, Mock(return_value={"clips": []}))

        assert job.status == "failed"
        assert job.error_message and "no devolvió clips" in job.error_message
        assert job.result_metadata["failed"] is True

    def test_run_job_error_claude_marca_failed_sin_rel_lanzar(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_con(video)
        fake_db.seed(video, job)

        # El re-raise interno de la ruta Claude cae en el except global, que marca
        # FAILED y no vuelve a lanzar: _run_job termina sin excepción.
        _ejecutar(fake_db, job, Mock(side_effect=RuntimeError("Error en Claude: timeout 60s")))

        assert job.status == "failed"
        assert "Error en Claude" in (job.error_message or "")
        assert job.result_metadata.get("error_type") == "RuntimeError"

    def test_run_job_video_faltante_en_disco_marca_failed(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        video.filepath = str(tmp_path / "ya-inexistente.mp4")
        job = _job_con(video)
        fake_db.seed(video, job)

        _ejecutar(fake_db, job, Mock(return_value={"clips": [_clip_payload()]}))

        assert job.status == "failed"
        assert "no existe en disco" in (job.error_message or "")

    def test_run_job_video_vacio_marca_failed(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        (tmp_path / "source.mp4").write_bytes(b"")  # 0 bytes
        job = _job_con(video)
        fake_db.seed(video, job)

        _ejecutar(fake_db, job, Mock(return_value={"clips": [_clip_payload()]}))
        assert job.status == "failed"

    def test_run_job_render_fallido_marca_failed(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_con(video)
        fake_db.seed(video, job)
        result = {"clips": [_clip_payload()], "transcription_segments": [{"start": 5, "end": 10, "text": "x"}]}

        _ejecutar_con_render(
            fake_db, job, Mock(return_value=result), Mock(side_effect=RuntimeError("ffmpeg crujio"))
        )

        assert job.status == "failed"
        assert "ffmpeg crujio" in (job.error_message or "")

    def test_run_job_sin_archivo_origen_marca_failed(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_con(video)
        fake_db.seed(video, job)
        tmp = Path(video.filepath)
        tmp.unlink()  # el video ya no está en disco

        # La validación corre ANTES de invocar el engine: su mock no debe llamarse
        engine = Mock(return_value={"clips": [_clip_payload()]})
        _ejecutar(fake_db, job, engine)
        engine.assert_not_called()
        assert job.status == "failed"
        assert "no existe en disco" in (job.error_message or "")

    def test_run_job_transcription_solo_en_bd_avanza_a_35(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        video.transcription_filepath = None
        video.transcript = "00:00:00 - Solo texto en la base"
        job = _job_con(video)
        fake_db.seed(video, job)

        result = {
            "clips": [_clip_payload(score=9)],
            "transcription_segments": [{"start": 5, "end": 25, "text": "golpeo"}],
        }
        dest = tmp_path / "renders"
        dest.mkdir()

        def fake_render(*args, **kwargs):
            salida = dest / "clip_00.mp4"
            salida.write_bytes(b"r")
            return str(salida), {"render": "hook+ass", "hook_applied": True, "ass_applied": True}

        _ejecutar_con_render(fake_db, job, Mock(return_value=result), Mock(side_effect=fake_render))
        assert job.status == "completed"
        assert job.progress == 100


# ------------------------------------------------------------------ run_job_safely


class TestRunJobSafely:
    def test_session_local_none_no_explota(self, monkeypatch) -> None:
        with patch.object(jobs_router, "SessionLocal", None):
            asyncio.run(jobs_router.run_job_safely(uuid_lib.uuid4()))

    def test_engine_roto_marca_y_no_propaga_a_background(self, tmp_path, user) -> None:
        fake_db = FakeSession()
        video = _video_tmp(tmp_path, user)
        job = _job_con(video)
        fake_db.seed(video, job)

        with (
            patch.object(jobs_router, "SessionLocal", lambda: fake_db),
            patch(ENGINE_PATH, Mock(side_effect=RuntimeError("boom fatal"))),
        ):
            asyncio.run(jobs_router.run_job_safely(job.id))

        assert job.status == "failed"
        assert "boom fatal" in (job.error_message or "")


# ------------------------------------------------------------------ segmentos


class TestLoadTranscriptionSegments:
    def test_fallback_transcript_bd(self, user, monkeypatch) -> None:
        video = make_video(user.id)
        video.filepath = "no/existe.mp4"
        video.transcription_filepath = None
        video.transcript = "00:00:05 - texto de prueba"

        monkeypatch.setattr(
            "backend_fastapi.app.services.whisper_service.transcribe_video", Mock(return_value=[])
        )
        segs = jobs_router._load_transcription_segments(video)
        assert segs and segs[0]["start"] == pytest.approx(5.0)

    def test_sin_video_fisico_usa_transcript(self, user) -> None:
        video = make_video(user.id, filepath="")
        video.transcript = "[0.0 - 2.0] corchetes"
        segs = jobs_router._load_transcription_segments(video)
        assert segs and segs[0]["text"] == "corchetes"

    def test_parse_transcript_text_to_segments_delega(self) -> None:
        segs = jobs_router._parse_transcript_text_to_segments("00:00:01 - algo")
        assert segs == [{"start": 1.0, "end": 4.0, "text": "algo"}]
