#!/usr/bin/env python3
"""
Limpia todos los archivos generados/temporales del proyecto.
Deja solo el código fuente.
"""

import os
import shutil
from pathlib import Path

ARCHIVOS_A_BORRAR = [
    "audio.mp3",
    "audio.wav",
    "audio_trans_temp.wav",
    "audio.json",
    "momentos_virales.json",
    "transcripcion.txt",
    "transcripcion_formatted.txt",
    "vidstab_transforms.trf",
]

CARPETAS_A_BORRAR = [
    "clips",
    "clips_editados",
    "__pycache__",
]

EXTENSIONES_PY_CACHE = ["*.pyc", "*.pyo", "*.pyd"]


def _borrar_archivos_individuales() -> int:
    """Borra los archivos generados listados; devuelve la cantidad borrada."""
    borrados = 0
    for nombre in ARCHIVOS_A_BORRAR:
        p = Path(nombre)
        if p.exists():
            p.unlink()
            borrados += 1
    return borrados


def _borrar_carpetas() -> int:
    """Borra las carpetas listadas si son directorios; devuelve la cantidad borrada."""
    borrados = 0
    for nombre in CARPETAS_A_BORRAR:
        p = Path(nombre)
        if p.exists() and p.is_dir():
            shutil.rmtree(p)
            borrados += 1
    return borrados


def _borrar_caches_py() -> int:
    """Borra __pycache__ y archivos .pyc/.pyo/.pyd; devuelve la cantidad borrada."""
    proyecto = Path(".")
    borrados = 0

    # Borrar __pycache__ en subcarpetas
    for p in proyecto.rglob("__pycache__"):
        shutil.rmtree(p)
        borrados += 1

    # Borrar archivos .pyc
    for ext in EXTENSIONES_PY_CACHE:
        for p in proyecto.rglob(ext):
            p.unlink()
            borrados += 1

    return borrados


def limpiar_proyecto():
    archivos_borrados = _borrar_archivos_individuales()
    carpetas_borradas = _borrar_carpetas()
    archivos_borrados += _borrar_caches_py()


if __name__ == "__main__":
    limpiar_proyecto()