"""Cobertura de `services/engine.py` (y su modo local recién restaurado).

FFmpeg/Whisper/Claude/RunPod quedan mockeados; ningún proceso real.
"""

from __future__ import annotations

import uuid as uuid_lib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

from backend_fastapi.app.services import engine


# ------------------------------------------------------------------ helpers puros


class TestHelpers:
    def test_validate_video_source_ok(self, tmp_path) -> None:
        archivo = tmp_path / "v.mp4"
        archivo.write_bytes(b"x")
        assert engine._validate_video_source(archivo) == archivo

    def test_validate_video_source_inexistente(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="no existe"):
            engine._validate_video_source(tmp_path / "nada.mp4")

    def test_validate_video_source_vacio(self, tmp_path) -> None:
        archivo = tmp_path / "vacio.mp4"
        archivo.write_bytes(b"")
        with pytest.raises(ValueError, match="vacío"):
            engine._validate_video_source(archivo)

    def test_punctuation_forte(self) -> None:
        assert engine._ends_with_strong_punctuation("mundo.") is True
        assert engine._ends_with_strong_punctuation("¿qué?") is True
        assert engine._ends_with_strong_punctuation("hola") is False
        assert engine._ends_with_strong_punctuation('"fin."') is True  # limpia comillas

    def test_disallowed_lead(self) -> None:
        for texto in ("y después", "Bueno, veamos", "ENTONCES pasó", "o sea que", "porque sí"):
            assert engine._hook_has_disallowed_lead(texto) is True
        assert engine._hook_has_disallowed_lead("Nadie esperaba esto") is False

    def test_resolve_sentence_timestamps(self) -> None:
        mapa = [
            {"id": "S_1", "words": [{"start": 0.0, "end": 1.0, "text": "Hola"}, {"start": 1.0, "end": 2.5, "text": "mundo."}]},
            {"id": "S_2", "words": [{"start": 3.0, "end": 4.0, "text": "otra"}, {"start": 4.0, "end": 6.0, "text": "idea."}]},
        ]
        st, en = engine._resolve_sentence_timestamps("S_1", "S_2", mapa)
        assert st == pytest.approx(0.0)          # padding clamp a 0
        assert en == pytest.approx(6.35)

    def test_resolve_sentence_timestamps_expande_hasta_punto(self) -> None:
        mapa = [
            {"id": "S_1", "words": [{"start": 0.0, "end": 2.0, "text": "frase"}]},        # sin puntuación
            {"id": "S_2", "words": [{"start": 2.5, "end": 4.0, "text": "cerrada."}]},
        ]
        _, en = engine._resolve_sentence_timestamps("S_1", "S_1", mapa)
        assert en == pytest.approx(4.35)         # extendida hasta la oración con punto

    def test_resolve_sentence_ids_desconocidos(self) -> None:
        with pytest.raises(ValueError, match="desconocido"):
            engine._resolve_sentence_timestamps("S_9", "S_1", [])

    def test_resolve_sentence_invertido(self) -> None:
        mapa = [
            {"id": "S_1", "words": [{"start": 0.0, "end": 1.0, "text": "a."}]},
            {"id": "S_2", "words": [{"start": 2.0, "end": 3.0, "text": "b."}]},
        ]
        with pytest.raises(ValueError, match="invertido"):
            engine._resolve_sentence_timestamps("S_2", "S_1", mapa)

    def test_hook_window_valida_y_none(self) -> None:
        mapa = [
            {"id": "S_1", "words": [{"start": 0.0, "end": 1.4, "text": "uno"}]},
            {"id": "S_2", "words": [{"start": 1.5, "end": 2.8, "text": "dos"}]},
            {"id": "S_3", "words": [{"start": 3.0, "end": 5.6, "text": "tres"}]},
        ]
        candidato = {"start_sentence_id": "S_1", "end_sentence_id": "S_1"}
        ventana = engine._resolve_hook_candidate_window(candidato, mapa)
        assert ventana is not None
        # 1.4s <= 2.5 → expande a S_1..S_2 (2.8s, dentro del rango 2.5-5.5)
        assert ventana["duration"] == pytest.approx(2.8)
        assert ventana["start_sentence_id"] == "S_1"
        assert ventana["end_sentence_id"] == "S_2"

        # ids desconocidos -> None
        assert engine._resolve_hook_candidate_window({"start_sentence_id": "X", "end_sentence_id": "S_1"}, mapa) is None

    def test_select_clip_hook_fallback_sin_teaser(self) -> None:
        mapa = [
            {"id": "S_1", "words": [{"start": 0.0, "end": 1.0, "text": "Hola"}, {"start": 1.0, "end": 2.5, "text": "mundo"}]},
            {"id": "S_2", "words": [{"start": 3.0, "end": 20.0, "text": "resto"}]},
        ]
        clip = {"hook_candidates": [], "has_hook": False}
        hook = engine._select_clip_hook(clip, mapa, 0.0, 20.0)
        assert hook["mode"] == "in_clip"
        assert hook["source"] == "in_clip_fallback"
        assert hook["has_hook"] is False

    def test_select_clip_hook_teaser_valido(self) -> None:
        mapa = [
            {"id": "S_1", "words": [{"start": 0.0, "end": 1.0, "text": "inicio."}]},
            {"id": "S_2", "words": [{"start": 5.0, "end": 6.5, "text": "teaser"}, {"start": 6.5, "end": 8.4, "text": "fuerte."}]},
        ]
        clip = {
            "has_hook": True,
            "hook_candidates": [
                {"start_sentence_id": "S_2", "end_sentence_id": "S_2", "curiosity_score": 9,
                 "makes_sense_standalone": True}
            ],
        }
        hook = engine._select_clip_hook(clip, mapa, 0.0, 20.0)
        assert hook["mode"] == "teaser"
        assert hook["curiosity_score"] == 9
        assert (hook["start_time"], hook["end_time"]) == (pytest.approx(5.0), pytest.approx(8.4))

    def test_select_clip_hook_ignora_lead_prohibido(self) -> None:
        mapa = [
            {"id": "S_1", "words": [{"start": 0.0, "end": 1.0, "text": "inicio."}]},
            {"id": "S_2", "words": [{"start": 5.0, "end": 6.5, "text": "Bueno"}, {"start": 6.5, "end": 8.0, "text": "esto."}]},
        ]
        clip = {
            "has_hook": True,
            "hook_candidates": [
                {"start_sentence_id": "S_2", "end_sentence_id": "S_2", "curiosity_score": 10,
                 "makes_sense_standalone": True}
            ],
        }
        hook = engine._select_clip_hook(clip, mapa, 0.0, 20.0)
        # el teaser empieza con "Bueno" → descartado → fallback in-clip
        assert hook["mode"] == "in_clip"

    def test_select_clip_hook_en_apertura_es_in_clip(self) -> None:
        mapa = [
            {"id": "S_1", "words": [{"start": 0.0, "end": 1.0, "text": "gancho"}, {"start": 1.0, "end": 2.9, "text": "fuerte."}]},
        ]
        clip = {
            "has_hook": True,
            "hook_candidates": [
                {"start_sentence_id": "S_1", "end_sentence_id": "S_1", "curiosity_score": 10,
                 "makes_sense_standalone": True}
            ],
        }
        hook = engine._select_clip_hook(clip, mapa, 0.0, 30.0)
        assert hook["mode"] == "in_clip"
        assert hook["start_time"] == 0.0
        assert hook["end_time"] == pytest.approx(3.0)


# ------------------------------------------------------------------ ffprobe/ffmpeg


def _run_sideresponses(responses: list[Any]):
    """subprocess.run con respuestas en orden; cada dict: {stdout, stderr, returncode}."""
    plan = list(responses)

    def run(cmd, **kwargs):
        cfg = plan.pop(0) if plan else {"stdout": "", "stderr": "", "returncode": 0}
        return SimpleNamespace(returncode=cfg.get("returncode", 0), stdout=cfg.get("stdout", ""), stderr=cfg.get("stderr", ""))

    return run


class TestExtractAudio:
    def test_sin_pista_de_audio(self, tmp_path) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        with patch.object(engine.subprocess, "run", _run_sideresponses([{"stdout": "video\n", "returncode": 0}])):
            with pytest.raises(ValueError, match="no contiene audio"):
                engine.extract_audio_to_wav(str(video))

    def test_exito_con_diagnostico(self, tmp_path) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        wav_destino = Path(tempfile_mod.gettempdir()) / f"extracted_{video.stem}.wav"
        wav_destino.write_bytes(b"wav")

        def run(cmd, **k):
            if cmd[0] == "ffprobe":
                if "codec_type" in " ".join(cmd):
                    return SimpleNamespace(returncode=0, stdout="video\naudio\n", stderr="")
                return SimpleNamespace(returncode=0, stdout="12.5\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")  # ffmpeg extract ok

        with patch.object(engine.subprocess, "run", run):
            resultado = engine.extract_audio_to_wav(str(video))
        assert resultado == str(wav_destino)

    def test_ffmpeg_falla_al_extraer(self, tmp_path) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")

        def run(cmd, **k):
            if cmd[0] == "ffprobe" and "codec_type" in " ".join(cmd):
                return SimpleNamespace(returncode=0, stdout="audio\n", stderr="")
            if cmd[0] == "ffmpeg":
                return SimpleNamespace(returncode=1, stdout="", stderr="boom")
            return SimpleNamespace(returncode=0, stdout="12\n", stderr="")

        with patch.object(engine.subprocess, "run", run):
            with pytest.raises(RuntimeError, match="falló al extraer audio"):
                engine.extract_audio_to_wav(str(video))

    def test_timeout_al_extraer(self, tmp_path) -> None:
        import subprocess as subprocess_real

        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")

        def run(cmd, **k):
            if cmd[0] == "ffmpeg":
                raise subprocess_real.TimeoutExpired(cmd, 180)
            return SimpleNamespace(returncode=0, stdout="audio\n", stderr="")

        with patch.object(engine.subprocess, "run", run):
            with pytest.raises(RuntimeError, match="Timeout 180s"):
                engine.extract_audio_to_wav(str(video))


import tempfile as tempfile_mod  # noqa: E402  (usado por los tests de arriba)


class TestEnsureWavAudio:
    def test_fallback_segunda_via(self, tmp_path) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        wav_destino = Path(tempfile_mod.gettempdir()) / f"{video.stem}_extracted.wav"
        wav_destino.write_bytes(b"wav-actualizado")

        intento = {"n": 0}

        def run(cmd, **k):
            intento["n"] += 1
            if intento["n"] == 1:
                return SimpleNamespace(returncode=1, stdout="", stderr="fallo1")
            return SimpleNamespace(returncode=0, stdout="", stderr="")  # fallback ok

        with patch.object(engine.subprocess, "run", run):
            resultado = engine.ensure_wav_audio(str(video))
        assert resultado == str(wav_destino)

    def test_ambas_vias_fallan(self, tmp_path) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        wav_destino = Path(tempfile_mod.gettempdir()) / f"{video.stem}_extracted.wav"
        if wav_destino.exists():
            wav_destino.unlink()

        def run(cmd, **k):
            if "volumedetect" in " ".join(cmd):
                return SimpleNamespace(returncode=0, stdout="", stderr="max_volume: -10.0 dB")
            return SimpleNamespace(returncode=1, stdout="", stderr="kaput")

        with patch.object(engine.subprocess, "run", run):
            with pytest.raises(RuntimeError, match="Fallo en FFmpeg al extraer"):
                engine.ensure_wav_audio(str(video))

    def test_diagnostico_volumedetect_en_stderr(self, tmp_path, caplog) -> None:
        import logging

        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        wav_destino = Path(tempfile_mod.gettempdir()) / f"{video.stem}_extracted.wav"
        wav_destino.write_bytes(b"wav")

        def run(cmd, **k):
            if "volumedetect" in " ".join(cmd):
                return SimpleNamespace(returncode=0, stdout="", stderr="mean_volume: -20.0 dB\nmax_volume: -3.5 dB")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with caplog.at_level(logging.INFO, logger="backend_fastapi.app.services.engine"):
            with patch.object(engine.subprocess, "run", run):
                engine.ensure_wav_audio(str(video))
        assert "max_volume: -3.5 dB" in caplog.text


# ------------------------------------------------------------------ run_clip_engine


def _wav_grande(tmp_path: Path) -> str:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"W" * 20000)  # >10KB para el diagnóstico
    return str(wav)


def _segs_con_palabras() -> list[dict]:
    """Tres oraciones con timestamps de palabra (para build_sentence_map real)."""
    return [
        {"start": 0.0, "end": 2.9, "text": "Hola mundo fuerte.", "words": [
            {"start": 0.0, "end": 1.0, "text": "Hola"},
            {"start": 1.0, "end": 2.9, "text": "mundo fuerte."},
        ]},
        {"start": 4.0, "end": 7.6, "text": "Teaser impactante.", "words": [
            {"start": 4.0, "end": 5.4, "text": "Teaser"},
            {"start": 5.4, "end": 7.6, "text": "impactante."},
        ]},
        {"start": 8.0, "end": 30.0, "text": "Resto de la historia.", "words": [
            {"start": 8.0, "end": 14.0, "text": "Resto"},
            {"start": 14.0, "end": 30.0, "text": "de la historia."},
        ]},
    ]


class TestRunClipEngine:
    def test_transcripcion_inexistente(self, tmp_path) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        with pytest.raises(FileNotFoundError, match="Transcripcion no encontrada"):
            engine.run_clip_engine(str(video), str(tmp_path / "no.txt"), allow_runpod=False)

    def test_rama_runpod_ok(self, tmp_path, monkeypatch) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        tp = tmp_path / "t.txt"
        tp.write_text("00:00:00 - hola", encoding="utf-8")

        from backend_fastapi.app.services import runpod_service

        monkeypatch.setattr(runpod_service, "is_runpod_configured", lambda: True)
        monkeypatch.setattr(
            runpod_service,
            "process_local_video_via_runpod",
            Mock(return_value={"clips": [{"titulo": "x"}], "transcription_segments": [{"start": 0, "end": 1, "text": "h"}]}),
        )
        callback = Mock()
        result = engine.run_clip_engine(str(video), str(tp), callback)
        assert result["engine"] == "runpod"
        assert result["video"] == str(video)
        callback.assert_called_once_with(35)

    def test_rama_runpod_sin_segmentos(self, tmp_path, monkeypatch) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        tp = tmp_path / "t.txt"
        tp.write_text("00:00:00 - hola", encoding="utf-8")

        from backend_fastapi.app.services import runpod_service

        monkeypatch.setattr(runpod_service, "is_runpod_configured", lambda: True)
        monkeypatch.setattr(
            runpod_service,
            "process_local_video_via_runpod",
            Mock(return_value={"clips": [], "transcription_segments": []}),
        )
        with pytest.raises(RuntimeError, match="no devolvió segmentos"):
            engine.run_clip_engine(str(video), str(tp))

    def test_local_claude_ok(self, tmp_path, monkeypatch) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        tp = tmp_path / "t.txt"
        tp.write_text("00:00:00 - respaldo", encoding="utf-8")
        wav = _wav_grande(tmp_path)

        from backend_fastapi.app.services import whisper_service, claude_service

        monkeypatch.setattr(engine, "ensure_wav_audio", lambda video_path: wav)
        monkeypatch.setattr(whisper_service, "transcribe_audio", lambda wav_path, language="es": _segs_con_palabras())
        crudo = [
            {
                "start_sentence_id": "S_1",
                "end_sentence_id": "S_3",
                "score": 9,
                "title": "Momento fuerte",
                "has_hook": False,
                "hook_candidates": [],
            }
        ]
        monkeypatch.setattr(claude_service, "select_clips_via_claude", lambda *a, **k: crudo)

        callback = Mock()
        result = engine.run_clip_engine(str(video), str(tp), callback, allow_runpod=False)

        assert result["engine"] == "native_claude"
        assert len(result["clips"]) == 1
        clip = result["clips"][0]
        assert clip["criterio_principal"] == "claude_semantico"
        assert clip["start_time"] == pytest.approx(0.0)
        assert clip["end_time"] == pytest.approx(30.35)
        assert clip["hook_selection"]["mode"] == "in_clip"   # sin teaser válido
        assert result["transcription_segments"] == _segs_con_palabras()
        callback.assert_called_once_with(35)

    def test_local_teaser_aplicado(self, tmp_path, monkeypatch) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        tp = tmp_path / "t.txt"
        tp.write_text("00:00:00 - respaldo", encoding="utf-8")
        wav = _wav_grande(tmp_path)

        from backend_fastapi.app.services import whisper_service, claude_service

        monkeypatch.setattr(engine, "ensure_wav_audio", lambda video_path: wav)
        monkeypatch.setattr(whisper_service, "transcribe_audio", lambda wav_path, language="es": _segs_con_palabras())
        crudo = [
            {
                "start_sentence_id": "S_1",
                "end_sentence_id": "S_3",
                "score": 9,
                "title": "Teaser fuerte",
                "has_hook": True,
                "hook_candidates": [
                    {"start_sentence_id": "S_2", "end_sentence_id": "S_2",
                     "curiosity_score": 10, "makes_sense_standalone": True}
                ],
            }
        ]
        monkeypatch.setattr(claude_service, "select_clips_via_claude", lambda *a, **k: crudo)
        result = engine.run_clip_engine(str(video), str(tp), allow_runpod=False)
        hook = result["clips"][0]["hook_selection"]
        assert hook["mode"] == "teaser"
        assert hook["curiosity_score"] == 10
        assert hook["start_time"] == pytest.approx(4.0)

    def test_local_whisper_sin_voz_fallback_texto_sin_timestamps(self, tmp_path, monkeypatch) -> None:
        """Comportamiento real documentado: el fallback a transcripción file
        produce segmentos SIN timestamps de palabra → build_sentence_map (Claude)
        exige timestamps de palabra y el pipeline falla con RuntimeError.
        Hallazgo: las subidas con solo .txt no producen clips en modo local."""
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        tp = tmp_path / "t.txt"
        tp.write_text("00:00:00 - respaldo desde archivo", encoding="utf-8")
        wav = _wav_grande(tmp_path)

        from backend_fastapi.app.services import whisper_service

        monkeypatch.setattr(engine, "ensure_wav_audio", lambda video_path: wav)
        monkeypatch.setattr(
            whisper_service, "transcribe_audio",
            Mock(side_effect=ValueError("El video subido no contiene audio")),
        )
        with pytest.raises(RuntimeError, match="No hay timestamps"):
            engine.run_clip_engine(str(video), str(tp), allow_runpod=False)

    def test_local_transcripcion_file_vacia_propaga_valueerror(self, tmp_path, monkeypatch) -> None:
        """Archivo de transcripción en blanco: el `raise` interno re-lanza el
        ValueError original de Whisper (sin mensaje de '0 segmentos')."""
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        tp = tmp_path / "vacia.txt"
        tp.write_text("   ", encoding="utf-8")
        wav = _wav_grande(tmp_path)

        from backend_fastapi.app.services import whisper_service

        monkeypatch.setattr(engine, "ensure_wav_audio", lambda video_path: wav)
        monkeypatch.setattr(
            whisper_service, "transcribe_audio",
            Mock(side_effect=ValueError("El video subido no contiene audio")),
        )
        with pytest.raises(ValueError, match="no contiene audio"):
            engine.run_clip_engine(str(video), str(tp), allow_runpod=False)

    def test_local_claude_sin_clips_validos_propaga(self, tmp_path, monkeypatch) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        tp = tmp_path / "t.txt"
        tp.write_text("00:00:00 - respaldo", encoding="utf-8")
        wav = _wav_grande(tmp_path)

        from backend_fastapi.app.services import whisper_service, claude_service

        monkeypatch.setattr(engine, "ensure_wav_audio", lambda video_path: wav)
        monkeypatch.setattr(whisper_service, "transcribe_audio", lambda wav_path, language="es": _segs_con_palabras())
        # clip de 3s (fuera de 15-60) → rechazado → RuntimeError
        monkeypatch.setattr(claude_service, "select_clips_via_claude", lambda *a, **k: [
            {"start_sentence_id": "S_1", "end_sentence_id": "S_1", "score": 9, "title": "corto"}
        ])
        with pytest.raises(RuntimeError, match="no quedaron clips"):
            engine.run_clip_engine(str(video), str(tp), allow_runpod=False)
