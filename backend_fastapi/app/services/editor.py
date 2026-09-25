"""Funciones de edición de video para producir clips verticales 9:16."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal


OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
OUTPUT_ASPECT_RATIO = "9:16"


def reframe_video(
    input_video: str | Path,
    output_video: str | Path,
    aspect_ratio: Literal["9:16"] = "9:16",
    timeout_seconds: int = 300,
) -> str:
    """Recorta al centro y escala el video a 1080x1920; nunca devuelve el original.

    El crop es FFmpeg-only, por lo que no depende de OpenCV, PyTorch o MediaPipe.
    Cualquier fallo se propaga como RuntimeError con el motivo concreto.
    """
    source = Path(input_video)
    output = Path(output_video)
    if aspect_ratio != OUTPUT_ASPECT_RATIO:
        raise RuntimeError(f"Aspect ratio no soportado: {aspect_ratio!r}; se requiere '9:16'")
    if not source.is_file():
        raise RuntimeError(f"No se puede aplicar crop 9:16: video de entrada no encontrado: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)

    crop_filter = (
        "crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':"
        "x='(iw-ow)/2':y='(ih-oh)/2',"
        f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:flags=lanczos,setsar=1"
    )
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vf",
        crop_filter,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output),
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
    except FileNotFoundError as exc:
        raise RuntimeError("No se pudo reencuadrar a 9:16: FFmpeg no está instalado o no está en PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"No se pudo reencuadrar a 9:16: FFmpeg excedió {timeout_seconds}s") from exc
    except OSError as exc:
        raise RuntimeError(f"No se pudo iniciar FFmpeg para el reencuadre 9:16: {exc}") from exc

    if result.returncode != 0:
        output.unlink(missing_ok=True)
        stderr = (result.stderr or "sin stderr")[-2500:]
        raise RuntimeError(f"FFmpeg falló al aplicar crop 9:16 (code={result.returncode}): {stderr}")
    if not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg terminó el crop 9:16 sin generar un video válido: {output}")

    probe_command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0:s=x",
        str(output),
    ]
    try:
        probe = subprocess.run(probe_command, capture_output=True, text=True, timeout=30)
    except FileNotFoundError as exc:
        output.unlink(missing_ok=True)
        raise RuntimeError("No se pudo validar el crop 9:16: ffprobe no está instalado o no está en PATH") from exc
    except subprocess.TimeoutExpired as exc:
        output.unlink(missing_ok=True)
        raise RuntimeError("No se pudo validar el crop 9:16: ffprobe excedió 30s") from exc
    except OSError as exc:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"No se pudo validar el crop 9:16 con ffprobe: {exc}") from exc

    dimensions = probe.stdout.strip() if probe.returncode == 0 else ""
    if dimensions != f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}":
        output.unlink(missing_ok=True)
        stderr = (probe.stderr or "").strip()
        raise RuntimeError(
            f"El reencuadre 9:16 produjo dimensiones inválidas: {dimensions or 'desconocidas'}; "
            f"esperadas {OUTPUT_WIDTH}x{OUTPUT_HEIGHT}. {stderr}"
        )

    return str(output)
