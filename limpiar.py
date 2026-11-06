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


def limpiar_proyecto():
    
    proyecto = Path(".")
    archivos_borrados = 0
    carpetas_borradas = 0
    
    # Borrar archivos individuales
    for nombre in ARCHIVOS_A_BORRAR:
        p = Path(nombre)
        if p.exists():
            p.unlink()
            archivos_borrados += 1
        else:
    
            pass
    # Borrar carpetas
    for nombre in CARPETAS_A_BORRAR:
        p = Path(nombre)
        if p.exists() and p.is_dir():
            shutil.rmtree(p)
            carpetas_borradas += 1
        else:
    
            pass
    # Borrar __pycache__ en subcarpetas
    for p in proyecto.rglob("__pycache__"):
        shutil.rmtree(p)
        archivos_borrados += 1
    
    # Borrar archivos .pyc
    for ext in EXTENSIONES_PY_CACHE:
        for p in proyecto.rglob(ext):
            p.unlink()
            archivos_borrados += 1
    


if __name__ == "__main__":
    limpiar_proyecto()