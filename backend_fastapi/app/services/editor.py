"""Funciones de edición de video para producir clips verticales 9:16."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
OUTPUT_ASPECT_RATIO = "9:16"
FACE_SMOOTH_ALPHA = 0.35
FACE_DEAD_ZONE = 0.015


def _validar_reframe_entrada(source: Path, aspect_ratio: str) -> None:
    """Valida aspect ratio y existencia del video de entrada."""
    if aspect_ratio != OUTPUT_ASPECT_RATIO:
        raise RuntimeError(f"Aspect ratio no soportado: {aspect_ratio!r}; se requiere '9:16'")
    if not source.is_file():
        raise RuntimeError(f"No se puede aplicar crop 9:16: video de entrada no encontrado: {source}")


def _dimensiones_ffprobe(source: Path) -> str | None:
    """Dimensiones 'WxH' del stream de video; None si no se pudo sondear."""
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x",
        str(source),
    ]
    probe = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
    if probe.returncode == 0 and probe.stdout.strip():
        return probe.stdout.strip()
    return None


def _dimensiones_o_aviso(source: Path) -> str | None:
    """Dimensiones del input; loguea aviso si ffprobe falla."""
    try:
        return _dimensiones_ffprobe(source)
    except Exception as probe_err:
        logger.warning("[editor] no se pudo verificar dimensiones del input: %s", probe_err)
        return None


def _copiar_si_ya_vertical(source: Path, output: Path) -> bool:
    """Copia tal cual si el video ya es 1080x1920. False si no."""
    dims = _dimensiones_o_aviso(source)
    if dims is None:
        return False
    logger.info("[editor] reframe_video input dimensions: %s (%s)", source.name, dims)
    if dims == f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}":
        logger.info("[editor] reframe_video: video ya es %dx%d, copiando tal cual", OUTPUT_WIDTH, OUTPUT_HEIGHT)
        import shutil
        shutil.copy2(str(source), str(output))
        return True
    return False


def _filtro_reframe(
    picos: list[float] | None = None,
    trayectoria: list[tuple[float, float]] | None = None,
) -> str:
    """Crop-primero + scale + zoompan por picos + setsar (issue #117)."""
    from .ffmpeg_service import _filtro_zoompan

    # Crop-primero (evita frames intermedios gigantes de 3413px que causan OOM en Render)
    # Para input 1280x720 (16:9):
    #   1. crop calcula 405x720 (centrado, manteniendo aspect ratio 9:16)
    #   2. scale escala a 1080x1920
    filtros = [
        _filtro_crop_tracking_editor(trayectoria) or f"crop='if(gt(iw/ih,9/16),ih*9/16,iw)':'if(gt(iw/ih,9/16),ih,iw*16/9)'",
        f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}",
    ]
    zoom = _filtro_zoompan(picos or [])
    if zoom:
        filtros.append(zoom)
    filtros.append("setsar=1")
    return ",".join(filtros)


def _detectar_trayectoria_editor(source: Path) -> list[tuple[float, float]]:
    """Detecta rostros en keyframes de baja resolución; vacío mantiene crop centrado."""
    try:
        import cv2
        import mediapipe as mp
        captura = cv2.VideoCapture(str(source))
        if not captura.isOpened():
            return []
        detector = mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)
        puntos = _keyframes_editor(captura, detector, cv2)
        captura.release()
        return _suavizar_trayectoria_editor(puntos)
    except Exception as exc:
        logger.info("[editor] face tracking no disponible; crop centrado: %s", exc)
        return []


def _keyframes_editor(captura, detector, cv2) -> list[tuple[float, float]]:
    """Analiza hasta 30 keyframes repartidos por todo el video."""
    fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    cuenta = min(int(frames / fps / 0.5) + 1, 30)
    indices = [round(i * (frames - 1) / max(cuenta - 1, 1)) for i in range(cuenta)]
    return [p for i in indices if (p := _rostro_editor(captura, detector, cv2, i, fps))]


def _rostro_editor(captura, detector, cv2, indice: int, fps: float):
    """Devuelve (timestamp, centro X) del rostro mayor en el frame."""
    captura.set(cv2.CAP_PROP_POS_FRAMES, indice)
    ok, frame = captura.read()
    if not ok:
        return None
    frame = cv2.resize(frame, (320, max(1, int(frame.shape[0] * 320 / frame.shape[1]))))
    resultado = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    detecciones = resultado.detections or []
    if not detecciones:
        return None
    caja = max(detecciones, key=lambda d: d.location_data.relative_bounding_box.width)
    bbox = caja.location_data.relative_bounding_box
    return indice / fps, bbox.xmin + bbox.width / 2


def _suavizar_trayectoria_editor(puntos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Suavizado EMA y dead-zone, equivalente al del worker."""
    salida = []
    for tiempo, x in sorted(puntos):
        if not salida:
            salida.append((tiempo, x))
            continue
        anterior = salida[-1][1]
        nuevo = anterior + FACE_SMOOTH_ALPHA * (x - anterior) if abs(x - anterior) > FACE_DEAD_ZONE else anterior
        salida.append((tiempo, nuevo))
    return salida


def _filtro_crop_tracking_editor(puntos: list[tuple[float, float]] | None) -> str:
    """Crop 9:16 con interpolación temporal o cadena vacía para fallback centrado."""
    if not puntos:
        return ""
    expresion = f"min(max({puntos[-1][1]:.5f},0),1)"
    for (t0, x0), (t1, x1) in reversed(list(zip(puntos, puntos[1:]))):
        pendiente = (x1 - x0) / max(t1 - t0, 0.001)
        tramo = f"min(max({x0:.5f}+(t-{t0:.3f})*{pendiente:.5f},0),1)"
        expresion = f"if(lt(t,{t1:.3f}),{tramo},{expresion})"
    x = f"if(gt(iw/ih,9/16),min(max(({expresion})*iw-ih*9/32,0),iw-ih*9/16),0)"
    return f"crop='if(gt(iw/ih,9/16),ih*9/16,iw)':'if(gt(iw/ih,9/16),ih,iw*16/9)':'{x}':0:eval=frame"


def _registrar_overhead_editor(deteccion: float, render: float) -> float:
    """Registra detección/render observado, en porcentaje."""
    porcentaje = 100 * deteccion / max(render, 0.001)
    logger.info("[editor] deteccion=%.3fs render=%.3fs overhead=%.2f%%", deteccion, render, porcentaje)
    return porcentaje


def _comando_reframe(
    source: Path, output: Path, picos: list[float] | None = None,
    trayectoria: list[tuple[float, float]] | None = None,
) -> list[str]:
    """Comando ffmpeg de crop-primero para 9:16 (+ zoompan si hay picos)."""
    crop_filter = _filtro_reframe(picos, trayectoria)
    logger.info("[editor] reframe_video applying filter: %s", crop_filter)
    return [
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
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output),
    ]


def _ejecutar_ffmpeg_reframe(
    source: Path, output: Path, timeout_seconds: int, picos: list[float] | None = None,
    trayectoria: list[tuple[float, float]] | None = None,
):
    """Corre ffmpeg para el reencuadre; RuntimeError ante arranque/timeout."""
    try:
        return subprocess.run(
            _comando_reframe(source, output, picos, trayectoria), capture_output=True, text=True, timeout=timeout_seconds
        )
    except FileNotFoundError as exc:
        raise RuntimeError("No se pudo reencuadrar a 9:16: FFmpeg no está instalado o no está en PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"No se pudo reencuadrar a 9:16: FFmpeg excedió {timeout_seconds}s") from exc
    except OSError as exc:
        raise RuntimeError(f"No se pudo iniciar FFmpeg para el reencuadre 9:16: {exc}") from exc


def _fallar_reframe(result, output: Path) -> None:
    """Elimina la salida parcial y lanza el RuntimeError del fallo de ffmpeg."""
    output.unlink(missing_ok=True)
    stderr = (result.stderr or "sin stderr")[-2500:]
    logger.error("[editor] reframe FAILED rc=%s: %s", result.returncode, stderr)
    if result.returncode == -9:
        raise RuntimeError(
            f"reframe vertical falló (memoria/ffmpeg): ffmpeg fue terminado por OOM (rc=-9). "
            f"El video de entrada puede ser demasiado grande para los recursos disponibles."
        )
    raise RuntimeError(
        f"reframe vertical falló (ffmpeg rc={result.returncode}): {stderr}"
    )


def _validar_salida_reframe(output: Path) -> None:
    """Lanza RuntimeError si ffmpeg no generó un video válido."""
    if not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg terminó el crop 9:16 sin generar un video válido: {output}")


def _sondear_salida(output: Path):
    """Sondeo ffprobe del output; RuntimeError ante fallo (borra salida)."""
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
        return subprocess.run(probe_command, capture_output=True, text=True, timeout=30)
    except FileNotFoundError as exc:
        output.unlink(missing_ok=True)
        raise RuntimeError("No se pudo validar el crop 9:16: ffprobe no está instalado o no está en PATH") from exc
    except subprocess.TimeoutExpired as exc:
        output.unlink(missing_ok=True)
        raise RuntimeError("No se pudo validar el crop 9:16: ffprobe excedió 30s") from exc
    except OSError as exc:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"No se pudo validar el crop 9:16 con ffprobe: {exc}") from exc


def _validar_dimensiones_salida(output: Path, probe) -> None:
    """Borra la salida y lanza RuntimeError si las dimensiones no son 1080x1920."""
    dimensions = probe.stdout.strip() if probe.returncode == 0 else ""
    if dimensions != f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}":
        output.unlink(missing_ok=True)
        stderr = (probe.stderr or "").strip()
        raise RuntimeError(
            f"El reencuadre 9:16 produjo dimensiones inválidas: {dimensions or 'desconocidas'}; "
            f"esperadas {OUTPUT_WIDTH}x{OUTPUT_HEIGHT}. {stderr}"
        )


def reframe_video(
    input_video: str | Path,
    output_video: str | Path,
    aspect_ratio: Literal["9:16"] = "9:16",
    timeout_seconds: int = 300,
    picos: list[float] | None = None,
) -> str:
    """Recorta al centro y escala el video a 1080x1920; nunca devuelve el original.

    `picos` (issue #117): timestamps RMS relativos al clip para zoompan 1.0→1.12.
    El crop es FFmpeg-only, por lo que no depende de OpenCV, PyTorch o MediaPipe.
    Cualquier fallo se propaga como RuntimeError con el motivo concreto.
    """
    source = Path(input_video)
    output = Path(output_video)
    _validar_reframe_entrada(source, aspect_ratio)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Verificar dimensiones del video de entrada
    if _copiar_si_ya_vertical(source, output):
        return str(output)

    inicio_deteccion = time.perf_counter()
    trayectoria = _detectar_trayectoria_editor(source)
    deteccion_seconds = time.perf_counter() - inicio_deteccion
    inicio_render = time.perf_counter()
    result = _ejecutar_ffmpeg_reframe(source, output, timeout_seconds, picos, trayectoria)
    _registrar_overhead_editor(deteccion_seconds, time.perf_counter() - inicio_render)
    if result.returncode != 0:
        _fallar_reframe(result, output)
    _validar_salida_reframe(output)

    probe = _sondear_salida(output)
    _validar_dimensiones_salida(output, probe)
    return str(output)
