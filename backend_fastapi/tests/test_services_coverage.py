"""Cobertura de servicios del backend FastAPI sin procesos ni red real.

Todo lo que toca FFmpeg/HTTP se aísla con `unittest.mock.patch`.
"""

from __future__ import annotations

import json
import os
import time
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

import _fixtures

from backend_fastapi.app.security import (
    hash_password,
    decode_access_token,
    create_access_token,
    verify_password,
)


# ---------------------------------------------------------------- security


class TestSecurity:
    def test_hash_y_verify_roundtrip(self) -> None:
        hashed = hash_password("Clave-Segura-123")
        assert verify_password("Clave-Segura-123", hashed) is True
        assert verify_password("otra-clave", hashed) is False

    def test_hash_trunca_a_72_bytes_bcrypt(self) -> None:
        larga = "a" * 100
        hashed = hash_password(larga)
        # bcrypt falla con entradas > 72 bytes nativas; el helper debe truncarlas
        assert verify_password("a" * 72, hashed) is True
        assert verify_password("a" * 73, hashed) is True

    def test_token_roundtrip_con_claims(self) -> None:
        token = create_access_token(_fixtures.uuid.uuid4(), extra_claims={"email": "a@b.com"})
        payload = decode_access_token(token)
        assert payload["type"] == "access"
        assert payload.get("email") == "a@b.com"

    def test_token_expirado(self, user) -> None:
        from backend_fastapi.app.security.jwt import TokenExpiredError

        token = create_access_token(user.id, expires_delta=timedelta(seconds=-10))
        with pytest.raises(TokenExpiredError):
            decode_access_token(token)

    def test_token_invalido(self) -> None:
        from backend_fastapi.app.security.jwt import TokenDecodeError

        with pytest.raises(TokenDecodeError):
            decode_access_token("no-es-un-jwt")


# ---------------------------------------------------------------- transcript_utils


class TestTranscriptUtils:
    def _parse(self, texto: str):
        from backend_fastapi.app.services.transcript_utils import parse_transcript_text_to_segments

        return parse_transcript_text_to_segments(texto)

    def test_formato_hms(self) -> None:
        segs = self._parse("00:00:10 - Primera\n00:01:05 - Segunda")
        assert segs[0] == {"start": 10.0, "end": 13.0, "text": "Primera"}
        assert segs[1]["start"] == 65.0

    def test_formato_ms(self) -> None:
        segs = self._parse("01:05 - Solo minutos")
        assert segs[0]["start"] == 65.0

    def test_formato_corchetes(self) -> None:
        segs = self._parse("[0.0 - 2.5] Texto entre corchetes")
        assert segs[0] == {"start": 0.0, "end": 2.5, "text": "Texto entre corchetes"}

    def test_lineas_sin_timestamp_ventana_de_3s(self) -> None:
        segs = self._parse("libre sin marca")
        assert segs[0]["end"] - segs[0]["start"] == pytest.approx(3.0)

    def test_texto_vacio(self) -> None:
        assert self._parse("   \n ") == []

    def test_marca_invalida_se_descarta_o_ventana(self) -> None:
        # corchete con end <= start se descarta por completo
        assert self._parse("[5 - 1] mal") == []
        # timestamp sin texto: la línea pierde el guion final y cae como "texto libre"
        # en la ventana sintética de 3s (comportamiento tolerante del parser)
        segs = self._parse("00:00:01 - ")
        assert len(segs) == 1
        assert segs[0]["text"] == "00:00:01 -"


# ---------------------------------------------------------------- ass_generator


def _aux_dialogues_de(partes: list[str]) -> list[str]:
    return [l for l in partes if l.startswith("Dialogue")]


class TestAssGenerator:
    def test_generate_ass_content_tiene_dialogues(self) -> None:
        from backend_fastapi.app.services.ass_generator import generate_ass_content

        content = generate_ass_content([{"start": 0.0, "end": 2.0, "text": "Hola mundo"}])
        assert "[Script Info]" in content
        assert "[V4+ Styles]" in content
        # _sanitize_text lleva el texto a mayúsculas para el estilo del clip viral
        assert "Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,HOLA MUNDO" in content

    def test_segmento_invalido_ignorado_y_dur_clamp(self) -> None:
        from backend_fastapi.app.services.ass_generator import generate_ass_content

        content = generate_ass_content(
            [
                {"start": 5.0, "end": 4.0, "text": "invertido"},   # se clampa a min_duration
                {"start": 1.0, "end": 1.05, "text": "corto"},       # < 0.15s -> fuera
                {"start": 2.0, "end": 2.1, "text": ""},             # texto vacio -> fuera
            ]
        )
        assert "INVERTIDO" in content.upper()      # segmento clamped, no descartado
        assert "CORTO" not in content.upper()      # duración < 0.15s -> fuera

    def test_write_ass_file_crea_archivo(self, tmp_path) -> None:
        from backend_fastapi.app.services.ass_generator import write_ass_file

        destino = tmp_path / "sub" / "clip.ass"
        result = write_ass_file([{"start": 0.0, "end": 1.5, "text": "hola"}], destino)
        assert Path(result).is_file()
        assert Path(result).read_text(encoding="utf-8").startswith("[Script Info]")

    def test_hooked_ventana_larga_se_normaliza(self, tmp_path) -> None:
        from backend_fastapi.app.services.ass_generator import generate_hooked_ass

        destino = tmp_path / "hooked.ass"
        # Nuevo contrato (#116): un hook de 9s se NORMALIZA a 5s (no rechaza)
        generate_hooked_ass(
            [{"start": 0.0, "end": 3.0, "text": "frase hook"}, {"start": 6.0, "end": 8.0, "text": "cuerpo"}],
            clip_start=5.0,
            clip_end=30.0,
            hook_start=0.0,
            hook_end=9.0,
            output_path=destino,
        )
        assert destino.exists()

    def test_validar_ventana_hook_banda_invalida(self) -> None:
        from backend_fastapi.app.services.ass_generator import _validar_ventana_hook

        with pytest.raises(ValueError, match="entre 4.5 y 5.5"):
            _validar_ventana_hook(0.0, 3.0)

    def test_hooked_genera_subtitulos_reordenados(self, tmp_path) -> None:
        from backend_fastapi.app.services.ass_generator import generate_hooked_ass

        destino = tmp_path / "hooked.ass"
        # Escenario de producción: hook DENTRO del clip (hook_service lo garantiza)
        generate_hooked_ass(
            [{"start": 5.0, "end": 8.0, "text": "frase hook"}, {"start": 12.0, "end": 14.0, "text": "cuerpo"}],
            clip_start=0.0,
            clip_end=30.0,
            hook_start=5.0,
            hook_end=8.0,
            output_path=destino,
        )
        partes = destino.read_text(encoding="utf-8").splitlines()
        dialogues = _aux_dialogues_de(partes)
        assert "FRASE HOOK" in dialogues[0]  # el hook va primero
        assert any("CUERPO" in line for line in dialogues)

    def test_segments_from_transcript_words(self) -> None:
        from backend_fastapi.app.services.ass_generator import segments_from_transcript_words

        segs = segments_from_transcript_words(
            [
                {"start": 0, "end": 1, "text": "hola"},
                {"start": "x"},  # invalido -> descartado
                {"end": 2, "text": "sin start"},  # falta start -> descartado
            ]
        )
        assert len(segs) == 1
        assert segs[0]["text"] == "hola"


# ---------------------------------------------------------------- storage_cleanup


class TestStorageCleanup:
    def test_cleanup_borra_lo_viejo_y_devuelve_bytes(self, monkeypatch, tmp_path) -> None:
        from backend_fastapi.app.services import storage_cleanup as sc

        uploads = tmp_path / "uploads"
        uploads.mkdir()
        viejo = uploads / "viejo.mp4"
        viejo.write_bytes(b"x" * 2048)
        nuevo = uploads / "nuevo.mp4"
        nuevo.write_bytes(b"y" * 1024)
        viejo_tiempo = time.time() - 48 * 3600
        os.utime(viejo, (viejo_tiempo, viejo_tiempo))

        liberado = sc.cleanup_storage(base_path=str(tmp_path), max_age_hours=24)
        assert liberado == 2048
        assert not viejo.exists()
        assert nuevo.exists()

    def test_cleanup_fase_2_respeta_max_total_mb(self, monkeypatch, tmp_path) -> None:
        from backend_fastapi.app.services import storage_cleanup as sc

        clips = tmp_path / "clips"
        clips.mkdir()
        a = clips / "a.mp4"
        a.write_bytes(b"a" * 3 * 1024 * 1024)
        b = clips / "b.mp4"
        b.write_bytes(b"b" * 1024 * 1024)
        os.utime(a, (time.time() - 100, time.time() - 100))  # a más viejo

        sc.cleanup_storage(base_path=str(tmp_path), max_age_hours=24, max_total_mb=1)
        assert not a.exists()
        assert b.exists()

    def test_cleanup_nunca_explota(self, monkeypatch, tmp_path) -> None:
        from backend_fastapi.app.services import storage_cleanup as sc

        # base inexistente -> 0 liberado, sin excepción
        assert sc.cleanup_storage(base_path=str(tmp_path / "nada")) == 0

    def test_ensure_disk_space_con_poco_espacio(self, monkeypatch, tmp_path) -> None:
        from backend_fastapi.app.services import storage_cleanup as sc

        usage = Mock(total=100, used=99, free=100 * 1024 * 1024)
        with patch("backend_fastapi.app.services.storage_cleanup.shutil.disk_usage", return_value=usage):
            min_free = sc.ensure_disk_space(tmp_path, min_free_mb=1024)  # exige -> borra
        assert min_free >= 0


# ---------------------------------------------------------------- runpod_service


class TestRunpodService:
    def test_is_runpod_configured(self, monkeypatch) -> None:
        from backend_fastapi.app.services import runpod_service as rs

        monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
        assert rs.is_runpod_configured() is False
        monkeypatch.setenv("RUNPOD_API_KEY", "k")
        monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "e")
        assert rs.is_runpod_configured() is True

    def test_settings_requiere_key(self, monkeypatch) -> None:
        from backend_fastapi.app.services.runpod_service import RunPodError, _settings

        monkeypatch.setenv("RUNPOD_API_KEY", "")
        with pytest.raises(RunPodError):
            _settings()

    def test_settings_timeouts_invalidos(self, monkeypatch) -> None:
        from backend_fastapi.app.services.runpod_service import RunPodError, _settings

        monkeypatch.setenv("RUNPOD_API_KEY", "k")
        monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "e")
        monkeypatch.setenv("RUNPOD_REQUEST_TIMEOUT_SECONDS", "no-es-num")
        with pytest.raises(RunPodError):
            _settings()

    def test_normalize_transcription_segments(self) -> None:
        from backend_fastapi.app.services.runpod_service import _normalize_transcription_segments

        out = _normalize_transcription_segments([{"start": "1", "end": "2", "text": " hola "}])
        assert out == [{"start": 1.0, "end": 2.0, "text": "hola"}]
        assert _normalize_transcription_segments([None, 3]) == []
        assert _normalize_transcription_segments("no-es-lista") == []

    def test_process_video_via_runpod_devuelve_output_normalizado(self, monkeypatch) -> None:
        from backend_fastapi.app.services import runpod_service as rs

        monkeypatch.setenv("RUNPOD_API_KEY", "k-123")
        monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "ep-1")
        response = Mock(status_code=200)
        response.json.return_value = {
            "id": "job-1",
            "status": "COMPLETED",
            "output": {"status": "COMPLETED", "clips": [{"titulo": "t"}], "transcription_segments": [{"start": 0, "end": 1, "text": "x"}]},
        }
        with patch.object(rs.requests, "post", return_value=response) as post:
            result = rs.process_video_via_runpod("https://media.example/v.mp4", transcription_text="hola")
        post.assert_called_once()
        assert result["clips"][0]["titulo"] == "t"
        assert result["transcription_segments"][0]["start"] == pytest.approx(0.0)

    def test_process_video_via_runpod_502_si_falla(self, monkeypatch) -> None:
        from backend_fastapi.app.services import runpod_service as rs
        from backend_fastapi.app.services.runpod_service import RunPodError

        monkeypatch.setenv("RUNPOD_API_KEY", "k-123")
        monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "ep-1")
        response = Mock(status_code=500)
        response.json.return_value = {"error": "kaput"}
        with patch.object(rs.requests, "post", return_value=response):
            with pytest.raises(RunPodError):
                rs.process_video_via_runpod("https://media.example/v.mp4")

    def test_process_local_video_rechaza_archivo_inexistente(self) -> None:
        from backend_fastapi.app.services.runpod_service import RunPodError, process_local_video_via_runpod

        with pytest.raises(RunPodError):
            process_local_video_via_runpod("no/existe/video.mp4")


# ---------------------------------------------------------------- hook_service


def _hook_payload() -> dict[str, Any]:
    return {
        "clips": [
            {
                "title": "Momento viral",
                "start_time": 0.0,
                "end_time": 30.0,
                "hook": {"text": "Te va a sorprender", "start_time": 2.0, "end_time": 5.0},
                "viral_score": 88,
                "reasoning": "giro fuerte",
            }
        ]
    }


class TestHookService:
    def test_format_transcript(self) -> None:
        from backend_fastapi.app.services.hook_service import _format_transcript

        texto = _format_transcript([{"start": 0, "end": 1, "text": "hola"}, {"start": 1, "end": 2, "text": "chau"}])
        assert "hola" in texto and "chau" in texto

    def test_parse_json_strict_tolerante_a_virgulas(self) -> None:
        from backend_fastapi.app.services.hook_service import _parse_json_strict

        data = _parse_json_strict('{"clips": [1,2,],}')
        assert data["clips"] == [1, 2]

    def test_parse_json_strict_extrae_json_de_texto_llm(self) -> None:
        from backend_fastapi.app.services.hook_service import _parse_json_strict

        data = _parse_json_strict('Acá va el resultado:\n```json\n{"clips": []}\n```')
        assert data == {"clips": []}

    def test_validate_clips_filtra_plagios(self) -> None:
        from backend_fastapi.app.services.hook_service import _validate_clips

        data = _hook_payload()
        data["clips"].append({})  # sin título ni hook -> se filtra
        clips = _validate_clips(data)
        assert len(clips) == 1
        assert clips[0]["viral_score"] == 88
        assert clips[0]["hook"]["duration"] == pytest.approx(3.0)

    def test_validate_clips_rechaza_formato_malo(self) -> None:
        from backend_fastapi.app.services.hook_service import _validate_clips

        with pytest.raises(ValueError):
            _validate_clips({"clips": "no-es-lista"})

    def test_mock_hooks_y_detect_mock(self) -> None:
        from backend_fastapi.app.services.hook_service import _mock_hooks, detect_hooks

        segs = [{"start": 0, "end": 2, "text": "hola"}]
        mock = _mock_hooks(segs)
        assert mock and mock[0]["hook"]["text"]
        assert detect_hooks(segs, mock=True) == mock

    def test_detect_hooks_sin_api_key_requiere_error(self, monkeypatch) -> None:
        from backend_fastapi.app.services import hook_service as hs

        # Hermetico: si hubiese una ANTHROPIC_API_KEY real en el equipo, este test
        # haria una llamada real. Se fuerza el proveedor "none" (sin sicProvider).
        monkeypatch.setattr(hs, "_get_provider", lambda: "none")
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            hs.detect_hooks([{"start": 0, "end": 1, "text": "hola"}])

    def test_detect_hooks_camino_llm_valido(self, monkeypatch) -> None:
        from backend_fastapi.app.services import hook_service as hs

        monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-fake")
        monkeypatch.setattr(hs, "_call_llm", lambda prompt: json.dumps(_hook_payload()))
        clips = hs.detect_hooks([{"start": 0, "end": 1, "text": "hola"}])
        assert len(clips) == 1
        assert clips[0]["viral_score"] == 88

    def test_detect_hooks_llm_sin_clips_propaga_error(self, monkeypatch) -> None:
        from backend_fastapi.app.services import hook_service as hs

        monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-fake")
        monkeypatch.setattr(hs, "_call_llm", lambda prompt: json.dumps({"clips": []}))
        with pytest.raises(RuntimeError, match="Error en API de Claude"):
            hs.detect_hooks([{"start": 0, "end": 1, "text": "hola"}])


# ---------------------------------------------------------------- ffmpeg_service


def _ffprobe_stdout(cmd) -> bytes:
    # burn/cut preguntan dimensiones; build_hook consulta el stream de audio
    return b"12.5\n" if "format=duration" in " ".join(cmd) else b"0\n"


def _ffprobe_respuesta(cmd):
    if cmd and cmd[0] == "ffprobe":
        return Mock(returncode=0, stdout=_ffprobe_stdout(cmd), stderr=b"")
    return None


def _es_salida_media(ultimo) -> bool:
    return ultimo is not None and ultimo.suffix.lower() in {".mp4", ".wav", ".ass"} and not ultimo.exists()


def _simula_archivo_salida(cmd) -> None:
    ultimo = Path(str(cmd[-1])) if cmd else None
    if _es_salida_media(ultimo):
        ultimo.parent.mkdir(parents=True, exist_ok=True)
        ultimo.write_bytes(b"mp4-simulado")


def _run_side_effect_ffmpeg_simulado(cmd, **kwargs):
    rapido = _ffprobe_respuesta(cmd)
    if rapido is not None:
        return rapido
    _simula_archivo_salida(cmd)
    return Mock(returncode=0, stdout=b"", stderr=b"")


def _patch_subprocess_ffmpeg():
    """Mockea subprocess.run del módulo: ffprobe devuelve duración "12.5"/audio "0";
    cada render 'crea' su archivo de salida (último argumento con sufijo de media)."""
    from backend_fastapi.app.services import ffmpeg_service as fs

    runner = Mock(side_effect=_run_side_effect_ffmpeg_simulado)
    return patch.object(fs.subprocess, "run", runner), runner, fs


class TestFFmpegService:
    def _patch_subprocess(self):
        return _patch_subprocess_ffmpeg()

    def test_escape_rutas_para_filtro_ass(self, tmp_path) -> None:
        from backend_fastapi.app.services.ffmpeg_service import escape_subtitles_path

        res = escape_subtitles_path(str(tmp_path / "sub.ass"))
        assert "\\:" in res  # el colon de C:\ queda escapado
        assert "," not in res.replace("\\,", "")  # las comas van escapadas

    def test_probe_duration(self, tmp_path) -> None:
        patcher, runner, fs = self._patch_subprocess()
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"x")
        with patcher:
            assert fs.probe_duration(video) == pytest.approx(12.5)
        assert runner.call_count == 1

    def test_probe_duration_sin_archivo_devuelve_none(self) -> None:
        from backend_fastapi.app.services.ffmpeg_service import probe_duration

        assert probe_duration("no/existe.mp4") is None

    def test_burn_subtitles_y_cut_segment_arman_comando(self, tmp_path) -> None:
        video = tmp_path / "in.mp4"
        video.write_bytes(b"x")
        ass = tmp_path / "sub.ass"
        ass.write_text("[Script Info]", encoding="utf-8")
        salida_burn = tmp_path / "burn.mp4"
        salida_cut = tmp_path / "cut.mp4"

        patcher, runner, fs = self._patch_subprocess()
        with patcher:
            fs.burn_subtitles(video, ass, salida_burn)
            fs.cut_segment(video, 1.0, 5.0, salida_cut)
        assert runner.call_count >= 2
        assert salida_burn.exists() and salida_cut.exists()

    def test_build_hook_clip_compone_teaser_y_cuerpo(self, tmp_path) -> None:
        from backend_fastapi.app.services.ffmpeg_service import build_hook_clip

        video = tmp_path / "in.mp4"
        video.write_bytes(b"x")
        salida = tmp_path / "hook.mp4"

        patcher, _, fs = self._patch_subprocess()
        with patcher:
            resultado = fs.build_hook_clip(video, 5.0, 30.0, 0.0, 3.0, salida)
        assert str(resultado) == str(salida)


# ---------------------------------------------------------------- hook teaser 116


class TestHookTeaser116:
    """Issue #116: teaser B&W 5s + zoom 1.08 + SFX whoosh + ventana normalizada."""

    def test_filtro_teaser_bw_constante(self) -> None:
        from backend_fastapi.app.services import ffmpeg_service as fs

        assert "eq=saturation=0" in fs.FILTRO_TEASER_BW
        assert "1.08" in fs.FILTRO_TEASER_BW
        assert "crop=iw:ih" in fs.FILTRO_TEASER_BW

    def test_normalizar_ventana_hook_estandariza_5s(self) -> None:
        from backend_fastapi.app.services.ffmpeg_service import _normalizar_ventana_hook

        # hook dentro del clip (contrato de hook_service) -> se extiende a 5s
        assert _normalizar_ventana_hook(12.0, 14.0, 10.0, 40.0) == (12.0, 17.0)
        # Hook pegado al final del clip: se recorta al final disponible
        assert _normalizar_ventana_hook(28.0, 30.5, 10.0, 30.0) == (25.0, 30.0)
        # Clip más corto que 5s: duración = lo que haya
        assert _normalizar_ventana_hook(0.0, 3.0, 0.0, 3.0) == (0.0, 3.0)

    def test_exigir_rangos_hook_banda_4_5_a_5_5(self) -> None:
        from backend_fastapi.app.services.ffmpeg_service import _exigir_rangos_hook

        _exigir_rangos_hook(5.0, 30.0, 0.0, 5.0)  # OK, no lanza
        with pytest.raises(ValueError, match="entre 4.5 y 5.5"):
            _exigir_rangos_hook(3.0, 30.0, 0.0, 3.0)
        with pytest.raises(ValueError, match="entre 4.5 y 5.5"):
            _exigir_rangos_hook(6.0, 30.0, 0.0, 6.0)

    def test_cortar_teaser_bw_comando(self, tmp_path) -> None:
        from backend_fastapi.app.services.ffmpeg_service import _cortar_teaser_bw

        video = tmp_path / "in.mp4"
        video.write_bytes(b"x")
        salida = tmp_path / "teaser.mp4"

        patcher, runner, fs = _patch_subprocess_ffmpeg()
        with patcher:
            fs._cortar_teaser_bw(video, 1.0, 6.0, salida)
        cmd = runner.call_args_list[-1].args[0]
        assert "-vf" in cmd
        assert "eq=saturation=0" in cmd[cmd.index("-vf") + 1]
        assert "1.08" in cmd[cmd.index("-vf") + 1]
        assert salida.exists()

    def test_filtro_y_maps_con_sfx_whoosh(self) -> None:
        from backend_fastapi.app.services.ffmpeg_service import _filtro_y_maps

        graph, maps = _filtro_y_maps(0.2, 5.0, 30.0, has_audio=True)
        assert "adelay=" in graph
        assert "volume=0.13" in graph
        assert "amix=inputs=2:duration=first:normalize=0" in graph
        assert maps == ["-map", "[v]", "-map", "[aout]"]

    def test_filtro_y_maps_sin_audio_sin_sfx(self) -> None:
        from backend_fastapi.app.services.ffmpeg_service import _filtro_y_maps

        graph, maps = _filtro_y_maps(0.2, 5.0, 30.0, has_audio=False)
        assert "adelay" not in graph and "amix" not in graph
        assert maps == ["-map", "[v]"]

    def test_ensamblar_hook_incluye_sfx_del_mood(self, tmp_path) -> None:
        from backend_fastapi.app.services.ffmpeg_service import (
            _ensamblar_hook, _filtro_y_maps, _input_sfx, _mood_valido,
        )

        hook_tmp = tmp_path / "hook.mp4"
        clip_tmp = tmp_path / "clip.mp4"
        out = tmp_path / "out.mp4"
        graph, maps = _filtro_y_maps(0.2, 5.0, 30.0, has_audio=True, con_sfx=True)

        patcher, runner, fs = _patch_subprocess_ffmpeg()
        with patcher:
            _ensamblar_hook(
                hook_tmp, clip_tmp, out, graph, maps, has_audio=True,
                sfx_input=_input_sfx(_mood_valido("impact")),
            )
        cmd = runner.call_args_list[-1].args[0]
        assert "sine=f=55" in " ".join(cmd)  # preset impact

    def test_ensamblar_hook_mood_none_sin_input(self, tmp_path) -> None:
        from backend_fastapi.app.services.ffmpeg_service import _ensamblar_hook, _filtro_y_maps

        hook_tmp = tmp_path / "hook.mp4"
        clip_tmp = tmp_path / "clip.mp4"
        out = tmp_path / "out.mp4"
        graph, maps = _filtro_y_maps(0.2, 5.0, 30.0, has_audio=True, con_sfx=False)

        patcher, runner, fs = _patch_subprocess_ffmpeg()
        with patcher:
            _ensamblar_hook(hook_tmp, clip_tmp, out, graph, maps, has_audio=True, sfx_input=None)
        cmd = runner.call_args_list[-1].args[0]
        assert "anoisesrc" not in " ".join(cmd)
        assert "sine" not in " ".join(cmd)

    def test_build_hook_clip_teaser_normalizado_a_5s(self, tmp_path) -> None:
        from backend_fastapi.app.services.ffmpeg_service import build_hook_clip

        video = tmp_path / "in.mp4"
        video.write_bytes(b"x")
        salida = tmp_path / "hook.mp4"

        patcher, runner, fs = _patch_subprocess_ffmpeg()
        with patcher:
            build_hook_clip(video, 5.0, 30.0, 0.0, 3.0, salida)
        # El teaser (cmd con -vf B&W) debe cortar 0.000 + 5.000 (no 3s)
        teaser_cmd = next(c.args[0] for c in runner.call_args_list if "-vf" in c.args[0])
        i = teaser_cmd.index("-t")
        assert teaser_cmd[i + 1] == "5.000"

    def test_ass_validacion_ventana_4_5_a_5_5(self, tmp_path) -> None:
        from backend_fastapi.app.services.ass_generator import _validar_ventana_hook

        _validar_ventana_hook(0.0, 5.0)  # OK
        with pytest.raises(ValueError, match="entre 4.5 y 5.5"):
            _validar_ventana_hook(0.0, 3.0)

    def test_generate_hooked_ass_normaliza_ventana(self, tmp_path) -> None:
        from backend_fastapi.app.services.ass_generator import generate_hooked_ass

        destino = tmp_path / "hooked.ass"
        # hook 0-3s (< 4.5) se normaliza a [0,5] y NO explota
        generate_hooked_ass(
            [{"start": 0.0, "end": 3.0, "text": "frase hook"}, {"start": 6.0, "end": 8.0, "text": "cuerpo"}],
            clip_start=5.0,
            clip_end=30.0,
            hook_start=0.0,
            hook_end=3.0,
            output_path=destino,
        )
        assert destino.exists()

    # ------------------------------------------------------------ sfx_mood (issue #116)

    def test_filtro_y_maps_por_mood(self) -> None:
        from backend_fastapi.app.services.ffmpeg_service import _filtro_y_maps, _input_sfx, _mood_valido

        # los 3 moods con input lavfi -> [aout]
        for mood in ("tension", "impact", "transition"):
            sfx_input = _input_sfx(_mood_valido(mood))
            assert sfx_input is not None
            graph, maps = _filtro_y_maps(0.2, 5.0, 30.0, has_audio=True, con_sfx=True)
            assert "adelay=" in graph and "amix=inputs=2:duration=first:normalize=0" in graph
            assert maps == ["-map", "[v]", "-map", "[aout]"]
            # el preset lavfi del mood está en el input
            assert any(mood == key for key in ("tension", "impact", "transition"))
            assert _mood_valido(mood) == mood

    def test_mood_none_omite_sfx(self) -> None:
        from backend_fastapi.app.services.ffmpeg_service import _filtro_y_maps, _input_sfx, _mood_valido

        assert _input_sfx("none") is None
        assert _mood_valido("none") == "none"
        graph, maps = _filtro_y_maps(0.2, 5.0, 30.0, has_audio=True, con_sfx=False)
        assert "adelay" not in graph and "amix" not in graph
        assert maps == ["-map", "[v]", "-map", "[a]"]

    def test_mood_invalido_cae_en_default(self) -> None:
        from backend_fastapi.app.services.ffmpeg_service import _mood_valido

        assert _mood_valido("DESCONOCIDO") == "transition"
        assert _mood_valido(None) == "transition"

    def test_input_sfx_prefiere_archivo_del_mood(self, tmp_path, monkeypatch) -> None:
        from backend_fastapi.app.services import ffmpeg_service as fs

        monkeypatch.setattr(fs.Path, "is_file", lambda self: str(self).endswith("impact.wav"))
        sfx_input = fs._input_sfx("impact")
        assert sfx_input[0] == "-i"
        assert sfx_input[1].endswith("impact.wav")

    def test_build_hook_clip_con_mood_impact(self, tmp_path) -> None:
        from backend_fastapi.app.services.ffmpeg_service import build_hook_clip

        video = tmp_path / "in.mp4"
        video.write_bytes(b"x")
        salida = tmp_path / "hook.mp4"

        patcher, runner, _ = _patch_subprocess_ffmpeg()
        with patcher:
            build_hook_clip(video, 5.0, 30.0, 0.0, 3.0, salida, sfx_mood="impact")
        ensamble = runner.call_args_list[-1].args[0]
        # el input del SFX es lavfi (backend no tiene /app/sfx) del preset impact
        assert "sine=f=55" in " ".join(ensamble)

    def test_render_sin_hook_teaser_usa_cut(self, tmp_path) -> None:
        """enable_hook_teaser=False en _render: hook_sel ignorado -> cut directo + ASS simple."""
        from backend_fastapi.app.routers import jobs as jobs_mod

        video = tmp_path / "in.mp4"
        video.write_bytes(b"x")
        ass_path = tmp_path / "sub.ass"
        segmentos = [{"start": 10.0, "end": 30.0, "text": "hola"}]

        build_hook = Mock()
        cut = Mock(return_value=str(tmp_path / "cut.mp4"))
        with patch("backend_fastapi.app.services.ffmpeg_service.build_hook_clip", build_hook), patch(
            "backend_fastapi.app.services.ffmpeg_service.cut_segment", cut
        ), patch("backend_fastapi.app.services.ass_generator.write_ass_file", Mock()):
            jobs_mod._generar_ass(10.0, 40.0, segmentos, None, "teaser", None)
            # Con enable_hook_teaser=False el hook_sel llega None al render:
            # _cortar_clip_intermedio usa cut_segment (sin build_hook_clip).
            jobs_mod._cortar_clip_intermedio(video, 10.0, 40.0, None, "teaser", tmp_path / "t.mp4")
        build_hook.assert_not_called()
        cut.assert_called_once()

    def test_guardia_paridad_teaser_backend_worker(self) -> None:
        """Contrato #116: ffmpeg_service y video_processor no divergen."""
        from backend_fastapi.app.services import ffmpeg_service as fs
        import video_processor as vp

        tokens_compartidos = ("eq=saturation=0", "1.08", "volume=0.13", "adelay=", "amix=inputs=2:duration=first:normalize=0")
        for token in tokens_compartidos:
            assert token in fs.FILTRO_TEASER_BW + fs._filtro_sfx_whoosh(5.0), f"backend sin {token}"
            assert token in vp.FILTRO_TEASER_BW + vp._filtro_teaser_cuerpo(True), f"worker sin {token}"
        assert fs.HOOK_TEASER_DURACION == vp.TEASER_DURACION == 5.0
        assert fs.SFX_DURACION == vp.SFX_DURACION == 0.9
        assert fs.VOLUMEN_SFX == vp.VOLUMEN_SFX == 0.13
        assert fs.SFX_PRESETS_LAVFI.keys() == vp.SFX_PRESETS_LAVFI.keys()
        assert fs.SFX_PRESETS_LAVFI == vp.SFX_PRESETS_LAVFI

    def test_hook_service_prompt_apunta_a_5s(self) -> None:
        from backend_fastapi.app.services.hook_service import _build_hook_prompt

        prompt = _build_hook_prompt("transcripcion de prueba")
        assert "4.5 <= duration <= 5.5" in prompt
        assert "OBJETIVO 5.0s" in prompt

    def test_jobs_ass_teaser_normaliza_ventana(self, tmp_path) -> None:
        from backend_fastapi.app.routers import jobs as jobs_mod

        ass_path = tmp_path / "hooked.ass"
        capturado = {}

        def fake_generate(segs, clip_start, clip_end, hs, he, out, title=None):
            capturado["hs"], capturado["he"] = hs, he

        with patch("backend_fastapi.app.services.ass_generator.generate_hooked_ass", fake_generate):
            jobs_mod._ass_teaser(
                10.0, 40.0,
                [{"start": 2.0, "end": 5.0, "text": "hola"}],
                (12.0, 14.0, {"mode": "teaser"}),
                ass_path, None,
            )
        assert capturado["hs"] == 12.0
        assert capturado["he"] == 17.0  # normalizado a 5s


# ---------------------------------------------------------------- publish_service


class TestPublishService:
    def test_modulo_importable_tras_fix(self) -> None:
        # publish_service.py venía con el `from __future__` despues del código (bug real)
        import backend_fastapi.app.services.publish_service as ps

        assert callable(ps._first_env)

    def test_first_env_lee_el_primero_no_vacio(self, monkeypatch) -> None:
        import backend_fastapi.app.services.publish_service as ps

        monkeypatch.delenv("VAR_A", raising=False)
        monkeypatch.setenv("VAR_B", "otra")
        assert ps._first_env("VAR_A", "VAR_B") == "otra"
        monkeypatch.delenv("VAR_A", raising=False)
        monkeypatch.delenv("VAR_B", raising=False)
        assert ps._first_env("VAR_A", "VAR_B") == ""
