#!/usr/bin/env python3
"""
Ejemplo de uso del engine de clipsai.

Este script demuestra cómo invocar el motor desde la capa web
usando la interfaz estable definida en engine.py.

Uso:
    python ejemplo_engine.py video.mp4 transcripcion.txt

O programáticamente:
    from engine import procesar_video
    resultado = procesar_video("video.mp4", "transcripcion.txt")
    if resultado.exito:
        for clip in resultado.clips:
            pass
"""

import sys
import os
import json
from engine import procesar_video, ProcesamientoResultado, limpiar_directorio_trabajo


def main():
    if len(sys.argv) < 3:
        sys.exit(1)

    video_path = sys.argv[1]
    transcripcion_path = sys.argv[2]


    # Invocación única del motor
    resultado = procesar_video(video_path, transcripcion_path)

    # Mostrar resultado estructurado (como lo recibiría la capa web)

    # Manejo según éxito o error
    if resultado.exito:
        for i, clip in enumerate(resultado.clips, 1):

            pass
        # Opcional: limpiar directorio temporal si no se necesitan los archivos
        # Descomenta la siguiente línea si quieres limpieza automática:
        # limpiar_directorio_trabajo(resultado.carpeta_salida)

    else:
        if resultado.error_detalle:
            for line in resultado.error_detalle.strip().split('\n')[-5:]:  # Últimas 5 líneas
                pass

        # Códigos de salida para integración con scripts
        if resultado.error_tipo == "ValidacionError":
            sys.exit(2)
        elif resultado.error_tipo in ("ConexionError", "TimeoutError"):
            sys.exit(3)
        elif resultado.error_tipo == "IAError":
            sys.exit(4)
        elif resultado.error_tipo == "AudioError":
            sys.exit(5)
        elif resultado.error_tipo == "TranscripcionError":
            sys.exit(6)
        elif resultado.error_tipo == "GeneracionError":
            sys.exit(7)
        elif resultado.error_tipo == "SinClipsValidos":
            sys.exit(8)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()