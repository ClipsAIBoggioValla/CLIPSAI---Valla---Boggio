"""Funciones de edición de video para producir clips verticales 9:16."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
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


def _filtro_split_editor(
    layout: str,
    rostro_izq: list[tuple[float, float]] | None = None,
    rostro_der: list[tuple[float, float]] | None = None,
    trayectoria: list[tuple[float, float]] | None = None,
) -> str:
    """Filter_complex para fuentes lado a lado: podcast 50/50, gameplay 1/3+2/3."""
    if layout not in ("podcast_split", "gameplay_split"):
        return _filtro_reframe_filter_complex(trayectoria)
    if not _trayectorias_dobles_validas(rostro_izq, rostro_der):
        logger.info("[editor] %s sin dos paneles válidos; usando reframe individual", layout)
        return _filtro_reframe_filter_complex(trayectoria)
    alto_camara, alto_juego = (960, 960) if layout == "podcast_split" else (640, 1280)
    return (
        "[0:v]split=2[cam][game];"
        f"[cam]crop=iw/2:ih:0:0,scale=1080:{alto_camara}:force_original_aspect_ratio=increase,"
        f"crop=1080:{alto_camara},setsar=1[vcam];"
        f"[game]crop=iw/2:ih:iw/2:0,scale=1080:{alto_juego}:force_original_aspect_ratio=increase,"
        f"crop=1080:{alto_juego},setsar=1[vgame];"
        "[vcam][vgame]vstack=inputs=2,setsar=1[v]"
    )


def _filtro_reframe_filter_complex(trayectoria: list[tuple[float, float]] | None) -> str:
    """Envuelve el reframe single como filter_complex con salida [v]."""
    return f"[0:v]{_filtro_reframe(trayectoria=trayectoria)}[v]"


def _detectar_trayectoria_editor(source: Path) -> list[tuple[float, float]]:
    """Detecta rostros en keyframes de baja resolución; vacío mantiene crop centrado."""
    captura = None
    try:
        import cv2
        captura = cv2.VideoCapture(str(source))
        if not captura.isOpened():
            return []
        detector = _cascade_rostros_editor(cv2)
        if detector is None:
            return []
        puntos = _keyframes_editor(captura, detector, cv2)
        return _suavizar_trayectoria_editor(puntos)
    except Exception as exc:
        logger.info("[editor] face tracking no disponible; crop centrado: %s", exc)
        return []
    finally:
        if captura is not None:
            captura.release()


def _cascade_rostros_editor(cv2):
    """Carga el Haar cascade de OpenCV; None conserva el crop centrado."""
    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    try:
        cascade = cv2.CascadeClassifier(cascade_path)
        if not cascade.empty():
            return cascade
    except Exception:
        pass
    return _cascade_rostros_temporal_editor(cv2, cascade_path)


def _cascade_rostros_temporal_editor(cv2, cascade_path: str):
    """Reintenta la carga desde un XML temporal en una ruta ASCII (Windows)."""
    try:
        directorio = tempfile.gettempdir()
        if not directorio.isascii():
            directorio = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Temp")
        if not directorio.isascii():
            return None
        with tempfile.TemporaryDirectory(prefix="clipsai_haar_", dir=directorio) as temporal:
            xml_temporal = Path(temporal) / "haarcascade_frontalface_default.xml"
            xml_temporal.write_bytes(Path(cascade_path).read_bytes())
            cascade = cv2.CascadeClassifier(str(xml_temporal))
            return None if cascade.empty() else cascade
    except Exception:
        return None


def _keyframes_editor(captura, detector, cv2, panel: str | None = None) -> list[tuple[float, float]]:
    """Analiza hasta 30 keyframes repartidos por todo el video."""
    fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    cuenta = min(int(frames / fps / 0.5) + 1, 30)
    indices = [round(i * (frames - 1) / max(cuenta - 1, 1)) for i in range(cuenta)]
    return [p for i in indices if (p := _rostro_editor(captura, detector, cv2, i, fps, panel))]


def _rostro_editor(captura, detector, cv2, indice: int, fps: float, panel: str | None = None):
    """Devuelve (timestamp, centro X) del rostro mayor en el frame."""
    captura.set(cv2.CAP_PROP_POS_FRAMES, indice)
    ok, frame = captura.read()
    if not ok:
        return None
    mitad = frame.shape[1] // 2
    frame = frame[:, :mitad] if panel == "left" else frame[:, mitad:] if panel == "right" else frame
    frame = cv2.resize(frame, (320, max(1, int(frame.shape[0] * 320 / frame.shape[1]))))
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detecciones = detector.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))
    if len(detecciones) == 0:
        return None
    x, y, ancho, alto = max(detecciones, key=lambda caja: caja[2] * caja[3])
    centro = (x + ancho / 2) / frame.shape[1]
    if panel == "left":
        centro /= 2
    elif panel == "right":
        centro = 0.5 + centro / 2
    return indice / fps, centro


def _detectar_trayectorias_split_editor(
    source: Path,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Detecta un rostro por mitad para validar los layouts split."""
    captura = None
    try:
        import cv2
        captura = cv2.VideoCapture(str(source))
        if not captura.isOpened():
            return [], []
        detector = _cascade_rostros_editor(cv2)
        if detector is None:
            return [], []
        izquierda = _suavizar_trayectoria_editor(_keyframes_editor(captura, detector, cv2, "left"))
        derecha = _suavizar_trayectoria_editor(_keyframes_editor(captura, detector, cv2, "right"))
        return izquierda, derecha
    except Exception as exc:
        logger.info("[editor] detección split no disponible; reframe centrado: %s", exc)
        return [], []
    finally:
        if captura is not None:
            captura.release()


def _trayectorias_dobles_validas(
    izquierda: list[tuple[float, float]] | None,
    derecha: list[tuple[float, float]] | None,
) -> bool:
    """Exige detecciones en ambos paneles en al menos un mismo instante."""
    if not izquierda or not derecha:
        return False
    instantes_derecha = {tiempo for tiempo, _ in derecha}
    return any(tiempo in instantes_derecha for tiempo, _ in izquierda)


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
    ancho = "if(gt(iw/ih,9/16),ih*9/16,iw)"
    alto = "if(gt(iw/ih,9/16),ih,iw*16/9)"
    return f"crop='{ancho}':'{alto}':'{x}':0"


def _registrar_overhead_editor(deteccion: float, render: float) -> float:
    """Registra detección/render observado, en porcentaje."""
    porcentaje = 100 * deteccion / max(render, 0.001)
    logger.info("[editor] deteccion=%.3fs render=%.3fs overhead=%.2f%%", deteccion, render, porcentaje)
    return porcentaje


def _comando_reframe(
    source: Path, output: Path, picos: list[float] | None = None,
    trayectoria: list[tuple[float, float]] | None = None,
    layout: str = "single_9_16",
    rostro_izq: list[tuple[float, float]] | None = None,
    rostro_der: list[tuple[float, float]] | None = None,
) -> list[str]:
    """Comando ffmpeg de crop-primero para 9:16 (+ zoompan si hay picos)."""
    split = layout in ("podcast_split", "gameplay_split")
    filtro = (
        _filtro_split_editor(layout, rostro_izq, rostro_der, trayectoria)
        if split else _filtro_reframe(picos, trayectoria)
    )
    logger.info("[editor] reframe_video applying filter: %s", filtro)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-filter_complex" if split else "-vf",
        filtro,
    ]
    if split:
        command.extend(["-map", "[v]", "-map", "0:a?"])
    command.extend([
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
    ])
    return command


def _ejecutar_ffmpeg_reframe(
    source: Path, output: Path, timeout_seconds: int, picos: list[float] | None = None,
    trayectoria: list[tuple[float, float]] | None = None,
    layout: str = "single_9_16",
    rostro_izq: list[tuple[float, float]] | None = None,
    rostro_der: list[tuple[float, float]] | None = None,
):
    """Corre ffmpeg para el reencuadre; RuntimeError ante arranque/timeout."""
    try:
        return subprocess.run(
            _comando_reframe(source, output, picos, trayectoria, layout, rostro_izq, rostro_der),
            capture_output=True, text=True, timeout=timeout_seconds
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
    layout: Literal["single_9_16", "podcast_split", "gameplay_split"] = "single_9_16",
) -> str:
    """Recorta al centro y escala el video a 1080x1920; nunca devuelve el original.

    `picos` (issue #117): timestamps RMS relativos al clip para zoompan 1.0→1.12.
    El crop es FFmpeg-only, por lo que no depende de OpenCV, PyTorch o MediaPipe.
    Cualquier fallo se propaga como RuntimeError con el motivo concreto.
    """
    source = Path(input_video)
    output = Path(output_video)
    _validar_reframe_entrada(source, aspect_ratio)
    if layout not in ("single_9_16", "podcast_split", "gameplay_split"):
        raise RuntimeError(f"Layout no soportado: {layout!r}")
    output.parent.mkdir(parents=True, exist_ok=True)

    # Verificar dimensiones del video de entrada
    if layout == "single_9_16" and _copiar_si_ya_vertical(source, output):
        return str(output)

    inicio_deteccion = time.perf_counter()
    rostro_izq, rostro_der = ([], [])
    if layout == "single_9_16":
        trayectoria = _detectar_trayectoria_editor(source)
    elif layout in ("podcast_split", "gameplay_split"):
        rostro_izq, rostro_der = _detectar_trayectorias_split_editor(source)
        trayectoria = rostro_izq or rostro_der
    deteccion_seconds = time.perf_counter() - inicio_deteccion
    inicio_render = time.perf_counter()
    result = _ejecutar_ffmpeg_reframe(
        source, output, timeout_seconds, picos, trayectoria, layout, rostro_izq, rostro_der
    )
    _registrar_overhead_editor(deteccion_seconds, time.perf_counter() - inicio_render)
    if result.returncode != 0:
        _fallar_reframe(result, output)
    _validar_salida_reframe(output)

    probe = _sondear_salida(output)
    _validar_dimensiones_salida(output, probe)
    return str(output)


def _overlay_graph() -> str:
    """Filtergraph de watermark discreto con transparencia del 60%."""
    return "[1:v]scale=220:-1,format=rgba,colorchannelmixer=aa=0.6[wm];[0:v][wm]overlay=W-w-24:H-h-24:shortest=1[outv]"


def overlay_watermark(video_path: str | Path, watermark_path: str | Path | None) -> str:
    """Aplica watermark local; ausencia de marca conserva el render original."""
    source = Path(video_path)
    watermark = Path(watermark_path) if watermark_path else None
    if watermark is None or not watermark.is_file():
        return str(source)
    temp_output = source.with_name(f".{source.stem}.watermark{source.suffix}")
    command = [
        "ffmpeg", "-y", "-i", str(source), "-loop", "1", "-i", str(watermark),
        "-filter_complex", _overlay_graph(), "-map", "[outv]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-c:a", "copy",
        "-movflags", "+faststart", str(temp_output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0 or not temp_output.is_file() or temp_output.stat().st_size == 0:
        temp_output.unlink(missing_ok=True)
        detail = (result.stderr or "").strip()[-1000:]
        raise RuntimeError(f"No se pudo aplicar el watermark: {detail}")
    os.replace(temp_output, source)
    return str(source)
