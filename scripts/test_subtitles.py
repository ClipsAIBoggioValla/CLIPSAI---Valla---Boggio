#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def _resolve_video(input_path: str | None) -> Path:
    candidates: list[Path] = []
    if input_path:
        candidates.append(Path(input_path))
    candidates.extend(
        [
            Path("backend/tests/fixtures/sample.mp4"),
            Path("backend_fastapi/tests/fixtures/sample.mp4"),
            Path("tests/fixtures/sample.mp4"),
            Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "sample.mp4",
            Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sample.mp4",
        ]
    )
    for p in candidates:
        if p.is_file():
            return p.resolve()
    raise FileNotFoundError(f"No se encontro video de prueba. Probados: {[str(c) for c in candidates]}")


def _mock_segments(duration: float = 10.0) -> list[dict]:
    texts = [
        "ESTE ES EL HOOK INICIAL DEL VIDEO",
        "SUBTITULOS QUEMADOS EN FORMATO VERTICAL",
        "BORDE OSCURO GRUESO PARA MAXIMA LEGIBILIDAD",
        "TEXTO CENTRADO EN TERCIO INFERIOR 9:16",
        "PRUEBA DE RENDER BURNED-IN CON FFMPEG",
    ]
    step = duration / len(texts)
    segs: list[dict] = []
    for i, t in enumerate(texts):
        segs.append({"start": i * step, "end": (i + 1) * step - 0.15, "text": t})
    return segs


def main() -> None:
    parser = argparse.ArgumentParser(description="Test E2E subtitulado burned-in (ASS + libx264)")
    parser.add_argument("video", nargs="?", default=None, help="Ruta a video mp4 de prueba (opcional, usa fixtures/sample.mp4)")
    parser.add_argument("--out", default=None, help="Ruta de salida mp4 (default temp)")
    parser.add_argument("--mock", action="store_true", help="Usar segmentos mock sin Whisper (rapido)")
    parser.add_argument("--keep", action="store_true", help="No borrar ASS/WAV temporales")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    backend_fastapi_root = root / "backend_fastapi"
    if str(backend_fastapi_root) not in sys.path:
        sys.path.insert(0, str(backend_fastapi_root))

    try:
        video = _resolve_video(args.video)
    except FileNotFoundError as exc:
        sys.exit(1)

    try:
        import subprocess

        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=5)
    except Exception as exc:
        sys.exit(1)

    wav_path: Path | None = None
    ass_path: Path | None = None
    out_path: Path
    if args.out:
        out_path = Path(args.out)
    else:
        tmp = tempfile.NamedTemporaryFile(suffix="_subtitled.mp4", delete=False)
        tmp.close()
        out_path = Path(tmp.name)

    segments: list[dict]
    if args.mock:
        segments = _mock_segments(duration=10.0)
    else:
        try:
            from backend_fastapi.app.services.whisper_service import extract_audio_wav, transcribe_wav

            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_wav.close()
            wav_path = Path(tmp_wav.name)
            extract_audio_wav(str(video), str(wav_path))
            raw = transcribe_wav(str(wav_path), language="es")
            segments = [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in raw]
            if not segments:
                segments = _mock_segments()
        except Exception as exc:
            import traceback

            traceback.print_exc()
            segments = _mock_segments()

    try:
        from backend_fastapi.app.services.ass_generator import write_ass_file

        tmp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False)
        tmp_ass.close()
        ass_path = Path(tmp_ass.name)
        write_ass_file(segments, str(ass_path), title=video.stem)
        for line in ass_path.read_text(encoding="utf-8").splitlines()[:12]:
            pass
    except Exception as exc:
        import traceback

        traceback.print_exc()
        sys.exit(1)

    try:
        from backend_fastapi.app.services.ffmpeg_service import burn_subtitles, escape_subtitles_path

        burn_subtitles(str(video), str(ass_path), str(out_path))
        try:
            from backend_fastapi.app.services.ffmpeg_service import probe_duration

            dur = probe_duration(str(out_path))
            if dur is not None:
                pass
        except Exception:
            pass
        if wav_path:
            pass
    except Exception as exc:
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if not args.keep:
            for p in (wav_path, ass_path):
                if p is not None:
                    try:
                        Path(p).unlink(missing_ok=True)
                    except Exception:
                        pass
        else:


            pass
if __name__ == "__main__":
    main()
