"""Issue #117 — emojis Noto Color Emoji + zoompan guiado por picos RMS.

Cubre el camino worker/raíz completo: picos RMS → engine → handler →
video_processor, y el contrato de paridad con los servicios del backend.
Sin FFmpeg, red ni modelos reales.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import audio_analyzer as aa  # noqa: E402
import engine as engine_mod  # noqa: E402
import main as main_mod  # noqa: E402
import video_processor as vp  # noqa: E402
from backend import handler as handler_mod  # noqa: E402
from backend_fastapi.app.services import ass_generator as backend_ass  # noqa: E402
from backend_fastapi.app.services import ffmpeg_service as backend_ffmpeg  # noqa: E402


# ------------------------------------------------------------------ picos RMS


class TestPicosParaZoom:
    def test_top_k_y_separacion_minima(self) -> None:
        tiempos = [i * 0.5 for i in range(60)]
        rms = [0.1] * 60
        for idx in range(0, 50, 4):  # 13 picos cada 2s
            rms[idx] = 0.9 - idx * 0.001
        picos = aa._picos_para_zoom(rms, tiempos)
        assert len(picos) == aa.PICO_ZOOM_TOP_K
        assert picos == sorted(picos)
        assert all(b - a >= aa.PICO_ZOOM_SEPARACION for a, b in zip(picos, picos[1:]))

    def test_elige_los_de_mayor_intensidad(self) -> None:
        tiempos = [0.0, 0.5, 10.0]
        rms = [0.2, 0.9, 0.5]
        assert aa._picos_para_zoom(rms, tiempos) == [0.5, 10.0]

    def test_lista_vacia(self) -> None:
        assert aa._picos_para_zoom([], []) == []

    def test_sidecar_roundtrip_y_missing(self, tmp_path: Path) -> None:
        salida = tmp_path / "audio.json"
        aa.guardar_picos_zoom([0.5, 1.5], str(salida).replace(".json", "_picos.json"))
        assert aa.cargar_picos(str(salida)) == [0.5, 1.5]
        assert aa.cargar_picos(str(tmp_path / "no-existe.json")) == []

    def test_analizar_audio_escribe_sidecar_sin_eventos(self, tmp_path: Path, monkeypatch: Any) -> None:
        monkeypatch.setattr(aa, "cargar_audio", Mock(return_value=([0.0], 16000)))
        monkeypatch.setattr(aa, "calcular_rms", Mock(return_value=([0.9, 0.1], [1.0, 8.0])))
        monkeypatch.setattr(aa, "detectar_eventos", Mock(return_value=[]))
        monkeypatch.setattr(aa, "detectar_momentos_intensos", Mock(return_value=[]))
        monkeypatch.setattr(aa, "detectar_cambios_escena", Mock(return_value=[]))
        salida = tmp_path / "audio.json"

        assert aa.analizar_audio("audio.mp3", str(salida)) == []
        assert aa.cargar_picos(str(salida)) == [1.0, 8.0]


# ------------------------------------------------------------------ zoompan


class TestZoompan:
    def test_sin_picos_no_agrega_filtro(self) -> None:
        assert vp._filtro_zoompan([]) == ""
        estatico = vp._construir_filtergraph(None, [])
        assert not any("zoompan" in filtro for filtro in estatico)
        assert estatico[-1] == "setsar=1"

    def test_expresion_usa_it_fps_y_rampa(self) -> None:
        filtro = vp._filtro_zoompan([1.0])
        assert filtro.startswith("fps=30,zoompan=")
        assert "it-1.000" in filtro
        assert "1+0.12" in filtro
        assert "/0.200" in filtro
        assert ":d=1:" in filtro
        assert ":fps=30" in filtro
        # `t` no existe en zoompan: la variable usada debe ser `it`.
        assert "(t-" not in filtro

    def test_top_k_acota_la_expresion(self) -> None:
        filtro = vp._filtro_zoompan([float(i) for i in range(20)])
        assert filtro.count("clip((it-") == vp.ZOOM_TOP_K

    def test_filtergraph_ordena_crop_scale_zoom_setsar(self) -> None:
        filtros = vp._construir_filtergraph(None, [1.0])
        zoom_idx = next(i for i, f in enumerate(filtros) if "zoompan" in f)
        assert filtros[0].startswith("crop=")
        assert filtros[1].startswith("scale=")
        assert zoom_idx == 2
        assert filtros[3] == "setsar=1"

    def test_paridad_worker_backend(self) -> None:
        picos = [0.25, 4.5, 12.0]
        assert vp._filtro_zoompan(picos) == backend_ffmpeg._filtro_zoompan(picos)
        assert backend_ffmpeg._filtro_zoompan([]) == ""


# ------------------------------------------------------------------ ASS emoji


class TestEmojiAssWorker:
    def test_emoji_con_override_noto_y_restauracion(self) -> None:
        linea = vp._evento_dialogue_ass(
            {"start": 0.0, "end": 2.0, "text": "hola mundo", "emoji": "🔥"}
        )
        assert "{\\fnNoto Color Emoji}🔥{\\fnDejaVu Sans} HOLA MUNDO" in linea

    @pytest.mark.parametrize("emoji", [None, "", "none", "NONE"])
    def test_sin_emoji_no_hay_override(self, emoji: str | None) -> None:
        linea = vp._evento_dialogue_ass(
            {"start": 0.0, "end": 2.0, "text": "hola", "emoji": emoji}
        )
        assert "\\fnNoto" not in linea

    def test_emoji_inseguro_se_sanea(self) -> None:
        linea = vp._evento_dialogue_ass(
            {"start": 0.0, "end": 2.0, "text": "hola", "emoji": "🔥{x}\\N"}
        )
        assert "🔥x" in linea
        assert "{x}" not in linea

    def test_paridad_dialogue_backend_worker(self) -> None:
        seg = {"start": 0.0, "end": 2.0, "text": "hola mundo", "emoji": "🔥"}
        worker = vp._evento_dialogue_ass(seg).strip()
        content = backend_ass.generate_ass_content([seg])
        backend = next(line for line in content.splitlines() if line.startswith("Dialogue:"))
        assert worker == backend

    def test_backend_hooked_ass_conserva_emoji(self, tmp_path: Path) -> None:
        destino = tmp_path / "hooked.ass"
        backend_ass.generate_hooked_ass(
            [
                {"start": 5.0, "end": 7.0, "text": "hook", "emoji": "🔥"},
                {"start": 12.0, "end": 14.0, "text": "cuerpo", "emoji": "😱"},
            ],
            clip_start=0.0,
            clip_end=30.0,
            hook_start=5.0,
            hook_end=10.0,
            output_path=destino,
        )
        contenido = destino.read_text(encoding="utf-8")
        assert "{\\fnNoto Color Emoji}🔥{\\fnDejaVu Sans}" in contenido
        assert "{\\fnNoto Color Emoji}😱{\\fnDejaVu Sans}" in contenido


# ------------------------------------------------------------------ LLM schema


class TestEmojisLlm:
    def test_sanitiza_invalidos_y_none(self) -> None:
        emojis = main_mod._emojis_validos(
            [
                {"segundo": 1.5, "emoji": "🔥"},
                {"segundo": "no-numero", "emoji": "😱"},
                {"segundo": 3.0, "emoji": "none"},
                {"segundo": -1.0, "emoji": "😱"},
                {"segundo": 4.0, "emoji": "{x}"},
                "no-es-dict",
            ]
        )
        assert emojis == [
            {"segundo": 1.5, "emoji": "🔥"},
            {"segundo": 4.0, "emoji": "x"},
        ]

    def test_prompt_incluye_emojis_cada_4_6_palabras(self) -> None:
        prompt = main_mod.construir_prompt("transcripcion", [], {})
        assert '"emoji"' in prompt
        assert "4-6 palabras" in prompt


# ------------------------------------------------------------------ handler


class TestHandlerPropagacion:
    def test_picos_de_clip_relativos(self) -> None:
        assert handler_mod._picos_de_clip([1.0, 2.5, 4.0, 9.0], 2.0, 5.0) == [0.5, 2.0]
        assert handler_mod._picos_de_clip(None, 0.0, 5.0) == []

    def test_emojis_a_segmentos_preserva_los_sin_emoji(self) -> None:
        segs = [
            {"start": 10.0, "end": 12.0, "text": "a"},
            {"start": 12.0, "end": 15.0, "text": "b"},
        ]
        resultado = handler_mod._emojis_a_segmentos(
            segs, [{"segundo": 11.0, "emoji": "🔥"}], 10.0, 15.0
        )
        assert resultado[0]["emoji"] == "🔥"
        assert "emoji" not in resultado[1]
        assert resultado[1] == segs[1]
        assert handler_mod._emojis_a_segmentos(segs, [], 10.0, 15.0) is segs

    def test_procesar_clip_vertical_propaga_picos_y_emoji(self, tmp_path: Path, monkeypatch: Any) -> None:
        horizontal = tmp_path / "h.mp4"
        horizontal.write_bytes(b"v")
        (tmp_path / "h_vertical.mp4").write_bytes(b"v")
        clip = SimpleNamespace(
            inicio="00:00:02", fin="00:00:06", archivo=str(horizontal),
            emojis=[{"segundo": 3.0, "emoji": "🔥"}], hook_texto="",
        )
        capturado: dict = {}

        def _fake_process(**kwargs):
            capturado.update(kwargs)
            return True

        monkeypatch.setattr("video_processor.process_clip_vertical", _fake_process)
        monkeypatch.setattr(handler_mod, "_subir_clip_a_r2", Mock(return_value={"ok": True}))

        resultado = handler_mod._procesar_clip_vertical(
            "v.mp4", [{"start": 2.5, "end": 3.5, "text": "hola"}],
            clip, 0, "bucket", "vid", picos_rms=[1.0, 2.5, 3.0, 9.0],
        )
        assert resultado == {"ok": True}
        assert capturado["picos_zoom"] == [0.5, 1.0]
        assert capturado["segments"][0]["emoji"] == "🔥"

    def test_respuesta_completa_pasa_picos(self, monkeypatch: Any) -> None:
        result = SimpleNamespace(
            clips=[], transcription_segments=[], carpeta_salida="out", picos_rms=[1.0, 2.0]
        )
        capturado: dict = {}

        def _fake(*args, **kwargs):
            capturado.update(kwargs)
            return []

        monkeypatch.setattr(handler_mod, "_procesar_clips_verticales", _fake)
        respuesta = handler_mod._respuesta_completa(result, "vid", Path("v.mp4"), "bucket")
        assert respuesta["status"] == "COMPLETED"
        assert capturado["picos_rms"] == [1.0, 2.0]


# ------------------------------------------------------------------ engine


class TestEnginePicos:
    def test_cargar_picos_zoom_usa_sidecar(self, tmp_path: Path, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "audio_analyzer", SimpleNamespace(cargar_picos=lambda ruta: [0.5, 2.0]))
        assert engine_mod._cargar_picos_zoom(str(tmp_path)) == [0.5, 2.0]

    def test_cargar_picos_zoom_fallback(self, monkeypatch: Any) -> None:
        def _explota(ruta):
            raise OSError("sin sidecar")

        monkeypatch.setitem(sys.modules, "audio_analyzer", SimpleNamespace(cargar_picos=_explota))
        assert engine_mod._cargar_picos_zoom("no-existe") == []

    def test_resultado_vacio_conserva_picos(self) -> None:
        resultado = engine_mod._resultado_vacio_con_segmentos("out", [], [1.0, 2.0])
        assert resultado.exito is True
        assert resultado.picos_rms == [1.0, 2.0]
        assert resultado.to_dict()["picos_rms"] == [1.0, 2.0]
