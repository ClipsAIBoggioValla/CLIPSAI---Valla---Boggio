#!/usr/bin/env python3
"""
Wrapper por subprocess para el motor de clipsai.

Alternativa a la importación directa: invoca engine.py como subprocess
y parsea la salida JSON. Útil si se quiere aislar completamente el motor
(ej. diferentes versiones de Python, memory leaks, timeouts, etc.).

Uso programático:
    from engine_subprocess import procesar_video_subprocess
    resultado = procesar_video_subprocess("video.mp4", "transcripcion.txt")
"""

import subprocess
import json
import sys
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ProcesamientoResultado:
    """Resultado estructurado del procesamiento (compatibilidad con engine.py)."""
    exito: bool
    clips: list
    carpeta_salida: str
    error: Optional[str] = None
    error_tipo: Optional[str] = None
    error_detalle: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exito": self.exito,
            "clips": self.clips,
            "carpeta_salida": self.carpeta_salida,
            "error": self.error,
            "error_tipo": self.error_tipo,
            "error_detalle": self.error_detalle,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcesamientoResultado":
        return cls(
            exito=data.get("exito", False),
            clips=data.get("clips", []),
            carpeta_salida=data.get("carpeta_salida", ""),
            error=data.get("error"),
            error_tipo=data.get("error_tipo"),
            error_detalle=data.get("error_detalle"),
        )


def _error_resultado(error: str, error_tipo: str, error_detalle: str = "") -> ProcesamientoResultado:
    """Resultado de error tipado del wrapper subprocess."""
    return ProcesamientoResultado(
        exito=False, clips=[], carpeta_salida="",
        error=error,
        error_tipo=error_tipo,
        error_detalle=error_detalle,
    )


def _validaciones_previas(video_path: str, transcripcion_path: str) -> tuple:
    """Valida entradas y la existencia de engine.py. Devuelve (engine_path, error|None)."""
    if not os.path.exists(video_path):
        return None, _error_resultado(f"Video no encontrado: {video_path}", "ValidacionError")
    if not os.path.exists(transcripcion_path):
        return None, _error_resultado(f"Transcripción no encontrada: {transcripcion_path}", "ValidacionError")

    # Resolver path absoluto de engine.py
    engine_path = os.path.join(os.path.dirname(__file__), "engine.py")
    if not os.path.exists(engine_path):
        return None, _error_resultado(f"engine.py no encontrado en {engine_path}", "ConfiguracionError")
    return engine_path, None


def _ejecutar_engine_subprocess(cmd: list, timeout_segundos: int) -> tuple:
    """Corre el subprocess con timeout. Devuelve (result|None, error|None)."""
    try:
        # Ejecutar subprocess con timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_segundos
        )
        return result, None
    except subprocess.TimeoutExpired:
        return None, _error_resultado(f"Timeout ({timeout_segundos}s) en procesamiento", "TimeoutError")
    except Exception as e:
        return None, _error_resultado(f"Error ejecutando subprocess: {e}", "SubprocessError")


def _parsear_salida_subprocess(result) -> tuple:
    """Parsea el stdout JSON del subprocess. Devuelve (data|None, error|None)."""
    # Parsear salida JSON (stdout)
    stdout = result.stdout.strip()
    if not stdout:
        return None, _error_resultado(
            "Subprocess no produjo salida",
            "SubprocessError",
            error_detalle=f"stderr: {result.stderr[:500]}"
        )

    try:
        return json.loads(stdout), None
    except json.JSONDecodeError as e:
        return None, _error_resultado(
            f"Salida JSON inválida del subprocess: {e}",
            "ParseError",
            error_detalle=f"stdout: {stdout[:500]}\nstderr: {result.stderr[:500]}"
        )


def procesar_video_subprocess(
    video_path: str,
    transcripcion_path: str,
    timeout_segundos: int = 600,
    python_executable: str = "python3"
) -> ProcesamientoResultado:
    """
    Procesa un video invocando engine.py como subprocess.

    Args:
        video_path: Ruta al archivo de video
        transcripcion_path: Ruta al archivo de transcripción
        timeout_segundos: Timeout máximo para el subprocess (default 10 min)
        python_executable: Ejecutable de Python a usar

    Returns:
        ProcesamientoResultado con el resultado estructurado
    """
    # Validaciones tempranas
    engine_path, error = _validaciones_previas(video_path, transcripcion_path)
    if error is not None:
        return error

    # Construir comando
    cmd = [
        python_executable,
        engine_path,
        video_path,
        transcripcion_path,
        "--json"
    ]

    result, error = _ejecutar_engine_subprocess(cmd, timeout_segundos)
    if error is not None:
        return error

    data, error = _parsear_salida_subprocess(result)
    if error is not None:
        return error

    return ProcesamientoResultado.from_dict(data)


# ============================================================
# CLI para testing
# ============================================================

def _main_cli():
    import argparse

    parser = argparse.ArgumentParser(description="Subprocess wrapper para engine clipsai")
    parser.add_argument("video", help="Ruta al archivo de video")
    parser.add_argument("transcripcion", help="Ruta al archivo de transcripción")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout en segundos")
    parser.add_argument("--python", default="python3", help="Ejecutable Python")
    args = parser.parse_args()


    resultado = procesar_video_subprocess(
        args.video,
        args.transcripcion,
        timeout_segundos=args.timeout,
        python_executable=args.python
    )


    if not resultado.exito:
        sys.exit(1)


if __name__ == "__main__":
    _main_cli()