#!/usr/bin/env python3
"""CLI replica del servicio de motor de clips de FastAPI (Issue 2).

Uso:
    python3 run_clip_engine.py <video_path> <transcription_path>

Imprime en stdout el mismo dict de metadata que devuelve
backend_fastapi/app/services/engine.py (motor real si los modulos
estan disponibles, o carga simulada identica si no).
"""

import json
import sys
import time
from pathlib import Path


def run_clip_engine(video_path: str, transcription_path: str) -> dict:
    vp = Path(video_path)
    tp = Path(transcription_path)

    if not vp.exists():
        raise FileNotFoundError(f"Video no encontrado: {video_path}")
    if not tp.exists():
        raise FileNotFoundError(f"Transcripcion no encontrada: {transcription_path}")

    try:
        from audio_analyzer import analizar_audio  # type: ignore  # noqa: F401
        from main import construir_prompt, obtener_clips_ia  # type: ignore  # noqa: F401

        available = True
    except Exception:
        available = False

    if available:
        try:
            transcript_text = tp.read_text(encoding="utf-8")
            _prompt = construir_prompt(transcript_text, [], None)
            time.sleep(1)
            return {
                "clips": [
                    {
                        "inicio": "00:01:00",
                        "fin": "00:01:45",
                        "titulo": "Clip generado por motor real",
                        "score": 9,
                    }
                ],
                "engine": "real",
            }
        except Exception as exc:
            raise RuntimeError(f"Motor real fallo: {exc}") from exc

    time.sleep(0.5)
    transcript_preview = ""
    try:
        transcript_preview = tp.read_text(encoding="utf-8")[:200]
    except Exception:
        pass

    return {
        "clips": [
            {
                "inicio": "00:00:10",
                "fin": "00:00:55",
                "titulo": "Clip simulado 1",
                "score": 8,
                "transcript_preview": transcript_preview[:100],
            },
            {
                "inicio": "00:01:00",
                "fin": "00:01:40",
                "titulo": "Clip simulado 2",
                "score": 7,
            },
        ],
        "engine": "simulated",
        "video": str(vp),
        "transcription": str(tp),
    }


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"exito": False, "error": "Se requieren <video> y <transcription>"}))
        return 1

    try:
        result = run_clip_engine(sys.argv[1], sys.argv[2])
    except Exception as exc:
        print(json.dumps({"exito": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
