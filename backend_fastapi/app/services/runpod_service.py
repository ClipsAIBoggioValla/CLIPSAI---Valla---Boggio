"""HTTP client for submitting video jobs to a RunPod Serverless endpoint."""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from ..services.r2_service import get_r2_client as _r2_get_client

logger = logging.getLogger(__name__)


class RunPodError(RuntimeError):
    """Raised when RunPod configuration or processing fails."""


def is_runpod_configured() -> bool:
    return bool(
        os.getenv("RUNPOD_API_KEY", "").strip()
        and os.getenv("RUNPOD_ENDPOINT_ID", "").strip()
    )


def _credenciales_runpod(endpoint_id: str | None) -> tuple[str, str]:
    """API key y endpoint id resuelto; RunPodError si falta alguno."""
    api_key = os.getenv("RUNPOD_API_KEY", "").strip()
    resolved_endpoint_id = (endpoint_id or os.getenv("RUNPOD_ENDPOINT_ID", "")).strip()
    if not api_key:
        raise RunPodError("RUNPOD_API_KEY no está configurada")
    if not resolved_endpoint_id:
        raise RunPodError("RUNPOD_ENDPOINT_ID no está configurado")
    return api_key, resolved_endpoint_id


def _timeouts_positivos(request_timeout: int, total_timeout: int, poll_interval: float) -> bool:
    """True si alguno de los timeouts no es mayor que cero."""
    return request_timeout <= 0 or total_timeout <= 0 or poll_interval <= 0


def _resolucion_timeouts() -> tuple[int, int, float]:
    """Lee y valida los timeouts de RunPod desde el entorno."""
    try:
        request_timeout = int(os.getenv("RUNPOD_REQUEST_TIMEOUT_SECONDS", "95"))
        total_timeout = int(os.getenv("RUNPOD_TIMEOUT_SECONDS", "1800"))
        poll_interval = float(os.getenv("RUNPOD_POLL_INTERVAL_SECONDS", "2"))
    except ValueError as exc:
        raise RunPodError("La configuración de timeouts de RunPod no es válida") from exc
    if _timeouts_positivos(request_timeout, total_timeout, poll_interval):
        raise RunPodError("Los timeouts de RunPod deben ser mayores que cero")
    return request_timeout, total_timeout, poll_interval


def _settings(endpoint_id: str | None = None) -> tuple[str, str, int, int, float, str]:
    api_key, resolved_endpoint_id = _credenciales_runpod(endpoint_id)
    request_timeout, total_timeout, poll_interval = _resolucion_timeouts()
    api_base = os.getenv("RUNPOD_API_BASE_URL", "https://api.runpod.ai/v2").rstrip("/")
    return api_key, resolved_endpoint_id, request_timeout, total_timeout, poll_interval, api_base


def _validar_video_local(source: Path) -> None:
    """Lanza RunPodError si el video local no existe o está vacío."""
    if not source.is_file():
        raise RunPodError(f"Video fuente inexistente o vacío; no se puede enviar a RunPod: {source}")
    try:
        if source.stat().st_size <= 0:
            raise RunPodError(f"Video fuente inexistente o vacío; no se puede enviar a RunPod: {source}")
    except OSError as exc:
        raise RunPodError(f"No se pudo leer el video fuente para enviarlo a RunPod: {source}") from exc


def _transcripcion_texto_local(transcription_path: str | Path | None) -> str | None:
    """Texto de la transcripción local si cabe en 10 MB; None si no hay."""
    if transcription_path is None:
        return None
    transcript_file = Path(transcription_path)
    if not transcript_file.is_file():
        return None
    if transcript_file.stat().st_size > 10 * 1024 * 1024:
        raise RunPodError("La transcripción supera el máximo de 10 MB permitido por el worker RunPod")
    return transcript_file.read_text(encoding="utf-8", errors="ignore")


def _endpoint_url_s3() -> str | None:
    """Endpoint personalizado de S3/R2; None si no está configurado."""
    return os.getenv("AWS_ENDPOINT_URL", "").strip() or None


def _cliente_s3() -> Any:
    """Cliente S3/R2 configurado con credenciales del entorno (delegado a r2_service).

    Cualquier error de configuración (credenciales faltantes o boto3 ausente)
    se envuelve en RunPodError para que el caller lo maneje de forma unificada.
    """
    try:
        return _r2_get_client()
    except Exception as exc:
        raise RunPodError(str(exc)) from exc


def _borrar_objeto_s3(s3: Any, bucket: str, key: str) -> None:
    """Elimina el objeto subido (ignora fallos)."""
    try:
        s3.delete_object(Bucket=bucket, Key=key)
    except Exception:
        pass


def process_local_video_via_runpod(
    video_path: str | Path,
    *,
    transcription_path: str | Path | None = None,
    video_id: str | None = None,
) -> dict[str, Any]:
    """Upload a local source to S3/R2 and process it in RunPod Serverless."""
    source = Path(video_path)
    _validar_video_local(source)
    transcript_text = _transcripcion_texto_local(transcription_path)

    _, _, _, total_timeout, _, _ = _settings()

    s3 = _cliente_s3()
    bucket = os.getenv("BUCKET_NAME", "clipsai-videos").strip()
    key = f"runpod-inputs/{uuid.uuid4().hex}{source.suffix or '.mp4'}"
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
            _borrar_objeto_s3(s3, bucket, key)


def _start_de_timestamp(ts_str: str) -> float:
    """Convierte 'M:SS' o 'H:MM:SS' (o float) a segundos."""
    ts_parts = ts_str.split(':')
    if len(ts_parts) == 2:
        return int(ts_parts[0]) * 60 + float(ts_parts[1])
    if len(ts_parts) == 3:
        return int(ts_parts[0]) * 3600 + int(ts_parts[1]) * 60 + float(ts_parts[2])
    return float(ts_parts[0])


def _end_desde_siguiente(start: float, next_ts: str, end: float) -> float:
    """Actualiza end con el start del siguiente si es posterior."""
    try:
        next_start = _start_de_timestamp(next_ts)
        if next_start > start:
            return next_start
    except (ValueError, IndexError):
        pass
    return end


def _end_estimado(start: float, siguiente: Any, end: float) -> float:
    """End desde el start del siguiente si es posterior; si no, el dado."""
    if isinstance(siguiente, dict):
        next_ts = str(siguiente.get("timestamp", "")).strip()
        if next_ts:
            return _end_desde_siguiente(start, next_ts, end)
    return end


def _segmento_con_tiempos(seg: dict, text: str) -> dict[str, Any] | None:
    """Segmento normalizado en formato start/end; None si es inválido."""
    try:
        start = float(seg["start"])
        end = float(seg["end"])
    except (ValueError, TypeError):
        return None
    if start < 0 or end <= start:
        return None
    return {"start": round(start, 2), "end": round(end, 2), "text": text}


def _segmento_con_timestamp(seg: dict, text: str, i: int, segments: list) -> dict[str, Any] | None:
    """Segmento normalizado desde timestamp 'M:SS'; None si es inválido."""
    try:
        start = _start_de_timestamp(str(seg["timestamp"]).strip())
    except (ValueError, TypeError, IndexError):
        return None
    if start < 0:
        return None
    # Estimar end: start del siguiente segmento o start + 3.0
    end = start + 3.0
    if i + 1 < len(segments):
        end = _end_estimado(start, segments[i + 1], end)
    return {"start": round(start, 2), "end": round(end, 2), "text": text}


def _segmento_por_formato(
    seg: dict, text: str, i: int, segments: list
) -> tuple[dict[str, Any] | None, str | None]:
    """Devuelve (registro, formato) del primer formato que aplique."""
    # Formato nuevo: start/end como floats
    if "start" in seg and "end" in seg:
        return _segmento_con_tiempos(seg, text), "start/end"
    # Formato viejo: timestamp como string "M:SS" o "H:MM:SS"
    if "timestamp" in seg:
        return _segmento_con_timestamp(seg, text, i, segments), "timestamp"
    return None, None


def _normalizar_item(i: int, seg: dict, segments: list) -> tuple[dict[str, Any] | None, str | None]:
    """(registro, formato) del item; (None, None) si se descarta."""
    text = str(seg.get("text", "")).strip()
    if not text:
        return None, None
    return _segmento_por_formato(seg, text, i, segments)


def _acumular_normalizado(
    normalized: list[dict[str, Any]], registro: dict, formato: str, format_detected: str | None
) -> str | None:
    """Agrega el registro y fija el formato si es el primero. Devuelve el formato vigente."""
    if format_detected is None:
        format_detected = formato
    normalized.append(registro)
    return format_detected


def _log_formato_segmentos(normalized: list[dict], format_detected: str | None) -> None:
    """Loguea el formato detectado de los segmentos normalizados."""
    fmt_label = format_detected if format_detected else "desconocido"
    logger.info("[runpod_service] Recibidos %d segmentos de transcripción (formato detectado: %s)", len(normalized), fmt_label)


def _normalizar_items(segments: list) -> list[dict[str, Any]]:
    """Normaliza cada item; detecta el formato de la primera entrada válida."""
    normalized = []
    format_detected = None
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        registro, formato = _normalizar_item(i, seg, segments)
        if registro is None:
            continue
        format_detected = _acumular_normalizado(normalized, registro, formato, format_detected)
    _log_formato_segmentos(normalized, format_detected)
    return normalized


def _normalize_transcription_segments(segments: list[Any]) -> list[dict[str, Any]]:
    """Normaliza segmentos de transcripción a formato uniforme {"start": float, "end": float, "text": str}.
    
    Acepta dos formatos de entrada:
    a) Formato nuevo: {"start": float, "end": float, "text": str}
    b) Formato viejo: {"timestamp": str, "text": str}
    
    Descarta items sin texto o con tiempos negativos.
    """
    if not isinstance(segments, list):
        return []
    return _normalizar_items(segments)


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


def _video_url_valido(video_url: Any) -> bool:
    """True si video_url es un string no vacío."""
    return isinstance(video_url, str) and bool(video_url.strip())


def _validar_params_runpod(video_url: Any, transcription_url: Any, transcription_text: Any) -> None:
    """Valida la URL y la exclusión mutua de la transcripción."""
    if not _video_url_valido(video_url):
        raise ValueError("video_url es obligatorio")
    if transcription_url and transcription_text:
        raise ValueError("Envía transcription_url o transcription_text, no ambos")


def _worker_input(
    video_url: str,
    transcription_url: str | None,
    transcription_text: str | None,
    video_id: str | None,
) -> dict[str, Any]:
    """Payload de entrada para el worker RunPod."""
    worker_input: dict[str, Any] = {"video_url": video_url.strip()}
    if transcription_url:
        worker_input["transcription_url"] = transcription_url
    if transcription_text is not None:
        worker_input["transcription_text"] = transcription_text
    if video_id:
        worker_input["video_id"] = video_id
    return worker_input


def _llamada_runsync(
    endpoint: str, headers: dict, worker_input: dict, request_timeout: int
) -> dict[str, Any]:
    """POST /runsync y decodificación; RunPodError ante fallo de red/JSON."""
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
    return data


def _salida_completada(output: Any, job_id: Any, status: str) -> dict[str, Any]:
    """Salida del job completado con segmentos normalizados si corresponde."""
    if isinstance(output, dict):
        # Normalizar segmentos de transcripción si existen
        raw_segments = output.get("transcription_segments", [])
        output["transcription_segments"] = _normalize_transcription_segments(raw_segments)
        return output
    return {"output": output, "job_id": job_id, "status": status}


def _consultar_status(
    status_url: str, headers: dict, request_timeout: int, job_id: Any
) -> dict[str, Any]:
    """GET /status/{job_id} y decodificación; RunPodError ante fallo."""
    try:
        response = requests.get(status_url, headers=headers, timeout=request_timeout)
        response.raise_for_status()
        return _decode_response(response)
    except requests.Timeout as exc:
        raise RunPodError(f"Timeout consultando el job RunPod {job_id}") from exc
    except requests.RequestException as exc:
        raise RunPodError(f"No se pudo consultar el job RunPod {job_id}: {exc}") from exc


def _esperar_job(
    status_url: str,
    headers: dict,
    request_timeout: int,
    total_timeout: int,
    poll_interval: float,
    job_id: Any,
) -> dict[str, Any]:
    """Sondea /status hasta COMPLETED/SUCCEEDED; RunPodError si expira."""
    deadline = time.monotonic() + total_timeout
    while time.monotonic() < deadline:
        time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        data = _consultar_status(status_url, headers, request_timeout, job_id)
        _raise_for_job_failure(data)
        status = str(data.get("status", "")).upper()
        if status in {"COMPLETED", "SUCCEEDED"}:
            return _salida_completada(data.get("output"), job_id, status)
    raise RunPodError(f"El job RunPod {job_id} no terminó en {total_timeout}s")


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
    _validar_params_runpod(video_url, transcription_url, transcription_text)

    api_key, resolved_endpoint_id, request_timeout, total_timeout, poll_interval, api_base = _settings(endpoint_id)
    endpoint = f"{api_base}/{quote(resolved_endpoint_id, safe='')}/runsync"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    worker_input = _worker_input(video_url, transcription_url, transcription_text, video_id)

    data = _llamada_runsync(endpoint, headers, worker_input, request_timeout)
    _raise_for_job_failure(data)
    status = str(data.get("status", "")).upper()
    if status in {"COMPLETED", "SUCCEEDED"}:
        return _salida_completada(data.get("output"), data.get("id"), status)

    job_id = data.get("id")
    if not job_id:
        raise RunPodError(f"Respuesta RunPod sin salida ni job id (status={status or 'desconocido'})")

    status_url = f"{api_base}/{quote(resolved_endpoint_id, safe='')}/status/{quote(str(job_id), safe='')}"
    return _esperar_job(status_url, headers, request_timeout, total_timeout, poll_interval, job_id)
