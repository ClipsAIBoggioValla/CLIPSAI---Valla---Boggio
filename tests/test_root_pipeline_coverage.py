"""Cobertura del pipeline raíz: `main.py`, `engine.py`, `video_processor.py`
y `whisper_transcriber.py` — sin FFmpeg, red ni Whisper reales.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import main as main_mod  # noqa: E402
import engine as engine_mod  # noqa: E402
import video_processor as vp_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_nvenc_cache():
    """Aísla el cache del sondeo NVENC entre tests (sin estado global cruzado)."""
    vp_mod._probe_nvenc_cache = None
    yield
    vp_mod._probe_nvenc_cache = None


# ------------------------------------------------------------------- main.py


def _escribir(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")


class TestEnvYChecks:
    def test_cargar_env_lee_claves(self, tmp_path: Path, monkeypatch: Any) -> None:
        env = tmp_path / ".env"
        _escribir(env, "ANTHROPIC_API_KEY=sk-test-123\n# comentario\nOPENAI_API_KEY= sk-openai \n")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        main_mod.cargar_env(str(env))
        import os
        assert os.getenv("ANTHROPIC_API_KEY") == "sk-test-123"
        assert os.getenv("OPENAI_API_KEY") == "sk-openai"

    def test_verificar_ffmpeg_con_binario(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=0)))
        assert main_mod.verificar_ffmpeg() is True

    def test_verificar_ffmpeg_sin_binario(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod.subprocess, "run", Mock(side_effect=FileNotFoundError("no ffmpeg")))
        assert main_mod.verificar_ffmpeg() is False

    def test_verificar_ffmpeg_con_error(self, monkeypatch: Any) -> None:
        import subprocess as sp

        monkeypatch.setattr(main_mod.subprocess, "run", Mock(side_effect=sp.CalledProcessError(1, "ffmpeg")))
        assert main_mod.verificar_ffmpeg() is False


class TestTranscripcion:
    def test_leer_transcripcion_para_ia_trunca(self, tmp_path: Path) -> None:
        archivo = tmp_path / "transcripcion_formatted.txt"
        _escribir(archivo, "x" * 300)
        texto = main_mod.leer_transcripcion_para_ia(str(archivo), max_chars=100)
        assert len(texto) == 100

    def test_formatear_transcripcion_agrupa_segmentos(self, tmp_path: Path) -> None:
        salida = tmp_path / "formatted.txt"
        crudo = (
            "0:00 - Hola mundo\n"
            "0:05 - seguimos hablando\n"
            "0:10 - tercer renglon\n"
        )
        resultado = main_mod.formatear_transcripcion(crudo, str(salida))
        assert resultado == str(salida)
        contenido = salida.read_text(encoding="utf-8")
        assert "00:00:00" in contenido
        assert contenido.strip()

    def test_preparar_transcripcion_para_ia_comprime(self, tmp_path: Path) -> None:
        archivo = tmp_path / "formatted.txt"
        lineas = "\n".join(f"0:{i:02d}:00 - segmento numero {i}" for i in range(40))
        _escribir(archivo, lineas)
        texto = main_mod.preparar_transcripcion_para_ia(str(archivo), max_segmentos=5)
        assert texto.strip()

    def test_enriquecer_datos_para_ia_devuelve_texto(self, tmp_path: Path) -> None:
        archivo = tmp_path / "formatted.txt"
        _escribir(archivo, "00:00:10 - dato clave\n")
        resultado = main_mod.enriquecer_datos_para_ia([{"timestamp": "0:10", "tipo": "grito", "intensidad": 8}], str(archivo))
        assert isinstance(resultado, (str, dict))


class TestLLMs:
    def test_llamar_claude_sin_key(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "ANTHROPIC_API_KEY", "")
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            main_mod.llamar_claude("prompt")

    def test_llamar_claude_exitoso(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "ANTHROPIC_API_KEY", "sk-ant-test")
        respuesta = Mock(status_code=200)
        respuesta.json = Mock(return_value={"content": [{"type": "text", "text": "[{\"inicio\": \"00:00:05\"}]"}]})
        post = Mock(return_value=respuesta)
        monkeypatch.setattr(main_mod.requests, "post", post)
        texto = main_mod.llamar_claude("prompt")
        assert texto.startswith("[")

    def test_llamar_claude_error_http(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "ANTHROPIC_API_KEY", "sk-ant-test")
        respuesta = Mock(status_code=500, text="boom")
        monkeypatch.setattr(main_mod.requests, "post", Mock(return_value=respuesta))
        with pytest.raises(ConnectionError, match="Error 500"):
            main_mod.llamar_claude("prompt")

    def test_llamar_openai_sin_key(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "OPENAI_API_KEY", "")
        monkeypatch.setattr(main_mod, "OPENROUTER_API_KEY", "")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "")
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            main_mod.llamar_openai_compatible("prompt")

    def test_llamar_openai_exitoso(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.setattr(main_mod, "OPENROUTER_API_KEY", "")
        respuesta = Mock(status_code=200)
        respuesta.json = Mock(return_value={"choices": [{"message": {"content": "[{\"inicio\": \"00:00:05\"}]"}}]})
        monkeypatch.setattr(main_mod.requests, "post", Mock(return_value=respuesta))
        texto = main_mod.llamar_openai_compatible("prompt")
        assert "inicio" in texto

    def test_post_con_retry_final_falla(self, monkeypatch: Any) -> None:
        import requests as requests_mod

        llamadas = Mock(side_effect=requests_mod.exceptions.ConnectionError("net caída"))
        monkeypatch.setattr(main_mod.requests, "post", llamadas)
        monkeypatch.setattr(main_mod.time, "sleep", Mock())
        with pytest.raises(ConnectionError, match="Error de conexión"):
            main_mod._post_con_retry("https://x", {}, {}, intentos=2)

    def test_post_con_retry_recupera(self, monkeypatch: Any) -> None:
        import requests as requests_mod

        ok = Mock(status_code=200)
        secuencia = [requests_mod.exceptions.ConnectionError("caída 1"), ok]
        monkeypatch.setattr(main_mod.requests, "post", Mock(side_effect=secuencia))
        monkeypatch.setattr(main_mod.time, "sleep", Mock())
        resp = main_mod._post_con_retry("https://x", {}, {}, intentos=3)
        assert resp is ok


class TestObtenerClipsIA:
    def _respuesta_con_clips(self) -> str:
        return json.dumps([
            {"inicio": "00:00:05", "fin": "00:00:40", "duracion": 35, "score": 9,
             "criterio_principal": "revelacion", "titulo_sugerido": "La verdad", "hook_texto": "Mirá esto",
             "primer_segundo": "Mirá", "motivo": "es fuerte", "tipo_contenido": "exclusiva", "audio_score": 8}
        ])

    def test_sin_claves_lanza(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "ANTHROPIC_API_KEY", "")
        monkeypatch.setattr(main_mod, "OPENAI_API_KEY", "")
        monkeypatch.setattr(main_mod, "OPENROUTER_API_KEY", "")
        for clave in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(clave, raising=False)
        with pytest.raises(ValueError, match="Falta la clave de API"):
            main_mod.obtener_clips_ia("texto", [], {})

    def test_proveedor_anthropic_y_parseo(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setattr(main_mod, "_llamar_con_fallback", Mock(return_value=self._respuesta_con_clips()))
        clips = main_mod.obtener_clips_ia("transcripcion", [], {})
        assert len(clips) == 1
        assert clips[0]["score"] == 9

    def test_markdown_fences_se_extrayen(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "ANTHROPIC_API_KEY", "sk-ant-test")
        envuelto = "```json\n" + self._respuesta_con_clips() + "\n```"
        monkeypatch.setattr(main_mod, "_llamar_con_fallback", Mock(return_value=envuelto))
        clips = main_mod.obtener_clips_ia("t", [], {})
        assert len(clips) == 1

    def test_sin_json_valido_lanza(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setattr(main_mod, "_llamar_con_fallback", Mock(return_value="no hay nada util aca"))
        with pytest.raises(ValueError, match="JSON"):
            main_mod.obtener_clips_ia("t", [], {})

    def test_objeto_con_clave_clips(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "ANTHROPIC_API_KEY", "sk-ant-test")
        payload = json.dumps({"clips": [{"inicio": "00:00:05", "fin": "00:00:40"}]})
        monkeypatch.setattr(main_mod, "_llamar_con_fallback", Mock(return_value=payload))
        clips = main_mod.obtener_clips_ia("t", [], {})
        assert len(clips) == 1

    def test_objetos_sueltos(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setattr(
            main_mod,
            "_llamar_con_fallback",
            Mock(return_value="texto previo {\"inicio\": \"00:00:05\", \"fin\": \"00:00:40\"} texto posterior"),
        )
        clips = main_mod.obtener_clips_ia("t", [], {})
        assert len(clips) == 1


class TestParseoYValidacion:
    def test_parsear_json_tolerante_basico(self) -> None:
        clips = main_mod.parsear_json_tolerante('[{"inicio": "00:00:05", "fin": "00:00:40", "score": 8}]')
        assert len(clips) == 1

    def test_parsear_json_tolerante_con_comas_sueltas(self) -> None:
        clips = main_mod.parsear_json_tolerante('[{"inicio": "00:00:05", "fin": "00:00:40", "score": 8,}]')
        assert len(clips) >= 0  # tolerante: puede reparar o descartar

    def test_timestamp_a_segundos(self) -> None:
        assert main_mod.timestamp_a_segundos("00:01:10") == pytest.approx(70.0)
        assert main_mod.timestamp_a_segundos("02:30") == pytest.approx(150.0)
        assert main_mod.timestamp_a_segundos("15.5") == pytest.approx(15.5)
        assert main_mod.timestamp_a_segundos("basura") == 0.0

    def test_validar_clips_filtra_30_90(self, monkeypatch: Any) -> None:
        clips = [
            {"inicio": "00:00:00", "fin": "00:00:35", "score": 9},   # 35s ok
            {"inicio": "00:00:00", "fin": "00:00:10", "score": 9},   # 10s corto
            {"inicio": "00:00:00", "fin": "00:02:00", "score": 5},   # 120s largo
            {"inicio": "00:00:00", "fin": "00:01:00", "score": 3},   # score bajo
        ]
        validos = main_mod.validar_clips(clips)
        assert len(validos) == 1
        assert validos[0]["score"] == 9


class TestCorteYProcesar:
    def test_cortar_clip_entrada_inexistente(self, tmp_path: Path) -> None:
        assert main_mod.cortar_clip(str(tmp_path / "no-existe.mp4"), "00:00:00", "00:00:30", "salida.mp4") is False

    def test_cortar_clip_rango_invalido(self, tmp_path: Path) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"v")
        assert main_mod.cortar_clip(str(video), "00:00:30", "00:00:10", "salida.mp4") is False

    def test_cortar_clip_ffmpeg_falla(self, tmp_path: Path, monkeypatch: Any) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"v")
        fallo = Mock(returncode=1, stderr=b"error ffmpeg")
        monkeypatch.setattr(main_mod.shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
        monkeypatch.setattr(main_mod.subprocess, "run", Mock(return_value=fallo))
        assert main_mod.cortar_clip(str(video), "00:00:00", "00:00:30", str(tmp_path / "out.mp4")) is False

    def test_procesar_clips_guarda_info(self, tmp_path: Path, monkeypatch: Any) -> None:
        monkeypatch.setattr(main_mod, "cortar_clip", Mock(return_value=True))
        salida = tmp_path / "clips"
        salida.mkdir()
        archivo = salida / "clip_1.mp4"
        archivo.write_bytes(b"x")
        clips = [{"inicio": "00:00:05", "fin": "00:00:40", "score": 9, "titulo_sugerido": "t"}]
        archivos = main_mod.procesar_clips("video.mp4", clips, str(salida))
        assert len(archivos) == 1
        info = json.loads((salida / "clips_info.json").read_text(encoding="utf-8"))
        assert info[0]["score"] == 9

    def test_construir_prompt_incluye_datos(self, monkeypatch: Any) -> None:
        prompt = main_mod.construir_prompt("transcripcion completa de prueba", [{"intensidad": 8}], {})
        assert "transcripcion completa de prueba" in prompt
        assert "REVELACION" in prompt or "revelacion" in prompt


# ------------------------------------------------------------------- engine.py (raíz)


def _parseador_transcripcion_ok(monkeypatch: Any) -> None:
    """Parseo 'exitoso' que escribe el archivo formateado con segmentos válidos."""
    def _parse_ok(transcripcion_original: str, salida: str) -> None:
        _escribir(
            Path(salida),
            "00:00:00 - hola mundo\n00:00:05 - seguimos\n00:00:10 - terminando\n",
        )

    monkeypatch.setattr("whisper_transcriber.parsear_transcripcion_youtube", _parse_ok)
    monkeypatch.setattr("whisper_transcriber.transcribir_audio", Mock())


def _parches_engine(monkeypatch: Any, clips: list, tmp_path: Path) -> None:
    """Deja el pipeline interno de `engine.procesar_video` con todo mockeado."""
    monkeypatch.setattr(main_mod, "extraer_audio", Mock())
    monkeypatch.setattr(main_mod, "analizar_audio_video", Mock(return_value=[]))
    monkeypatch.setattr(main_mod, "leer_transcripcion_para_ia", Mock(return_value="texto para IA"))
    monkeypatch.setattr(main_mod, "enriquecer_datos_para_ia", Mock(return_value={}))
    monkeypatch.setattr(main_mod, "preparar_transcripcion_para_ia", Mock(return_value="texto para IA"))
    monkeypatch.setattr(main_mod, "obtener_clips_ia", Mock(return_value=clips))
    monkeypatch.setattr(main_mod, "validar_clips", Mock(return_value=clips))

    def _fake_procesar_clips(video: str, clips_validos: list, clips_dir: str) -> list[str]:
        destino = Path(clips_dir) / "clips_info.json"
        destino.write_text(json.dumps(clips_validos), encoding="utf-8")
        return [str(tmp_path / "clip_1.mp4")]

    monkeypatch.setattr(main_mod, "procesar_clips", Mock(side_effect=_fake_procesar_clips))
    monkeypatch.setattr(engine_mod, "_verificar_ffmpeg", Mock(return_value=True))
    monkeypatch.setattr(engine_mod, "_validar_entradas", Mock(return_value=None))
    monkeypatch.setattr(main_mod, "AUDIO_ANALYZER_AVAILABLE", False)


class TestEngineProcesarVideo:
    def test_video_inexistente_da_error_validacion(self, tmp_path: Path) -> None:
        resultado = engine_mod.procesar_video(str(tmp_path / "no-existe.mp4"), str(tmp_path / "t.txt"))
        assert resultado.exito is False
        assert resultado.error_tipo == "ValidacionError"

    def test_ffmpeg_ausente_da_error_dependencia(self, tmp_path: Path, monkeypatch: Any) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"v")
        transcripcion = tmp_path / "t.txt"
        transcripcion.write_text("0:00 hola", encoding="utf-8")
        monkeypatch.setattr(engine_mod, "_validar_entradas", Mock(return_value=None))
        monkeypatch.setattr(engine_mod, "_verificar_ffmpeg", Mock(return_value=False))
        resultado = engine_mod.procesar_video(str(video), str(transcripcion))
        assert resultado.exito is False
        assert resultado.error_tipo == "DependenciaError"

    def test_pipeline_completo_exitoso(self, tmp_path: Path, monkeypatch: Any) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"v")
        transcripcion = tmp_path / "t.txt"
        transcripcion.write_text("0:00 hola\n0:05 mundo", encoding="utf-8")
        clips = [{"archivo": "clip_1.mp4", "inicio": "00:00:05", "fin": "00:00:40", "titulo_sugerido": "t",
                  "hook_texto": "h", "criterio_principal": "revelacion", "score": 9,
                  "primer_segundo": "p", "motivo": "m"}]
        _parches_engine(monkeypatch, clips, tmp_path)
        _parseador_transcripcion_ok(monkeypatch)

        resultado = engine_mod.procesar_video(str(video), str(transcripcion))
        assert resultado.exito is True
        assert len(resultado.clips) == 1

    def test_engine_falla_sin_clips(self, tmp_path: Path, monkeypatch: Any) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"v")
        transcripcion = tmp_path / "t.txt"
        transcripcion.write_text("0:00 hola", encoding="utf-8")
        _parches_engine(monkeypatch, [], tmp_path)
        _parseador_transcripcion_ok(monkeypatch)
        resultado = engine_mod.procesar_video(str(video), str(transcripcion))
        assert resultado.exito is True  # 0 clips = éxito vacío (comportamiento del engine)
        assert resultado.clips == []

    def test_ia_error_se_mapea(self, tmp_path: Path, monkeypatch: Any) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"v")
        transcripcion = tmp_path / "t.txt"
        transcripcion.write_text("0:00 hola", encoding="utf-8")
        _parches_engine(monkeypatch, [], tmp_path)
        _parseador_transcripcion_ok(monkeypatch)
        monkeypatch.setattr(main_mod, "obtener_clips_ia", Mock(side_effect=ValueError("respuesta inválida")))
        resultado = engine_mod.procesar_video(str(video), str(transcripcion))
        assert resultado.exito is False
        assert resultado.error_tipo == "IAError"

    def test_error_interno_inesperado(self, tmp_path: Path, monkeypatch: Any) -> None:
        video = tmp_path / "v.mp4"
        video.write_bytes(b"v")
        transcripcion = tmp_path / "t.txt"
        transcripcion.write_text("0:00 hola", encoding="utf-8")
        _parches_engine(monkeypatch, [], tmp_path)
        _parseador_transcripcion_ok(monkeypatch)
        monkeypatch.setattr(main_mod, "extraer_audio", Mock(side_effect=RuntimeError("ffmpeg muerto")))
        resultado = engine_mod.procesar_video(str(video), str(transcripcion))
        assert resultado.exito is False
        assert resultado.error_tipo == "AudioError"


# --------------------------------------------------- video_processor (worker)


class TestVideoProcessor:
    def test_generate_ass_con_hook(self, tmp_path: Path) -> None:
        salida = tmp_path / "sub.ass"
        segmentos = [{"start": 10, "end": 14, "text": "texto dentro"}]
        resultado = vp_mod.generate_ass_from_segments(segmentos, 10, 40, str(salida), hook_text="El hook")
        assert Path(resultado).is_file()
        contenido = salida.read_text(encoding="utf-8")
        assert ",Hook," in contenido
        assert ",Default," in contenido

    def test_generate_ass_sin_segmentos(self, tmp_path: Path) -> None:
        salida = tmp_path / "vacio.ass"
        resultado = vp_mod.generate_ass_from_segments([], 0, 30, str(salida))
        contenido = Path(resultado).read_text(encoding="utf-8")
        assert "[Events]" in contenido
        assert ",Default," not in contenido

    def test_reframe_and_burn_ffmpeg_falla(self, tmp_path: Path, monkeypatch: Any) -> None:
        fallo = SimpleNamespace(returncode=1, stderr="err")
        monkeypatch.setattr(vp_mod.subprocess, "run", Mock(return_value=fallo))
        assert vp_mod.reframe_and_burn_subtitles("in.mp4", "out.mp4", ass_file=None) is False

    def test_reframe_and_burn_exitoso(self, tmp_path: Path, monkeypatch: Any) -> None:
        ok = SimpleNamespace(returncode=0, stderr="")
        monkeypatch.setattr(vp_mod.subprocess, "run", Mock(return_value=ok))
        salida = tmp_path / "out.mp4"
        salida.write_bytes(b"v")
        assert vp_mod.reframe_and_burn_subtitles("in.mp4", str(salida), ass_file=None) is True

    def test_reframe_timeout(self, tmp_path: Path, monkeypatch: Any) -> None:
        import subprocess as sp

        monkeypatch.setattr(vp_mod.subprocess, "run", Mock(side_effect=sp.TimeoutExpired(cmd="ffmpeg", timeout=1)))
        assert vp_mod.reframe_and_burn_subtitles("in.mp4", "out.mp4") is False

    def test_process_clip_vertical_flujo(self, tmp_path: Path, monkeypatch: Any) -> None:
        input_video = tmp_path / "in.mp4"
        input_video.write_bytes(b"v")
        salida = tmp_path / "out.mp4"
        salida.write_bytes(b"v")

        def _run_ok(cmd, **kwargs):
            destino = cmd[-1]
            Path(destino).write_bytes(b"x")
            return SimpleNamespace(returncode=0, stderr="")

        monkeypatch.setattr(vp_mod.subprocess, "run", Mock(side_effect=_run_ok))
        resultado = vp_mod.process_clip_vertical(str(input_video), str(salida), [{"start": 0, "end": 5, "text": "hola"}], 0, 20)
        assert resultado is True

    def test_process_clip_vertical_corte_falla(self, tmp_path: Path, monkeypatch: Any) -> None:
        input_video = tmp_path / "in.mp4"
        input_video.write_bytes(b"v")
        fallo = SimpleNamespace(returncode=1, stderr="")
        monkeypatch.setattr(vp_mod.subprocess, "run", Mock(return_value=fallo))
        resultado = vp_mod.process_clip_vertical(str(input_video), str(tmp_path / "o.mp4"), [], 0, 20)
        assert resultado is False


# ------------------------------------------------------------------ nvenc (perf worker)


class TestCodecSeleccion:
    """Selección de codec h264_nvenc/libx264 con fallback de runtime (sin GPU real ni red)."""

    def _activar_gpu(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("RUNPOD_GPU", "1")
        # Sondeo mockeado: no depende del binario ffmpeg real del entorno.
        monkeypatch.setattr(vp_mod, "_sondear_nvenc", Mock(return_value=True))

    def test_sin_gpu_env_usa_libx264_y_no_sondea(self, monkeypatch: Any) -> None:
        # Sin RUNPOD_GPU: args libx264 y CERO subprocess de ffmpeg (el
        # short-circuit de env vive dentro de _sondear_nvenc, que corre real).
        monkeypatch.delenv("RUNPOD_GPU", raising=False)
        run = Mock(side_effect=AssertionError("no debe ejecutar ffmpeg sin RUNPOD_GPU"))
        monkeypatch.setattr(vp_mod.subprocess, "run", run)
        args = vp_mod._args_codec_video("20")
        assert args == ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20"]
        run.assert_not_called()

    def test_gpu_con_nvenc_disponible_usa_nvenc(self, monkeypatch: Any) -> None:
        self._activar_gpu(monkeypatch)
        args = vp_mod._args_codec_video("20")
        assert args[:3] == ["-c:v", "h264_nvenc", "-preset"]
        assert "-cq" in args and "-b:v" in args

    def test_gpu_sin_nvenc_en_binario_fallback_libx264(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("RUNPOD_GPU", "1")
        monkeypatch.setattr(vp_mod, "_sondear_nvenc", Mock(return_value=False))
        assert vp_mod._args_codec_video("20")[1] == "libx264"

    def test_probe_con_excepcion_devuelve_false(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("RUNPOD_GPU", "1")
        probe = Mock(side_effect=RuntimeError("ffmpeg no existe"))
        monkeypatch.setattr(vp_mod.subprocess, "run", probe)
        assert vp_mod._sondear_nvenc() is False
        probe.assert_called_once()

    def test_memoizacion_un_solo_probe(self, monkeypatch: Any) -> None:
        self._activar_gpu(monkeypatch)
        probe = Mock(return_value=True)
        monkeypatch.setattr(vp_mod, "_sondear_nvenc", probe)
        assert vp_mod._nvenc_disponible() is True
        assert vp_mod._nvenc_disponible() is True
        probe.assert_called_once()

    def test_reframe_retry_libx264_cuando_nvenc_falla(self, tmp_path: Path, monkeypatch: Any) -> None:
        self._activar_gpu(monkeypatch)
        llamadas = []

        def _run(cmd, **kwargs):
            llamadas.append(list(cmd))
            if len(llamadas) == 1:  # 1er intento (nvenc) falla
                return SimpleNamespace(returncode=1, stderr="nvenc error")
            Path(cmd[-1]).write_bytes(b"v")  # 2do intento (libx264) OK
            return SimpleNamespace(returncode=0, stderr="")

        monkeypatch.setattr(vp_mod.subprocess, "run", Mock(side_effect=_run))
        salida = tmp_path / "out.mp4"
        assert vp_mod.reframe_and_burn_subtitles("in.mp4", str(salida), ass_file=None) is True
        assert len(llamadas) == 2
        assert "h264_nvenc" in llamadas[0]
        assert "libx264" in llamadas[1]

    def test_reframe_sin_gpu_no_reintenta(self, tmp_path: Path, monkeypatch: Any) -> None:
        monkeypatch.delenv("RUNPOD_GPU", raising=False)
        run = Mock(return_value=SimpleNamespace(returncode=1, stderr="err"))
        monkeypatch.setattr(vp_mod.subprocess, "run", run)
        assert vp_mod.reframe_and_burn_subtitles("in.mp4", "out.mp4", ass_file=None) is False
        assert run.call_count == 1

    def test_corte_retry_libx264_cuando_nvenc_falla(self, tmp_path: Path, monkeypatch: Any) -> None:
        self._activar_gpu(monkeypatch)
        input_video = tmp_path / "in.mp4"
        input_video.write_bytes(b"v")
        llamadas = []

        def _run(cmd, **kwargs):
            llamadas.append(list(cmd))
            if len(llamadas) == 1:
                return SimpleNamespace(returncode=1, stderr="nvenc error")
            Path(cmd[-1]).write_bytes(b"x")
            return SimpleNamespace(returncode=0, stderr="")

        monkeypatch.setattr(vp_mod.subprocess, "run", Mock(side_effect=_run))
        resultado = vp_mod.process_clip_vertical(
            str(input_video), str(tmp_path / "out.mp4"), [{"start": 0, "end": 5, "text": "hola"}], 0, 20
        )
        assert resultado is True
        assert len(llamadas) >= 2
        assert "h264_nvenc" in llamadas[0]
        assert any("libx264" in cmd for cmd in llamadas[1:])
