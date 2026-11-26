"""Regresión de face-tracking en el editor FastAPI (#128)."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import numpy as np

from backend_fastapi.app.services import editor


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


def test_editor_tracking_usa_haar_cascade_sin_mp_solutions(monkeypatch) -> None:
    _cv2_falso(monkeypatch, [(160, 40, 40, 60)])
    trayectoria = editor._detectar_trayectoria_editor(Path("video.mp4"))
    assert trayectoria and trayectoria[0][1] == 0.5625


def test_editor_tracking_fallback_si_cascade_falla_o_no_hay_rostros(monkeypatch) -> None:
    _cv2_falso(monkeypatch, [(160, 40, 40, 60)], cascade_vacio=True)
    assert editor._detectar_trayectoria_editor(Path("video.mp4")) == []
    assert editor._filtro_reframe(trayectoria=None).startswith("crop='if(gt(iw/ih,9/16)")

    _cv2_falso(monkeypatch, [])
    assert editor._detectar_trayectoria_editor(Path("video.mp4")) == []


def test_editor_cascade_vacio_reintenta_xml_desde_temporal_ascii(monkeypatch, tmp_path: Path) -> None:
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
    assert editor._cascade_rostros_editor(cv2) is not None
    assert len(rutas) == 2 and not rutas[0].isascii() and rutas[1].isascii()
    assert not Path(rutas[1]).exists()


def test_editor_fallback_centra_crop_si_no_hay_rostros() -> None:
    filtro = editor._filtro_reframe(trayectoria=None)
    assert filtro.startswith("crop='if(gt(iw/ih,9/16)")
    assert "zoompan" not in filtro


def test_editor_crop_interpola_trayectoria() -> None:
    filtro = editor._filtro_reframe(trayectoria=[(0.0, 0.25), (1.0, 0.75)])
    assert filtro.startswith("crop=")
    assert "if(lt(t,1.000)" in filtro
    assert "scale=1080:1920" in filtro


def test_crop_tracking_dinamico_sin_eval_y_salida_v_en_reframe_video(tmp_path, monkeypatch) -> None:
    trayectoria = [(0.0, 0.25), (1.0, 0.75)]
    filtro = editor._filtro_crop_tracking_editor(trayectoria)
    assert filtro.endswith("':0") and "eval=frame" not in filtro

    source, output = tmp_path / "in.mp4", tmp_path / "out.mp4"
    source.write_bytes(b"video")
    monkeypatch.setattr(editor, "_detectar_trayectorias_split_editor", lambda path: (trayectoria, []))
    capturado = {}

    def ejecutar(source, output, timeout, picos, tracking, layout, izquierda, derecha):
        comando = editor._comando_reframe(source, output, picos, tracking, layout, izquierda, derecha)
        capturado["grafo"] = comando[comando.index("-filter_complex") + 1]
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(editor, "_ejecutar_ffmpeg_reframe", ejecutar)
    monkeypatch.setattr(editor, "_validar_salida_reframe", lambda path: None)
    monkeypatch.setattr(editor, "_sondear_salida", lambda path: types.SimpleNamespace())
    monkeypatch.setattr(editor, "_validar_dimensiones_salida", lambda path, probe: None)

    assert editor.reframe_video(source, output, layout="podcast_split") == str(output)
    assert ":0,scale=1080:1920" in capturado["grafo"]
    assert "eval=frame" not in capturado["grafo"] and capturado["grafo"].endswith("[v]")


def test_comando_reframe_conserva_picos_y_agrega_crop_dinamico() -> None:
    comando = editor._comando_reframe(
        Path("in.mp4"), Path("out.mp4"), [1.0], [(0.0, 0.4), (1.0, 0.6)]
    )
    vf = comando[comando.index("-vf") + 1]
    assert "it-1.000" in vf
    assert "if(lt(t,1.000)" in vf


def test_comando_reframe_split_podcast_y_gameplay() -> None:
    caras = [(0.0, 0.4)]
    podcast = editor._comando_reframe(
        Path("in.mp4"), Path("out.mp4"), layout="podcast_split", rostro_izq=caras, rostro_der=caras
    )
    gameplay = editor._comando_reframe(
        Path("in.mp4"), Path("out.mp4"), layout="gameplay_split", rostro_izq=caras, rostro_der=caras
    )
    for command in (podcast, gameplay):
        graph = command[command.index("-filter_complex") + 1]
        assert "[0:v]split=2[cam][game]" in graph
        assert "-map" in command and "[v]" in command and "0:a?" in command
    assert "scale=1080:960" in podcast[podcast.index("-filter_complex") + 1]
    assert "scale=1080:640" in gameplay[gameplay.index("-filter_complex") + 1]
    assert "scale=1080:1280" in gameplay[gameplay.index("-filter_complex") + 1]


def test_split_editor_fallback_usa_reframe_simple_para_layout_invalido() -> None:
    filtro = editor._filtro_split_editor("layout_invalido")
    assert filtro == f"[0:v]{editor._filtro_reframe()}[v]"
    assert filtro.endswith("[v]") and "split=2" not in filtro
    assert "scale=1080:1920" in filtro


def test_split_editor_fallback_tracking_con_un_solo_rostro() -> None:
    rostro = [(0.0, 0.3), (1.0, 0.7)]
    filtro = editor._filtro_split_editor("podcast_split", rostro_izq=rostro, trayectoria=rostro)
    assert "split=2" not in filtro and "scale=1080:1920" in filtro
    assert "if(lt(t,1.000)" in filtro and filtro.endswith("[v]")


def test_filtro_split_fallback_es_compatible_con_comando_reframe() -> None:
    rostro = [(0.0, 0.3), (1.0, 0.7)]
    filtro = editor._filtro_split_editor("podcast_split", rostro_izq=rostro, trayectoria=rostro)
    comando = editor._comando_reframe(
        Path("in.mp4"), Path("out.mp4"), trayectoria=rostro,
        layout="podcast_split", rostro_izq=rostro,
    )
    grafo = comando[comando.index("-filter_complex") + 1]
    assert filtro.endswith("[v]") and grafo == filtro
    assert comando[comando.index("-map") + 1] == "[v]"


def test_split_editor_fallback_centrado_si_no_detecta_rostros() -> None:
    filtro = editor._filtro_split_editor("gameplay_split")
    assert "split=2" not in filtro and "scale=1080:1920" in filtro and filtro.endswith("[v]")


def test_split_editor_fallback_si_detecciones_no_coinciden_en_el_tiempo() -> None:
    izquierda, derecha = [(0.0, 0.2)], [(1.0, 0.8)]
    filtro = editor._filtro_split_editor(
        "podcast_split", izquierda, derecha, trayectoria=[(0.0, 0.3), (1.0, 0.6)]
    )
    assert "split=2" not in filtro and "scale=1080:1920" in filtro
    assert "if(lt(t,1.000)" in filtro and filtro.endswith("[v]")
