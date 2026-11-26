"""Tests focalizados de tracking facial, Active Speaker y fallback (#128)."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import audio_analyzer as aa  # noqa: E402
import video_processor as vp  # noqa: E402


def _cv2_falso(monkeypatch, detecciones, cascade_vacio=False):
    cv2 = types.ModuleType("cv2")
    cv2.CAP_PROP_FPS = 1
    cv2.CAP_PROP_FRAME_COUNT = 2
    cv2.CAP_PROP_POS_FRAMES = 3
    cv2.COLOR_BGR2GRAY = 4
    cv2.data = types.SimpleNamespace(haarcascades="/haarcascades/")

    class Captura:
        def isOpened(self):
            return True

        def get(self, propiedad):
            return 30

        def set(self, propiedad, valor):
            return None

        def read(self):
            return True, np.zeros((100, 200, 3), dtype=np.uint8)

        def release(self):
            return None

    class Cascade:
        def empty(self):
            return cascade_vacio

        def detectMultiScale(self, imagen, **kwargs):
            return detecciones

    cv2.VideoCapture = lambda ruta: Captura()
    cv2.CascadeClassifier = lambda ruta: Cascade()
    cv2.resize = lambda imagen, dimensiones: np.zeros((dimensiones[1], dimensiones[0], 3), dtype=np.uint8)
    cv2.cvtColor = lambda imagen, conversion: np.zeros(imagen.shape[:2], dtype=np.uint8)
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setitem(sys.modules, "mediapipe", types.ModuleType("mediapipe"))


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


def test_tracking_usa_haar_cascade_sin_mp_solutions(monkeypatch) -> None:
    _cv2_falso(monkeypatch, [(160, 40, 40, 60)])
    trayectoria = vp._detectar_trayectoria_rostros("video.mp4")
    assert trayectoria and trayectoria[0][1] == 0.5625


def test_tracking_sin_cascade_o_rostros_activa_crop_centrado(monkeypatch) -> None:
    _cv2_falso(monkeypatch, [], cascade_vacio=True)
    assert vp._detectar_trayectoria_rostros("video.mp4") == []
    assert vp._filtro_crop_tracking(None) == ""


def test_cascade_vacio_reintenta_xml_desde_temporal_ascii(monkeypatch, tmp_path: Path) -> None:
    _cv2_falso(monkeypatch, [])
    cv2 = sys.modules["cv2"]
    cascade_dir = tmp_path / "cascádé"
    cascade_dir.mkdir()
    (cascade_dir / "haarcascade_frontalface_default.xml").write_bytes(b"xml")
    cv2.data.haarcascades = str(cascade_dir) + os.sep
    rutas = []

    def cargar(ruta):
        rutas.append(ruta)
        return types.SimpleNamespace(empty=lambda: len(rutas) == 1)

    cv2.CascadeClassifier = cargar
    assert vp._cascade_rostros(cv2) is not None
    assert len(rutas) == 2 and not rutas[0].isascii() and rutas[1].isascii()
    assert not Path(rutas[1]).exists()


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


def test_podcast_split_usa_retrato_individual_si_falta_una_cara() -> None:
    trayectoria = [(0.0, 0.4), (1.0, 0.6)]
    for izquierda, derecha, centro_x in ((trayectoria, None, "iw/4"), (None, trayectoria, "3*iw/4")):
        filtro = vp._filtro_podcast_split(izquierda, derecha)
        assert "vstack=inputs=2" not in filtro
        assert "scale=1080:1920" in filtro and centro_x in filtro
        assert "if(lt(t,1.000)" in filtro and filtro.endswith("[v]")


def test_podcast_split_usa_retrato_centrado_si_no_hay_rostros() -> None:
    filtro = vp._filtro_podcast_split(None, None)
    assert "vstack=inputs=2" not in filtro
    assert "scale=1080:1920" in filtro and "crop='if(gt(iw/ih,9/16)" in filtro
    assert filtro.endswith("[v]")


def test_podcast_split_con_dos_rostros_mantiene_paneles_y_recorte_acotado() -> None:
    izquierda, derecha = [(0.0, 0.2)], [(0.0, 0.8)]
    filtro = vp._filtro_podcast_split(izquierda, derecha)
    assert "crop=iw/2:iw*4/9:0:" in filtro
    assert "crop=iw/2:iw*4/9:iw/2:" in filtro
    assert vp._y_crop_panel(izquierda) in filtro and "max(0,ih-iw*4/9)" in filtro
    assert "vstack=inputs=2" in filtro and filtro.endswith("[v]")


def test_podcast_split_sin_detecciones_simultaneas_usa_tracking_individual() -> None:
    izquierda, derecha = [(0.0, 0.2)], [(1.0, 0.8)]
    trayectoria = [(0.0, 0.3), (1.0, 0.6)]
    filtro = vp._filtro_podcast_split(izquierda, derecha, trayectoria=trayectoria)
    assert "vstack=inputs=2" not in filtro and "scale=1080:1920" in filtro
    assert "if(lt(t,1.000)" in filtro and filtro.endswith("[v]")


def test_gameplay_split_apila_camara_y_juego_con_subtitulos(tmp_path: Path) -> None:
    ass_file = tmp_path / "subs.ass"
    ass_file.write_text("[Events]", encoding="utf-8")
    caras = [(0.0, 0.4)]
    filtro = vp._filtro_gameplay_split(str(ass_file), caras, caras)
    assert "[cam]crop=iw/2:ih:0:0" in filtro
    assert "scale=1080:640" in filtro and "scale=1080:1280" in filtro
    assert "vstack=inputs=2" in filtro and "ass=" in filtro and filtro.endswith("[v]")


def test_gameplay_split_usa_retrato_tracking_si_falta_un_panel() -> None:
    trayectoria = [(0.0, 0.35), (1.0, 0.6)]
    filtro = vp._filtro_gameplay_split(None, trayectoria, None, trayectoria)
    assert "split=2" not in filtro and "vstack=inputs=2" not in filtro
    assert "scale=1080:1920" in filtro and "if(lt(t,1.000)" in filtro


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
