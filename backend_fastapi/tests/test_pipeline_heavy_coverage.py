"""Cobertura de `services/whisper_service.py` y `tasks/subtitle_pipeline.py`.

Whisper/faster-whisper/ffprobe/ffmpeg y RunPod quedan mockeados — sin modelo,
sin GPU y sin red.
"""

from __future__ import annotations

import sys
import tempfile
import types
import uuid as uuid_lib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

import _fixtures
import conftest as _c
from _fixtures import FakeSession, make_clip, make_video

from backend_fastapi.app.services import whisper_service as ws

_SOCIAL = _c.make_social_account
_JOB = _c.make_job


def _video_tmp(tmp_path: Path, usuario: Any = None) -> Any:
    archivo = tmp_path / "v.mp4"
    archivo.write_bytes(b"x")
    return archivo


def _resp_run(stdout: str = "", stderr: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# ------------------------------------------------------------------ helpers


class TestHelpersWhisper:
    def test_has_audio_track_si_no(self, monkeypatch, tmp_path) -> None:
        video = _video_tmp(tmp_path)
        monkeypatch.setattr(ws.subprocess, "run", Mock(return_value=_resp_run("video\naudio\n")))
        assert ws._has_audio_track(str(video)) is True

        monkeypatch.setattr(ws.subprocess, "run", Mock(return_value=_resp_run("video\n")))
        assert ws._has_audio_track(str(video)) is False

        # ffprobe con returncode != 0 → sin pista de audio detectable
        monkeypatch.setattr(ws.subprocess, "run", Mock(return_value=_resp_run(returncode=1)))
        assert ws._has_audio_track(str(video)) is False

        # ffprobe NO instalado (FileNotFoundError) → True: no bloquea, Whisper detectará
        monkeypatch.setattr(ws.subprocess, "run", Mock(side_effect=FileNotFoundError()))
        assert ws._has_audio_track(str(video)) is True

    def test_validate_video_source(self, tmp_path) -> None:
        video = _video_tmp(tmp_path)
        assert ws._validate_video_source(str(video)) == video
        with pytest.raises(FileNotFoundError):
            ws._validate_video_source(str(tmp_path / "nada.mp4"))
        vacio = tmp_path / "vacio.mp4"
        vacio.write_bytes(b"")
        with pytest.raises(ValueError, match="vacío"):
            ws._validate_video_source(str(vacio))

    def test_detect_device_explicito(self) -> None:
        assert ws._detect_device_and_compute("cuda", "float16") == ("cuda", "float16")
        assert ws._detect_device_and_compute("cpu", "int8") == ("cpu", "int8")

    def test_detect_device_auto_sin_torch(self, monkeypatch) -> None:
        monkeypatch.setitem(sys.modules, "torch", None)  # import torch → ImportError
        assert ws._detect_device_and_compute("auto", "auto") == ("cpu", "int8")

    def test_detect_device_auto_con_cuda(self, monkeypatch) -> None:
        torch_fake = SimpleNamespace(cuda=SimpleNamespace(is_available=Mock(return_value=True)))
        monkeypatch.setitem(sys.modules, "torch", torch_fake)
        assert ws._detect_device_and_compute("auto", "auto") == ("cuda", "float16")


# ------------------------------------------------------------------ extract_audio_wav


class TestExtractAudioWav:
    def _run_plan(self, video: Path, salida: Path, primer_ok: bool = True):
        intento = {"n": 0}

        def run(cmd, **k):
            intento["n"] += 1
            if cmd[0] == "ffprobe":
                return _resp_run("video\naudio\n")
            if cmd[0] == "ffmpeg" and "version" in " ".join(cmd):
                return _resp_run()
            if intento["n"] == 2 and not primer_ok:
                return _resp_run(returncode=1, stderr="kaput")
            if not salida.exists():
                salida.write_bytes(b"wav-data")
            return _resp_run()

        return run, intento

    def test_exito(self, tmp_path, monkeypatch) -> None:
        video = _video_tmp(tmp_path)
        salida = tmp_path / "out.wav"
        run, _ = self._run_plan(video, salida, primer_ok=True)
        monkeypatch.setattr(ws.subprocess, "run", run)
        assert ws.extract_audio_wav(str(video), str(salida)) == str(salida)

    def test_fallback_segunda_via(self, tmp_path, monkeypatch) -> None:
        video = _video_tmp(tmp_path)
        salida = tmp_path / "out2.wav"
        run, intento = self._run_plan(video, salida, primer_ok=False)
        monkeypatch.setattr(ws.subprocess, "run", run)
        resultado = ws.extract_audio_wav(str(video), str(salida))
        assert resultado == str(salida)
        assert intento["n"] >= 3  # primer intento + fallback

    def test_ambas_vias_fallan(self, tmp_path, monkeypatch) -> None:
        video = _video_tmp(tmp_path)
        salida = tmp_path / "out3.wav"

        def run(cmd, **k):
            if cmd[0] == "ffprobe" or "version" in " ".join(cmd):
                return _resp_run("video\naudio\n")
            return _resp_run(returncode=1, stderr="boom")

        monkeypatch.setattr(ws.subprocess, "run", run)
        with pytest.raises(RuntimeError, match="Fallo en FFmpeg al extraer"):
            ws.extract_audio_wav(str(video), str(salida))

    def test_sin_pista_audio(self, tmp_path, monkeypatch) -> None:
        video = _video_tmp(tmp_path)
        monkeypatch.setattr(ws.subprocess, "run", Mock(return_value=_resp_run("video\n")))
        with pytest.raises(ValueError, match="no contiene audio"):
            ws.extract_audio_wav(str(video), str(tmp_path / "x.wav"))

    def test_ffmpeg_no_instalado(self, tmp_path, monkeypatch) -> None:
        video = _video_tmp(tmp_path)
        monkeypatch.setattr(ws.subprocess, "run", Mock(side_effect=FileNotFoundError()))
        with pytest.raises(RuntimeError, match="no instalado"):
            ws.extract_audio_wav(str(video), str(tmp_path / "x.wav"))


# ------------------------------------------------------------------ transcribe_wav


def _fake_whisper_module(segs: list[Any], fallo_al_cargar: bool = False) -> types.ModuleType:
    mod = types.ModuleType("faster_whisper")

    if fallo_al_cargar:
        mod.WhisperModel = Mock(side_effect=RuntimeError("modelo roto"))
        return mod

    def transcribe(wav, **k):
        return iter(segs), SimpleNamespace(language="es")

    mod.WhisperModel = Mock(return_value=SimpleNamespace(transcribe=transcribe))
    return mod


class TestTranscribeWav:
    def test_wav_inexistente(self) -> None:
        with pytest.raises(FileNotFoundError):
            ws.transcribe_wav("no/existe.wav")

    def test_wav_casi_vacio(self, tmp_path) -> None:
        wav = tmp_path / "chico.wav"
        wav.write_bytes(b"W" * 100)  # <10KB → diagnóstico de corrupto
        mod = _fake_whisper_module([])
        with patch.dict(sys.modules, {"faster_whisper": mod}):
            with pytest.raises(RuntimeError, match="casi vacío"):
                ws.transcribe_wav(str(wav))

    def test_exito_normaliza_y_preserva_words(self, tmp_path) -> None:
        wav = tmp_path / "grande.wav"
        wav.write_bytes(b"W" * 20000)
        segs = [
            SimpleNamespace(
                text=" Hola mundo. ", start=0.0, end=2.0,
                words=[SimpleNamespace(start=0.0, end=1.0, word="Hola"),
                       SimpleNamespace(start=1.0, end=2.0, word="mundo.")],
            ),
            SimpleNamespace(text="", start=2.0, end=3.0, words=[]),          # texto vacío → fuera
            SimpleNamespace(text="invertido", start=5.0, end=4.0, words=[]),  # end<start → clamp
        ]
        mod = _fake_whisper_module(segs)
        with patch.dict(sys.modules, {"faster_whisper": mod}):
            resultado = ws.transcribe_wav(str(wav), model_name="turbo")
        assert len(resultado) == 2
        assert resultado[0]["text"] == "Hola mundo."
        assert [w["text"] for w in resultado[0]["words"]] == ["Hola", "mundo."]
        # el segmento invertido se clampa a end=start+0.5
        assert resultado[1]["end"] == pytest.approx(5.5)
        # el modelo resuelto por _MODEL_MAP
        mod.WhisperModel.assert_called_once()
        assert mod.WhisperModel.call_args.args[0].startswith("deepdml/faster-whisper-large-v3-turbo")

    def test_cero_segmentos(self, tmp_path) -> None:
        wav = tmp_path / "g2.wav"
        wav.write_bytes(b"W" * 20000)
        mod = _fake_whisper_module([])
        with patch.dict(sys.modules, {"faster_whisper": mod}):
            with pytest.raises(RuntimeError, match="devolvió 0 segmentos"):
                ws.transcribe_wav(str(wav))

    def test_fallo_al_cargar_modelo(self, tmp_path) -> None:
        wav = tmp_path / "g3.wav"
        wav.write_bytes(b"W" * 20000)
        mod = _fake_whisper_module([], fallo_al_cargar=True)
        with patch.dict(sys.modules, {"faster_whisper": mod}):
            with pytest.raises(RuntimeError, match="No se pudo cargar modelo"):
                ws.transcribe_wav(str(wav))

    def test_faster_whisper_no_instalado(self, tmp_path) -> None:
        wav = tmp_path / "g4.wav"
        wav.write_bytes(b"W" * 20000)
        with patch.dict(sys.modules, {"faster_whisper": None}):
            with pytest.raises(RuntimeError, match="no instalado"):
                ws.transcribe_wav(str(wav))


# ------------------------------------------------------------------ transcribe_video


class TestTranscribeVideo:
    def test_rama_runpod_normaliza(self, tmp_path, monkeypatch) -> None:
        from backend_fastapi.app.services import runpod_service

        video = _video_tmp(tmp_path)
        monkeypatch.setattr(runpod_service, "is_runpod_configured", lambda: True)
        monkeypatch.setattr(
            runpod_service,
            "process_local_video_via_runpod",
            Mock(return_value={"transcription_segments": [
                {"start": "0", "end": "1", "text": "hola"},
                {"start": 2, "end": 1, "text": "mal"},   # end<=start → descartado
            ]}),
        )
        segs = ws.transcribe_video(str(video))
        assert segs == [{"start": 0.0, "end": 1.0, "text": "hola", "words": []}]

    def test_rama_runpod_formato_invalido(self, tmp_path, monkeypatch) -> None:
        from backend_fastapi.app.services import runpod_service

        video = _video_tmp(tmp_path)
        monkeypatch.setattr(runpod_service, "is_runpod_configured", lambda: True)
        monkeypatch.setattr(
            runpod_service,
            "process_local_video_via_runpod",
            Mock(return_value={"transcription_segments": [{"start": 2, "end": 1, "text": "mal"}]}),
        )
        with pytest.raises(RuntimeError, match="formato inválido"):
            ws.transcribe_video(str(video))

    def test_local_sin_audio(self, tmp_path, monkeypatch) -> None:
        from backend_fastapi.app.services import runpod_service

        video = _video_tmp(tmp_path)
        monkeypatch.setattr(runpod_service, "is_runpod_configured", lambda: False)
        monkeypatch.setattr(ws, "_has_audio_track", lambda path: False)
        with pytest.raises(ValueError, match="no contiene audio"):
            ws.transcribe_video(str(video))

    def test_local_completo_borra_wav(self, tmp_path, monkeypatch) -> None:
        from backend_fastapi.app.services import runpod_service

        video = _video_tmp(tmp_path)
        wav = tmp_path / "extraido.wav"
        wav.write_bytes(b"W" * 20000)
        # el .env real de esta máquina tiene RUNPOD_API_KEY: forzamos modo local
        monkeypatch.setattr(runpod_service, "is_runpod_configured", lambda: False)
        monkeypatch.setattr(ws, "_has_audio_track", lambda path: True)
        monkeypatch.setattr(ws, "extract_audio_wav", lambda video_path, wav_path=None: str(wav))
        monkeypatch.setattr(
            ws, "transcribe_wav",
            lambda wav_path, language="es", model_name="large-v3-turbo": [
                {"start": 0.0, "end": 1.0, "text": "hola", "words": []}
            ],
        )
        segs = ws.transcribe_video(str(video))
        assert segs[0]["text"] == "hola"
        assert not wav.exists()  # keep_wav False → se limpia

    def test_local_keep_wav(self, tmp_path, monkeypatch) -> None:
        from backend_fastapi.app.services import runpod_service

        video = _video_tmp(tmp_path)
        wav = tmp_path / "extraido2.wav"
        wav.write_bytes(b"W" * 20000)
        monkeypatch.setattr(runpod_service, "is_runpod_configured", lambda: False)
        monkeypatch.setattr(ws, "_has_audio_track", lambda path: True)
        monkeypatch.setattr(ws, "extract_audio_wav", lambda video_path, wav_path=None: str(wav))
        monkeypatch.setattr(
            ws, "transcribe_wav",
            lambda wav_path, language="es", model_name="large-v3-turbo": [
                {"start": 0.0, "end": 1.0, "text": "hola", "words": []}
            ],
        )
        ws.transcribe_video(str(video), keep_wav=True)
        assert wav.exists()

    def test_alias_transcribe_audio_y_to_segments(self, tmp_path, monkeypatch) -> None:
        wav = _video_tmp(tmp_path)
        segs = [{"start": 0.0, "end": 1.0, "text": "hola", "words": []}]
        monkeypatch.setattr(
            ws, "transcribe_wav",
            lambda wav_path, language="es", model_name="large-v3-turbo": segs,
        )
        monkeypatch.setattr(ws, "transcribe_video", lambda *a, **k: segs)
        assert ws.transcribe_audio(str(wav))[0]["text"] == "hola"
        assert ws.transcribe_video_to_segments(str(wav))[0]["text"] == "hola"


# ------------------------------------------------------------------ subtitle_pipeline


from backend_fastapi.app.tasks import subtitle_pipeline as sp  # noqa: E402


class TestUpdateClipStatus:
    def test_error_log_atributo_presente(self) -> None:
        clip = make_clip(uuid_lib.uuid4())
        sp._update_clip_status(FakeSession(), clip, "FAILED", error_log="boom " * 500)
        assert clip.status == "FAILED"
        assert clip.error_log.startswith("boom")
        assert len(clip.error_log) <= 8000

    def test_error_log_sin_atributo_usa_tags(self) -> None:
        clip = SimpleNamespace(status="ready", tags=None)  # sin error_log
        sp._update_clip_status(FakeSession(), clip, "FAILED", error_log="kaput")
        assert clip.status == "FAILED"
        assert clip.tags["error_log"] == "kaput"

    def test_completo_limpia_error(self) -> None:
        clip = make_clip(uuid_lib.uuid4(), error_log="viejo")
        sp._update_clip_status(FakeSession(), clip, "COMPLETED", output_path="/x/out.mp4")
        assert clip.status == "COMPLETED"
        assert clip.error_log is None
        assert clip.storage_path == "/x/out.mp4"


class TestResolveVideoPath:
    def _base(self, tmp_path: Path) -> tuple[FakeSession, Path]:
        return FakeSession(), tmp_path

    def test_por_storage_path(self, tmp_path, db, user) -> None:
        archivo = tmp_path / "clip.mp4"
        archivo.write_bytes(b"x")
        clip = make_clip(_JOB(uuid_lib.uuid4()).id, storage_path=str(archivo))
        assert sp._resolve_video_path(clip, db) == str(archivo)

    def test_por_video(self, tmp_path, db, user) -> None:
        video_file = tmp_path / "fuente.mp4"
        video_file.write_bytes(b"x")
        video = make_video(user.id, filepath=str(video_file), file_path=str(video_file))
        clip = make_clip(_JOB(video.id).id, video.id, storage_path="/no/existe.mp4")
        db.seed(video)
        assert sp._resolve_video_path(clip, db) == str(video_file)

    def test_por_job(self, tmp_path, db, user) -> None:
        video_file = tmp_path / "fuente2.mp4"
        video_file.write_bytes(b"x")
        video = make_video(user.id, filepath=str(video_file), file_path=str(video_file))
        job = _JOB(video.id)
        clip = make_clip(job.id, None, storage_path="/no/existe.mp4")
        db.seed(video, job)
        assert sp._resolve_video_path(clip, db) == str(video_file)

    def test_nada_encontrado(self, db) -> None:
        clip = make_clip(_JOB(uuid_lib.uuid4()).id, storage_path="/no/existe.mp4")
        assert sp._resolve_video_path(clip, db) is None


class TestRunSubtitlePipeline:
    def _setup(self, db: FakeSession, user: Any, tmp_path: Path) -> tuple[Any, Any]:
        video_file = tmp_path / "fuente.mp4"
        video_file.write_bytes(b"x")
        video = make_video(user.id, filepath=str(video_file), file_path=str(video_file))
        job = _JOB(video.id)
        clip = make_clip(job.id, video.id, start_time=0.0, end_time=30.0, storage_path=str(video_file))
        db.seed(video, job, clip)
        return clip, video_file

    def test_clip_id_invalido(self) -> None:
        with pytest.raises(ValueError, match="invalido"):
            sp.run_subtitle_pipeline("no-es-uuid")

    def test_clip_inexistente_regresa_silencio(self, monkeypatch) -> None:
        fake_db = FakeSession()
        with patch.object(sp, "SessionLocal", lambda: fake_db):
            assert sp.run_subtitle_pipeline(uuid_lib.uuid4()) is None

    def test_flujo_completo(self, tmp_path, db, user, monkeypatch) -> None:
        clip, video_file = self._setup(db, user, tmp_path)
        salida_esperada = tmp_path / f"{clip.id}_subtitled.mp4"

        def fake_extract(video_path, wav_path=None):
            Path(wav_path).write_bytes(b"W" * 20000)
            return wav_path

        segs = [
            {"start": 0.0, "end": 2.0, "text": "Hola"},
            {"start": 1.0, "end": 5.0, "text": "mundo"},
            {"start": 100.0, "end": 110.0, "text": "fuera de ventana"},  # descartado
        ]
        salida = salida_esperada

        def fake_burn(video_path, ass_path, output_path):
            Path(output_path).write_bytes(b"mp4")
            return output_path

        with (
            patch.object(sp, "SessionLocal", lambda: db),
            patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", lambda: False),
            patch("backend_fastapi.app.services.whisper_service.extract_audio_wav", fake_extract),
            patch("backend_fastapi.app.services.whisper_service.transcribe_wav", Mock(return_value=segs)),
            patch("backend_fastapi.app.services.ffmpeg_service.burn_subtitles", fake_burn),
        ):
            sp.run_subtitle_pipeline(clip.id)

        assert clip.status == "COMPLETED"
        assert clip.storage_path != str(video_file)          # nunca el original
        assert clip.storage_path.endswith("_subtitled.mp4")
        assert salida is not None and Path(clip.storage_path).exists()
        assert db.commits >= 2

    def test_flujo_runpod_sin_extract_local(self, tmp_path, db, user, monkeypatch) -> None:
        clip, video_file = self._setup(db, user, tmp_path)
        segs = [{"start": 0.0, "end": 2.0, "text": "Hola"}]
        salida = tmp_path / "salida2_sub.mp4"

        extract = Mock()
        transcribe_video = Mock(return_value=segs)
        transcribe_wav = Mock()

        def fake_burn(video_path, ass_path, output_path):
            Path(output_path).write_bytes(b"mp4")
            return output_path

        with (
            patch.object(sp, "SessionLocal", lambda: db),
            patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", lambda: True),
            patch("backend_fastapi.app.services.whisper_service.extract_audio_wav", extract),
            patch("backend_fastapi.app.services.whisper_service.transcribe_video", transcribe_video),
            patch("backend_fastapi.app.services.whisper_service.transcribe_wav", transcribe_wav),
            patch("backend_fastapi.app.services.ffmpeg_service.burn_subtitles", fake_burn),
        ):
            sp.run_subtitle_pipeline(clip.id)

        assert clip.status == "COMPLETED"
        extract.assert_not_called()      # vía RunPod no extrae WAV local
        transcribe_video.assert_called_once()
        transcribe_wav.assert_not_called()

    def test_transcripcion_vacia_marca_failed(self, tmp_path, db, user, monkeypatch) -> None:
        clip, _ = self._setup(db, user, tmp_path)

        with (
            patch.object(sp, "SessionLocal", lambda: db),
            patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", lambda: False),
            patch("backend_fastapi.app.services.whisper_service.extract_audio_wav",
                  Mock(side_effect=lambda video_path, wav_path=None: wav_path)),
            patch("backend_fastapi.app.services.whisper_service.transcribe_wav", Mock(return_value=[])),
        ):
            sp.run_subtitle_pipeline(clip.id)

        assert clip.status == "FAILED"
        assert clip.error_log and "Transcripcion vacia" in clip.error_log

    def test_video_faltante_marca_failed(self, tmp_path, db, user, monkeypatch) -> None:
        clip, _ = self._setup(db, user, tmp_path)
        Path(clip.storage_path).unlink()  # la fuente desaparece

        with patch.object(sp, "SessionLocal", lambda: db):
            sp.run_subtitle_pipeline(clip.id)

        assert clip.status == "FAILED"
        assert "Video fuente no encontrado" in (clip.error_log or "")

    def test_salida_con_nombre_igual_al_fuente_usa_sufijo(self, tmp_path, db, user, monkeypatch) -> None:
        # El video fuente se llama igual que el output previsto → usa sufijo _burned
        clip = make_clip(_JOB(uuid_lib.uuid4()).id, start_time=0.0, end_time=30.0, storage_path="")
        video_file = tmp_path / f"{clip.id}_subtitled.mp4"
        video_file.write_bytes(b"x")
        clip.storage_path = str(video_file)
        video = make_video(user.id, filepath=str(video_file), file_path=str(video_file))
        job = _JOB(video.id)
        clip.job_id = job.id
        clip.video_id = video.id
        db.seed(video, job, clip)

        segs = [{"start": 0.0, "end": 2.0, "text": "Hola"}]
        escritos: list[str] = []

        def fake_burn(video_path, ass_path, output_path):
            escritos.append(output_path)
            Path(output_path).write_bytes(b"mp4")
            return output_path

        with (
            patch.object(sp, "SessionLocal", lambda: db),
            patch("backend_fastapi.app.services.runpod_service.is_runpod_configured", lambda: False),
            patch("backend_fastapi.app.services.whisper_service.extract_audio_wav",
                  Mock(side_effect=lambda video_path, wav_path=None: wav_path)),
            patch("backend_fastapi.app.services.whisper_service.transcribe_wav", Mock(return_value=segs)),
            patch("backend_fastapi.app.services.ffmpeg_service.burn_subtitles", fake_burn),
        ):
            sp.run_subtitle_pipeline(clip.id)

        assert escritos and "_burned" in escritos[0]
        assert clip.status == "COMPLETED"
