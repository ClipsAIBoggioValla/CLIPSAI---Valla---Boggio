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


def _video_cli_valido(video_argument: str) -> Path:
    """Ruta absoluta del video CLI. FileNotFoundError si no existe."""
    video_path = Path(video_argument).expanduser().resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video no encontrado: {video_path}")
    return video_path


def _transcript_temporal() -> Path:
    """Archivo de transcripción temporal vacío (habilita el fallback de Whisper del engine)."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="clipsai_cli_", encoding="utf-8", delete=False
    ) as transcript_file:
        return Path(transcript_file.name)


def _clip_cli(item: dict, index: int) -> tuple[float, float]:
    """(start, end) del clip CLI. ValueError si los timestamps son inválidos."""
    start = _as_seconds(item.get("start_time", item.get("inicio", item.get("start", 0))))
    end = _as_seconds(item.get("end_time", item.get("fin", item.get("end", 0))))
    if end <= start:
        raise ValueError(f"Clip {index + 1}: timestamps inválidos {start}–{end}")
    return start, end


def _clips_cli_validos(clips: list) -> list[dict]:
    """Clips renderizables del resultado del engine (dicts con datos)."""
    return [c for c in clips if isinstance(c, dict)]


def _renderizar_clip_cli(render: Any, select_hook: Any, clip: dict, index: int, segments: list[dict], video_path: Path, job_id: uuid.UUID) -> Path:
    """Un clip del CLI: hook + render 9:16 con el pipeline de jobs."""
    start, end = _clip_cli(clip, index)
    hook_selection = select_hook(start, end, clip.get("hook_selection") if isinstance(clip.get("hook_selection"), dict) else None)
    output_path, _metadata = render(
        str(video_path),
        start,
        end,
        segments,
        hook_selection,
        job_id,
        index,
        str(clip.get("title") or clip.get("titulo") or "Clip")[:255],
    )
    return Path(output_path).resolve()


def _renderizar_clips_cli(clips: list, segments: list[dict], video_path: Path) -> list[Path]:
    """Renderiza cada clip del resultado del engine con el pipeline de jobs."""
    from .routers.jobs import (
        _render_clip_with_ass_and_hook,
        _select_hook_for_clip,
    )

    job_id = uuid.uuid4()
    generated: list[Path] = []
    for index, clip in enumerate(_clips_cli_validos(clips)):
        logger.debug("Renderizando clip CLI %s", index + 1)
        generated.append(_renderizar_clip_cli(_render_clip_with_ass_and_hook, _select_hook_for_clip, clip, index, segments, video_path, job_id))
    return generated


def _payload_cli(result: Any) -> tuple[list, list]:
    """(clips, segments) del resultado del engine para el CLI. ValueError si no hay clips."""
    clips = _clips_de_resultado(result)
    segments = _segmentos_de_resultado(result)
    if not isinstance(clips, list) or not clips:
        raise RuntimeError("El motor no devolvió clips para renderizar")
    if not isinstance(segments, list):
        segments = []
    return clips, segments


def _clips_de_resultado(result: Any) -> Any:
    """Clips crudos del resultado del engine."""
    return result.get("clips") if isinstance(result, dict) else None


def _segmentos_de_resultado(result: Any) -> Any:
    """Segmentos crudos del resultado del engine."""
    return result.get("transcription_segments", []) if isinstance(result, dict) else []


def run_video(video_argument: str) -> list[Path]:
    """Ejecuta Whisper→Claude y el mismo render crop 9:16+ASS usado por Jobs."""
    video_path = _video_cli_valido(video_argument)

    from .routers.jobs import STORAGE_CLIPS_DIR  # noqa: F401  (conservado por compat)
    from .services.engine import run_clip_engine

    temporary_transcript = _transcript_temporal()
    try:
        # run_clip_engine requiere una ruta de transcripción aunque Whisper la genere
        # directamente desde el video. El archivo vacío solo habilita su fallback.
        def report_progress(progress: int = 35) -> None:
            pass

        result = run_clip_engine(
            str(video_path),
            str(temporary_transcript),
            progress_callback=report_progress,
        )
    finally:
        temporary_transcript.unlink(missing_ok=True)

    clips, segments = _payload_cli(result)
    generated = _renderizar_clips_cli(clips, segments, video_path)
    if not generated:
        raise RuntimeError("No se generaron archivos MP4")
    return generated


def command_run(args: argparse.Namespace) -> int:
    try:
        run_video(args.video)
        return 0
    except Exception as exc:
        logger.exception("Falló el procesamiento CLI: %s", exc)
        return 1


def _job_cli(db, job_id: uuid.UUID) -> Any:
    """Job consultado por el CLI. None si no existe."""
    return db.get(Job, job_id)


def _detalle_de_fallo(job: Any) -> None:
    """Muestra (best-effort) el traceback del fallo guardado en result_metadata."""
    metadata = job.result_metadata if isinstance(job.result_metadata, dict) else {}
    stack_trace = metadata.get("traceback") or metadata.get("stack_trace")
    if stack_trace:
        logger.error("Traceback del fallo:\n%s", str(stack_trace)[:2000])


def _mostrar_estado_job(job: Any) -> None:
    """Muestra el estado del job y su error si falló."""
    if job.error_message:
        logger.error("Error del job: %s", job.error_message)
    if str(job.status).lower() == "failed":
        _detalle_de_fallo(job)


def command_inspect(args: argparse.Namespace) -> int:
    try:
        job_id = uuid.UUID(args.job_id)
    except ValueError:
        return 2

    db = SessionLocal()
    try:
        job = _job_cli(db, job_id)
        if job is None:
            return 1
        _mostrar_estado_job(job)
        return 0
    except SQLAlchemyError as exc:
        logger.exception("No se pudo consultar el Job %s", job_id)
        return 1
    finally:
        db.close()


def _jobs_recientes(db) -> list:
    """Últimos 10 jobs ordenados por fecha descendente."""
    return db.execute(select(Job).order_by(Job.created_at.desc()).limit(10)).scalars().all()


def _imprimir_job(job: Job) -> None:
    """Una línea por job con fecha y error truncado."""
    created_at = job.created_at.isoformat(timespec="seconds") if isinstance(job.created_at, datetime) else "desconocido"
    error = " ".join(str(job.error_message or "").split())
    if len(error) > 72:
        error = error[:69] + "..."
    logger.info("%s  %s  %s", created_at, job.status, error)


def command_list(_args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        jobs = _jobs_recientes(db)
        if not jobs:
            return 0
        for job in jobs:
            _imprimir_job(job)
        return 0
    except SQLAlchemyError as exc:
        logger.exception("No se pudieron listar los Jobs")
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
