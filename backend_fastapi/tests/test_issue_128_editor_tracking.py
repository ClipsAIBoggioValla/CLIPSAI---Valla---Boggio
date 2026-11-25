"""Regresión de face-tracking en el editor FastAPI (#128)."""

from __future__ import annotations

from pathlib import Path

from backend_fastapi.app.services import editor


def test_editor_fallback_centra_crop_si_no_hay_rostros() -> None:
    filtro = editor._filtro_reframe(trayectoria=None)
    assert filtro.startswith("crop='if(gt(iw/ih,9/16)")
    assert "zoompan" not in filtro


def test_editor_crop_interpola_trayectoria() -> None:
    filtro = editor._filtro_reframe(trayectoria=[(0.0, 0.25), (1.0, 0.75)])
    assert filtro.startswith("crop=")
    assert "if(lt(t,1.000)" in filtro
    assert "scale=1080:1920" in filtro


def test_comando_reframe_conserva_picos_y_agrega_crop_dinamico() -> None:
    comando = editor._comando_reframe(
        Path("in.mp4"), Path("out.mp4"), [1.0], [(0.0, 0.4), (1.0, 0.6)]
    )
    vf = comando[comando.index("-vf") + 1]
    assert "it-1.000" in vf
    assert "if(lt(t,1.000)" in vf
