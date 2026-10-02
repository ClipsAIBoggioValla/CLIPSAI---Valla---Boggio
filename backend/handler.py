"""RunPod Serverless handler for the ClipsAI video-analysis engine."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from backend.core.security.ssrf_guard import SSRFError, validate_url


MAX_VIDEO_BYTES = 500 * 1024 * 1024
MAX_TRANSCRIPT_BYTES = 10 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
TRANSCRIPT_EXTENSIONS = {".txt", ".srt", ".vtt"}


def _download_input(url: str, destination: Path, max_bytes: int) -> None:
    """Download one public input without following redirects or buffering it all in memory."""
    try:
        validate_url(url)
    except SSRFError as exc:
        raise ValueError(f"URL de entrada no permitida: {exc}") from exc

    total = 0
    try:
        with requests.get(url, stream=True, timeout=(10, 120), allow_redirects=False) as response:
            if 300 <= response.status_code < 400:
                raise ValueError("La URL de entrada respondió con una redirección; usa la URL final directa")
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError(f"El archivo supera el máximo permitido de {max_bytes // (1024 * 1024)} MB")

            with destination.open("wb") as output:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"El archivo supera el máximo permitido de {max_bytes // (1024 * 1024)} MB")
                    output.write(chunk)
    except requests.RequestException as exc:
        raise RuntimeError(f"No se pudo descargar el archivo de entrada: {exc}") from exc

    if total == 0:
        raise ValueError("El archivo de entrada está vacío")


def _url_extension(url: str, allowed: set[str], default: str) -> str:
    extension = Path(urlparse(url).path).suffix.lower()
    if not extension:
        return default
    if extension not in allowed:
        raise ValueError(f"Extensión no soportada: {extension}")
    return extension


def _serialize_clip(clip: Any) -> dict[str, Any]:
    if hasattr(clip, "__dict__"):
        raw = vars(clip)
    elif isinstance(clip, dict):
        raw = clip
    else:
        return {"value": str(clip)}

    result: dict[str, Any] = {}
    for key in (
        "inicio",
        "fin",
        "start_time",
        "end_time",
        "duracion",
        "duration",
        "score",
        "titulo",
        "titulo_sugerido",
        "title",
        "criterio_principal",
        "hook_texto",
        "motivo",
        "engine",
        "has_hook",
        "hook_selection",
    ):
        value = raw.get(key)
        if value is not None:
            result[key] = value
    return result


def process_video_job(job: dict[str, Any]) -> dict[str, Any]:
    """Analyze a video URL and return JSON-safe clip candidates and metadata.

    RunPod input example::

        {"input": {
            "video_url": "https://storage.example/video.mp4",
            "transcription_url": "https://storage.example/transcript.txt"
        }}

    Instead of ``transcription_url``, callers may send ``transcription_text``.
    """
    if not isinstance(job, dict):
        raise ValueError("El job de RunPod debe ser un objeto JSON")
    input_data = job.get("input")
    if not isinstance(input_data, dict):
        raise ValueError("Falta job['input'] con los parámetros de procesamiento")

    video_url = input_data.get("video_url")
    if not isinstance(video_url, str) or not video_url.strip():
        raise ValueError("Falta el parámetro obligatorio input.video_url")
    video_url = video_url.strip()
    video_extension = _url_extension(video_url, VIDEO_EXTENSIONS, ".mp4")

    transcript_url = input_data.get("transcription_url")
    if transcript_url is not None and (not isinstance(transcript_url, str) or not transcript_url.strip()):
        raise ValueError("input.transcription_url debe ser una URL no vacía")
    if transcript_url:
        transcript_extension = _url_extension(transcript_url, TRANSCRIPT_EXTENSIONS, ".txt")
    else:
        transcript_extension = ".txt"

    transcript_text = input_data.get("transcription_text")
    if transcript_text is not None and not isinstance(transcript_text, str):
        raise ValueError("input.transcription_text debe ser texto")
    if transcript_text and len(transcript_text.encode("utf-8")) > MAX_TRANSCRIPT_BYTES:
        raise ValueError("input.transcription_text supera el máximo de 10 MB")

    video_id = str(input_data.get("video_id") or uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix="clipsai_runpod_") as work_dir:
        work_path = Path(work_dir)
        video_path = work_path / f"video{video_extension}"
        transcript_path = work_path / f"transcription{transcript_extension}"

        _download_input(video_url, video_path, MAX_VIDEO_BYTES)
        if transcript_url:
            _download_input(transcript_url, transcript_path, MAX_TRANSCRIPT_BYTES)
        else:
            transcript_path.write_text(transcript_text or "", encoding="utf-8")

        # Import after the input is validated/downloaded, so module loading and
        # model initialization happen only for an actual processing request.
        from backend_fastapi.app.services.engine import run_clip_engine

        result = run_clip_engine(str(video_path), str(transcript_path))
        clips = result.get("clips") or []
        return {
            "status": "COMPLETED",
            "video_id": video_id,
            "engine": result.get("engine", "clipsai"),
            "clips": [_serialize_clip(clip) for clip in clips],
            "clip_count": len(clips),
            "transcription_segments_count": len(result.get("transcription_segments") or []),
        }


if __name__ == "__main__":
    import runpod

    runpod.serverless.start({"handler": process_video_job})
