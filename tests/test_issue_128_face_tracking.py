"""Tests focalizados de tracking facial, Active Speaker y fallback (#128)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import audio_analyzer as aa  # noqa: E402
import video_processor as vp  # noqa: E402


def test_suavizado_reduce_jitter_y_conserva_tiempos() -> None:
    salida = vp._suavizar_trayectoria([(0.0, 0.5), (0.5, 0.51), (1.0, 0.9)])
    assert salida[1][1] == salida[0][1]
    assert salida[2][1] < 0.9
    assert [p[0] for p in salida] == [0.0, 0.5, 1.0]


def test_crop_tracking_interpolado_y_fallback_centrado() -> None:
    assert vp._filtro_crop_tracking(None) == ""
    filtro = vp._filtro_crop_tracking([(0.0, 0.3), (1.0, 0.7)])
    assert filtro.startswith("crop=")
    assert "eval=frame" in filtro and "if(lt(t,1.000)" in filtro
    assert vp._construir_filtergraph(None, [], None)[0].startswith("crop='if(gt(iw/ih,9/16)")


def test_active_speaker_cruza_rms_solo_con_rostros_en_ambos_paneles() -> None:
    caras = {"left": [(0.0, 0.5)], "right": [(0.0, 0.5)]}
    rms = [{"start": 0.0, "end": 0.5, "rms": [0.8, 0.1]},
           {"start": 0.5, "end": 1.0, "rms": [0.1, 0.9]}]
    assert aa.cruzar_rostros_rms(caras, rms) == [
        {"start": 0.0, "end": 0.5, "panel": "left"},
        {"start": 0.5, "end": 1.0, "panel": "right"},
    ]
    filtro = vp._filtro_podcast_split(caras["left"], caras["right"], rms)
    assert "between(t,0.000,0.500)" in filtro
    assert "eq=brightness" in filtro and "vstack=inputs=2" in filtro
    assert aa.cruzar_rostros_rms({"left": []}, rms) == []
    assert aa.cruzar_rostros_rms(caras, [{"start": 0, "end": 1, "rms": [0.5]}]) == []
    assert aa.cruzar_rostros_rms(caras, [{"start": 0, "end": 0.2, "rms": [0.9, 0.1]}]) == []


def test_podcast_split_neutro_si_falla_deteccion_o_rms() -> None:
    filtro = vp._filtro_podcast_split(None, None)
    assert "vstack=inputs=2" in filtro
    assert "brightness='0.12*(0)'" in filtro
    assert "crop=iw/2" in filtro


def test_gameplay_split_apila_camara_y_juego_con_subtitulos(tmp_path: Path) -> None:
    ass_file = tmp_path / "subs.ass"
    ass_file.write_text("[Events]", encoding="utf-8")
    filtro = vp._filtro_gameplay_split(str(ass_file))
    assert "[cam]crop=iw/2:ih:0:0" in filtro
    assert "scale=1080:640" in filtro and "scale=1080:1280" in filtro
    assert "vstack=inputs=2" in filtro and "ass=" in filtro and filtro.endswith("[v]")


def test_overhead_se_mide_en_relacion_al_render() -> None:
    assert vp._log_tracking_overhead(5.0, 100.0) == 5.0


def test_rms_por_ventana_y_sidecar_roundtrip(tmp_path: Path) -> None:
    ventanas = aa.rms_por_ventana(np.array([[1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0]]), 4, 0.5)
    assert ventanas[0]["rms"] == [1.0, 0.0]
    assert ventanas[1]["rms"] == [0.0, 1.0]
    audio_json = tmp_path / "audio.json"
    aa.guardar_rms_ventanas(ventanas, str(tmp_path / "audio_rms.json"))
    assert aa.cargar_rms_ventanas(str(audio_json)) == ventanas
    assert aa.cargar_rms_ventanas(str(tmp_path / "missing.json")) == []
