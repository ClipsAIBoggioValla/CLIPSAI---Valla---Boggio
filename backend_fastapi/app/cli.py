"""Herramientas CLI para ejecutar el pipeline e inspeccionar Jobs.

Uso desde ``backend_fastapi``:
    python -m app.cli run --video /ruta/video.mp4
    python -m app.cli inspect --job-id <UUID>
    python -m app.cli list
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .database import SessionLocal
from .models import Job

logger = logging.getLogger("clipsai.cli")


def _as_seconds(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if ":" not in text:
        return float(text)
    parts = text.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    raise ValueError(f"Timestamp inválido: {value!r}")


def run_video(video_argument: str) -> list[Path]:
    """Ejecuta Whisper→Claude y el mismo render crop 9:16+ASS usado por Jobs."""
    video_path = Path(video_argument).expanduser().resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video no encontrado: {video_path}")

    from .routers.jobs import (
        STORAGE_CLIPS_DIR,
        _render_clip_with_ass_and_hook,
        _select_hook_for_clip,
    )
    from .services.engine import run_clip_engine

    print(f"[1/3] Preparando video: {video_path}", flush=True)
    temporary_transcript: Path | None = None
    try:
        # run_clip_engine requiere una ruta de transcripción aunque Whisper la genere
        # directamente desde el video. El archivo vacío solo habilita su fallback.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix="clipsai_cli_", encoding="utf-8", delete=False
        ) as transcript_file:
            temporary_transcript = Path(transcript_file.name)

        def report_progress(progress: int = 35) -> None:
            print(f"[motor] Whisper completado — progreso {progress}%", flush=True)

        print("[2/3] Ejecutando Whisper y selección semántica Claude...", flush=True)
        result = run_clip_engine(
            str(video_path),
            str(temporary_transcript),
            progress_callback=report_progress,
        )
    finally:
        if temporary_transcript is not None:
            temporary_transcript.unlink(missing_ok=True)

    clips = result.get("clips") if isinstance(result, dict) else None
    segments = result.get("transcription_segments", []) if isinstance(result, dict) else []
    if not isinstance(clips, list) or not clips:
        raise RuntimeError("El motor no devolvió clips para renderizar")
    if not isinstance(segments, list):
        segments = []

    job_id = uuid.uuid4()
    generated: list[Path] = []
    print(f"[3/3] Renderizando {len(clips)} clip(s): recorte → hook → crop 9:16 → ASS", flush=True)
    for index, clip in enumerate(clips):
        if not isinstance(clip, dict):
            logger.warning("Se omite el resultado %s porque no es un objeto de clip", index + 1)
            continue
        start = _as_seconds(clip.get("start_time", clip.get("inicio", clip.get("start", 0))))
        end = _as_seconds(clip.get("end_time", clip.get("fin", clip.get("end", 0))))
        if end <= start:
            raise ValueError(f"Clip {index + 1}: timestamps inválidos {start}–{end}")
        hook_selection = _select_hook_for_clip(
            start,
            end,
            clip.get("hook_selection") if isinstance(clip.get("hook_selection"), dict) else None,
        )
        output_path, metadata = _render_clip_with_ass_and_hook(
            str(video_path),
            start,
            end,
            segments,
            hook_selection,
            job_id,
            index,
            str(clip.get("title") or clip.get("titulo") or "Clip")[:255],
        )
        path = Path(output_path).resolve()
        generated.append(path)
        print(
            f"  Clip {index + 1}/{len(clips)}: {path} "
            f"(render={metadata.get('render')}, ratio={metadata.get('aspect_ratio', '9:16')})",
            flush=True,
        )

    if not generated:
        raise RuntimeError("No se generaron archivos MP4")
    print("Archivos MP4 generados:", flush=True)
    for path in generated:
        print(path, flush=True)
    return generated


def command_run(args: argparse.Namespace) -> int:
    try:
        run_video(args.video)
        return 0
    except Exception as exc:
        logger.exception("Falló el procesamiento CLI: %s", exc)
        return 1


def command_inspect(args: argparse.Namespace) -> int:
    try:
        job_id = uuid.UUID(args.job_id)
    except ValueError:
        print(f"ID de Job inválido: {args.job_id}", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            print(f"Job no encontrado: {job_id}", file=sys.stderr)
            return 1
        print(f"ID:       {job.id}")
        print(f"Estado:   {str(job.status).upper()}")
        print(f"Progreso: {job.progress}%")
        print(f"Creado:   {job.created_at.isoformat() if job.created_at else 'desconocido'}")
        if job.error_message:
            print(f"Error:\n{job.error_message}")
        if str(job.status).lower() == "failed":
            metadata = job.result_metadata if isinstance(job.result_metadata, dict) else {}
            stack_trace = metadata.get("traceback") or metadata.get("stack_trace")
            if stack_trace:
                print(f"Stack trace:\n{stack_trace}")
        return 0
    except SQLAlchemyError as exc:
        logger.exception("No se pudo consultar el Job %s", job_id)
        print(f"Error de base de datos: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def command_list(_args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        jobs = db.execute(select(Job).order_by(Job.created_at.desc()).limit(10)).scalars().all()
        if not jobs:
            print("No hay Jobs registrados.")
            return 0

        print(f"{'ID':36} {'ESTADO':12} {'FECHA':25} ERROR")
        print("-" * 120)
        for job in jobs:
            created_at = job.created_at.isoformat(timespec="seconds") if isinstance(job.created_at, datetime) else "desconocido"
            error = " ".join(str(job.error_message or "").split())
            if len(error) > 72:
                error = error[:69] + "..."
            print(f"{str(job.id):36} {str(job.status).upper():12} {created_at:25} {error}")
        return 0
    except SQLAlchemyError as exc:
        logger.exception("No se pudieron listar los Jobs")
        print(f"Error de base de datos: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Procesa videos e inspecciona Jobs de ClipsAI desde consola.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="Procesar un video directamente")
    run_parser.add_argument("--video", required=True, help="Ruta del video fuente")
    run_parser.set_defaults(handler=command_run)

    inspect_parser = commands.add_parser("inspect", help="Consultar estado y error de un Job")
    inspect_parser.add_argument("--job-id", required=True, help="UUID del Job")
    inspect_parser.set_defaults(handler=command_inspect)

    list_parser = commands.add_parser("list", help="Listar los 10 Jobs más recientes")
    list_parser.set_defaults(handler=command_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
