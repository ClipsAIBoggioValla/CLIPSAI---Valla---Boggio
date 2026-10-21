"""HTTP client for submitting video jobs to a RunPod Serverless endpoint."""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


class RunPodError(RuntimeError):
    """Raised when RunPod configuration or processing fails."""


def is_runpod_configured() -> bool:
    return bool(
        os.getenv("RUNPOD_API_KEY", "").strip()
        and os.getenv("RUNPOD_ENDPOINT_ID", "").strip()
    )


def _settings(endpoint_id: str | None = None) -> tuple[str, str, int, int, float, str]:
    api_key = os.getenv("RUNPOD_API_KEY", "").strip()
    resolved_endpoint_id = (endpoint_id or os.getenv("RUNPOD_ENDPOINT_ID", "")).strip()
    if not api_key:
        raise RunPodError("RUNPOD_API_KEY no está configurada")
    if not resolved_endpoint_id:
        raise RunPodError("RUNPOD_ENDPOINT_ID no está configurado")

    try:
        request_timeout = int(os.getenv("RUNPOD_REQUEST_TIMEOUT_SECONDS", "95"))
        total_timeout = int(os.getenv("RUNPOD_TIMEOUT_SECONDS", "1800"))
        poll_interval = float(os.getenv("RUNPOD_POLL_INTERVAL_SECONDS", "2"))
    except ValueError as exc:
        raise RunPodError("La configuración de timeouts de RunPod no es válida") from exc
    if request_timeout <= 0 or total_timeout <= 0 or poll_interval <= 0:
        raise RunPodError("Los timeouts de RunPod deben ser mayores que cero")

    api_base = os.getenv("RUNPOD_API_BASE_URL", "https://api.runpod.ai/v2").rstrip("/")
    return api_key, resolved_endpoint_id, request_timeout, total_timeout, poll_interval, api_base


def process_local_video_via_runpod(
    video_path: str | Path,
    *,
    transcription_path: str | Path | None = None,
    video_id: str | None = None,
) -> dict[str, Any]:
    """Upload a local source to S3/R2 and process it in RunPod Serverless."""
    source = Path(video_path)
    if not source.is_file():
        raise RunPodError(f"Video fuente inexistente o vacío; no se puede enviar a RunPod: {source}")
    try:
        if source.stat().st_size <= 0:
            raise RunPodError(f"Video fuente inexistente o vacío; no se puede enviar a RunPod: {source}")
    except OSError as exc:
        raise RunPodError(f"No se pudo leer el video fuente para enviarlo a RunPod: {source}") from exc

    transcript_text: str | None = None
    if transcription_path is not None:
        transcript_file = Path(transcription_path)
        if transcript_file.is_file():
            if transcript_file.stat().st_size > 10 * 1024 * 1024:
                raise RunPodError("La transcripción supera el máximo de 10 MB permitido por el worker RunPod")
            transcript_text = transcript_file.read_text(encoding="utf-8", errors="ignore")

    _, _, _, total_timeout, _, _ = _settings()

    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RunPodError("boto3 no está instalado; se necesita para enviar el video local a R2") from exc

    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    endpoint_url = os.getenv("AWS_ENDPOINT_URL", "").strip() or None
    if not access_key or not secret_key:
        raise RunPodError(
            "Faltan AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY para subir el video local a R2 antes de RunPod"
        )

    bucket = os.getenv("BUCKET_NAME", "clipsai-videos").strip()
    key = f"runpod-inputs/{uuid.uuid4().hex}{source.suffix or '.mp4'}"
    s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=os.getenv("AWS_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )
    uploaded = False
    try:
        s3.upload_file(str(source), bucket, key)
        uploaded = True
        video_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=min(max(total_timeout + 600, 3600), 604800),
        )
        return process_video_via_runpod(
            video_url,
            transcription_text=transcript_text,
            video_id=video_id,
        )
    except RunPodError:
        raise
    except Exception as exc:
        raise RunPodError(f"No se pudo subir/procesar el video local mediante RunPod: {exc}") from exc
    finally:
        if uploaded:
            try:
                s3.delete_object(Bucket=bucket, Key=key)
            except Exception:
                pass


def _decode_response(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        body = response.text[:500]
        raise RunPodError(f"RunPod devolvió una respuesta que no es JSON (HTTP {response.status_code}): {body}") from exc
    if not isinstance(data, dict):
        raise RunPodError("RunPod devolvió una respuesta JSON inesperada")
    return data


def _raise_for_job_failure(data: dict[str, Any]) -> None:
    status = str(data.get("status", "")).upper()
    if status in {"FAILED", "CANCELLED", "TIMED_OUT"}:
        error = data.get("error") or data.get("output") or "sin detalle"
        raise RunPodError(f"El job de RunPod terminó con estado {status}: {error}")


def process_video_via_runpod(
    video_url: str,
    *,
    transcription_url: str | None = None,
    transcription_text: str | None = None,
    video_id: str | None = None,
    endpoint_id: str | None = None,
) -> dict[str, Any]:
    """Call ``/runsync`` and poll the job if RunPod returns it as in-progress.

    URLs must be reachable by the RunPod worker. Use public or presigned URLs;
    local filesystem paths from the FastAPI container are not accessible remotely.
    """
    if not isinstance(video_url, str) or not video_url.strip():
        raise ValueError("video_url es obligatorio")
    if transcription_url and transcription_text:
        raise ValueError("Envía transcription_url o transcription_text, no ambos")

    api_key, resolved_endpoint_id, request_timeout, total_timeout, poll_interval, api_base = _settings(endpoint_id)
    endpoint = f"{api_base}/{quote(resolved_endpoint_id, safe='')}/runsync"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    worker_input: dict[str, Any] = {"video_url": video_url.strip()}
    if transcription_url:
        worker_input["transcription_url"] = transcription_url
    if transcription_text is not None:
        worker_input["transcription_text"] = transcription_text
    if video_id:
        worker_input["video_id"] = video_id

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"input": worker_input},
            timeout=request_timeout,
        )
        response.raise_for_status()
        data = _decode_response(response)
    except requests.Timeout as exc:
        raise RunPodError(f"Timeout esperando respuesta inicial de RunPod ({request_timeout}s)") from exc
    except requests.RequestException as exc:
        raise RunPodError(f"No se pudo llamar al endpoint de RunPod: {exc}") from exc

    _raise_for_job_failure(data)
    status = str(data.get("status", "")).upper()
    if status in {"COMPLETED", "SUCCEEDED"}:
        output = data.get("output")
        return output if isinstance(output, dict) else {"output": output, "job_id": data.get("id"), "status": status}

    job_id = data.get("id")
    if not job_id:
        raise RunPodError(f"Respuesta RunPod sin salida ni job id (status={status or 'desconocido'})")

    deadline = time.monotonic() + total_timeout
    status_url = f"{api_base}/{quote(resolved_endpoint_id, safe='')}/status/{quote(str(job_id), safe='')}"
    while time.monotonic() < deadline:
        time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        try:
            response = requests.get(status_url, headers=headers, timeout=request_timeout)
            response.raise_for_status()
            data = _decode_response(response)
        except requests.Timeout as exc:
            raise RunPodError(f"Timeout consultando el job RunPod {job_id}") from exc
        except requests.RequestException as exc:
            raise RunPodError(f"No se pudo consultar el job RunPod {job_id}: {exc}") from exc

        _raise_for_job_failure(data)
        status = str(data.get("status", "")).upper()
        if status in {"COMPLETED", "SUCCEEDED"}:
            output = data.get("output")
            return output if isinstance(output, dict) else {"output": output, "job_id": job_id, "status": status}

    raise RunPodError(f"El job RunPod {job_id} no terminó en {total_timeout}s")
