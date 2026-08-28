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
            print(clip.archivo)
"""

import sys
import os
import json
from engine import procesar_video, ProcesamientoResultado, limpiar_directorio_trabajo


def main():
    if len(sys.argv) < 3:
        print("Uso: python ejemplo_engine.py <video> <transcripcion>")
        print("")
        print("Ejemplo:")
        print("  python ejemplo_engine.py video.mp4 transcripcion.txt")
        print("")
        print("La transcripción debe estar en formato YouTube:")
        print("  0:00 - Primer segmento de texto")
        print("  0:30 - Segundo segmento")
        print("  1:00 - Tercer segmento")
        sys.exit(1)

    video_path = sys.argv[1]
    transcripcion_path = sys.argv[2]

    print("=" * 60)
    print("  ENGINE CLIPSAI - EJEMPLO DE INVOCACIÓN")
    print("=" * 60)
    print(f"Video: {video_path}")
    print(f"Transcripción: {transcripcion_path}")
    print("-" * 60)

    # Invocación única del motor
    resultado = procesar_video(video_path, transcripcion_path)

    # Mostrar resultado estructurado (como lo recibiría la capa web)
    print("\nRESULTADO ESTRUCTURADO:")
    print(json.dumps(resultado.to_dict(), indent=2, ensure_ascii=False))

    # Manejo según éxito o error
    if resultado.exito:
        print(f"\n✓ PROCESAMIENTO EXITOSO")
        print(f"  Clips generados: {len(resultado.clips)}")
        print(f"  Carpeta de salida: {resultado.carpeta_salida}")
        print("")
        print("  Clips:")
        for i, clip in enumerate(resultado.clips, 1):
            print(f"    {i}. {os.path.basename(clip.archivo)}")
            print(f"       Inicio: {clip.inicio} | Fin: {clip.fin}")
            print(f"       Score: {clip.score} | Criterio: {clip.criterio_principal}")
            print(f"       Título: {clip.titulo_sugerido}")
            print(f"       Hook: {clip.hook_texto}")
            print("")

        # Opcional: limpiar directorio temporal si no se necesitan los archivos
        # Descomenta la siguiente línea si quieres limpieza automática:
        # limpiar_directorio_trabajo(resultado.carpeta_salida)
        print(f"  NOTA: Los clips están en {resultado.carpeta_salida}")
        print(f"  Usa limpiar_directorio_trabajo() cuando termines de usarlos.")

    else:
        print(f"\n✗ ERROR EN PROCESAMIENTO")
        print(f"  Tipo: {resultado.error_tipo}")
        print(f"  Mensaje: {resultado.error}")
        if resultado.error_detalle:
            print(f"  Detalle técnico:")
            for line in resultado.error_detalle.strip().split('\n')[-5:]:  # Últimas 5 líneas
                print(f"    {line}")

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