"""RunPod Serverless handler for the ClipsAI video-analysis engine.

Este handler es COMPLETAMENTE independiente de FastAPI y PostgreSQL.
Solo usa engine.py para procesar video + transcripcion -> clips.
Después de generar clips horizontales, los procesa a verticales 9:16 con subs+hook
y los sube a R2, devolviendo URLs en vez de paths locales.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from backend.core.security.ssrf_guard import SSRFError, validate_url


# Asegurar que el root del proyecto este en sys.path para importar engine.py
# En RunPod, el codigo se monta en /app
_project_root = os.environ.get("PROJECT_ROOT", "/app")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# Logger del worker: RunPod captura stdout del contenedor, asi que se escribe a stdout
# en lugar de usar print disperso por el codigo (convencion del proyecto: logging.getLogger).
logger = logging.getLogger("clipsai.handler")
if not logger.handlers:
    _stream_handler = logging.StreamHandler(sys.stdout)
    _stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [clipsai.handler] %(message)s"))
    logger.addHandler(_stream_handler)
logger.setLevel(os.environ.get("CLIPSAI_LOG_LEVEL", "INFO").upper())
logger.propagate = False


MAX_VIDEO_BYTES = 500 * 1024 * 1024
MAX_TRANSCRIPT_BYTES = 10 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
# Redirects seguidos manualmente validando cada hop con el SSRF guard
# (issue #112): allow_redirects=False evita el toctou post-validación.
MAX_REDIRECTS = 5
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
TRANSCRIPT_EXTENSIONS = {".txt", ".srt", ".vtt"}


def _credenciales_r2() -> tuple:
    """Claves AWS del entorno; aborta si falta alguna."""
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()

    if not access_key or not secret_key:
        raise RuntimeError("Faltan AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY para subir a R2")
    return access_key, secret_key


def _cliente_s3():
    """Cliente S3 apuntando a R2 según el entorno."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError(f"boto3 no está instalado: {exc}") from exc

    access_key, secret_key = _credenciales_r2()
    endpoint_url = os.getenv("AWS_ENDPOINT_URL", "").strip() or None

    return boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=os.getenv("AWS_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def _url_publica_r2(key: str) -> str:
    """URL pública del objeto vía custom domain del bucket."""
    # Construir URL PÚBLICA vía custom domain del bucket.
    # R2_PUBLIC_URL (ej: https://videos.clipsai.xyz o el bucket r2.dev para dev).
    # El custom domain ya apunta al bucket: la key va SIN el nombre del bucket.
    # Las URLs *.r2.cloudflarestorage.com son PRIVADAS (403 sin firma) — no se usan.
    public_base_url = os.getenv("R2_PUBLIC_URL", "").strip().rstrip("/")
    if not public_base_url:
        public_base_url = "https://videos.clipsai.xyz"
    return f"{public_base_url}/{key.lstrip('/')}"


def _upload_to_r2(file_path: str, bucket: str, key: str) -> str:
    """Sube un archivo a R2 y devuelve la URL pública.
    
    Args:
        file_path: Ruta local del archivo
        bucket: Nombre del bucket R2
        key: Key del objeto en R2
    
    Returns:
        URL pública del archivo en R2
    
    Raises:
        RuntimeError: Si falla el upload
    """
    s3 = _cliente_s3()

    try:
        logger.info("Subiendo a R2 %s -> %s/%s", file_path, bucket, key)
        s3.upload_file(file_path, bucket, key)

        url = _url_publica_r2(key)

        logger.info("Subido a R2: %s", url)
        return url

    except Exception as exc:
        raise RuntimeError(f"Error subiendo a R2: {exc}") from exc


def _validar_content_length(response, max_bytes: int) -> None:
    """Aborta si el Content-Length del response supera el máximo."""
    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > max_bytes:
        raise ValueError(f"El archivo supera el maximo permitido de {max_bytes // (1024 * 1024)} MB")


def _copiar_chunks(response, output, max_bytes: int) -> int:
    """Escribe los chunks del response en el archivo y devuelve el total."""
    total = 0
    for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"El archivo supera el maximo permitido de {max_bytes // (1024 * 1024)} MB")
        output.write(chunk)
    return total


def _validar_url_entrada(url: str, tipo: str) -> str:
    """Valida una URL con el SSRF guard y registra el resultado."""
    try:
        validate_url(url)
    except SSRFError:
        logger.warning("URL de %s rechazada por SSRF guard: %s", tipo, url)
        raise
    logger.info("URL de %s validada por SSRF guard", tipo)
    return url


def _estado_es_redirect(response) -> bool:
    """True si la respuesta HTTP es un redirect 3xx."""
    return 300 <= response.status_code < 400


def _location_validada(url_actual: str, response) -> str:
    """Location absoluto del redirect, validado con el SSRF guard."""
    location = response.headers.get("Location", "").strip()
    if not location:
        raise SSRFError(f"Redirect {response.status_code} sin Location: {url_actual}")
    destino = urljoin(url_actual, location)
    validate_url(destino)
    logger.warning("Redirect %s -> %s (validado por SSRF guard)", url_actual, destino)
    return destino


def _descargar_hops(url: str, destination: Path, max_bytes: int) -> int:
    """Descarga siguiendo redirects manualmente, validando cada hop (SSRF).

    allow_redirects=False: cada 3xx se cierra con el context manager y el
    siguiente hop se re-valida antes del GET, sin toctou post-validación.
    """
    for _ in range(MAX_REDIRECTS + 1):
        with requests.get(url, stream=True, timeout=(10, 120), allow_redirects=False) as response:
            if _estado_es_redirect(response):
                url = _location_validada(url, response)
                continue
            response.raise_for_status()
            _validar_content_length(response, max_bytes)
            with destination.open("wb") as output:
                return _copiar_chunks(response, output, max_bytes)
    raise SSRFError(f"Demasiados redirects (>{MAX_REDIRECTS}) en {url}")


def _descargar_stream(url: str, destination: Path, max_bytes: int) -> int:
    """Valida la URL con el SSRF guard y descarga el stream a destino."""
    _validar_url_entrada(url, "descarga")
    return _descargar_hops(url, destination, max_bytes)


def _download_file(url: str, destination: Path, max_bytes: int) -> None:
    """Descarga un archivo desde una URL sin cargarlo todo en memoria."""
    total = 0
    try:
        total = _descargar_stream(url, destination, max_bytes)
    except SSRFError as exc:
        raise RuntimeError(f"URL rechazada por SSRF guard: {exc}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"No se pudo descargar el archivo de entrada: {exc}") from exc

    if total == 0:
        raise ValueError("El archivo de entrada esta vacio")


def _get_extension(url: str, allowed: set[str], default: str) -> str:
    """Extrae la extension de una URL y valida que sea permitida."""
    extension = Path(urlparse(url).path).suffix.lower()
    if not extension:
        return default
    if extension not in allowed:
        raise ValueError(f"Extension no soportada: {extension}")
    return extension


def _serialize_clip(clip: Any) -> dict[str, Any]:
    """Serializa un ClipInfo (dataclass) a diccionario."""
    if hasattr(clip, "__dict__"):
        return vars(clip)
    elif isinstance(clip, dict):
        return clip
    else:
        return {"value": str(clip)}


def _validar_input(job: dict[str, Any]) -> dict[str, Any]:
    """Valida la forma del job y devuelve su input."""
    if not isinstance(job, dict):
        raise ValueError("El job de RunPod debe ser un objeto JSON")

    input_data = job.get("input")
    if not isinstance(input_data, dict):
        raise ValueError("Falta job['input'] con los parametros de procesamiento")
    return input_data


def _video_url_de(input_data: dict[str, Any]) -> tuple:
    """(video_url limpia, extension) validados del input (incluye SSRF guard)."""
    # Extraer video_url
    video_url = input_data.get("video_url")
    if not isinstance(video_url, str) or not video_url.strip():
        raise ValueError("Falta el parametro obligatorio input.video_url")
    video_url = video_url.strip()
    _validar_url_entrada(video_url, "video")
    video_extension = _get_extension(video_url, VIDEO_EXTENSIONS, ".mp4")
    return video_url, video_extension


def _url_transcripcion_invalida(transcript_url: Any) -> bool:
    """True si transcription_url viene y no es una URL no vacía."""
    return transcript_url is not None and (not isinstance(transcript_url, str) or not transcript_url.strip())


def _validar_transcript_url(input_data: dict[str, Any]) -> str | None:
    """Valida transcription_url del input (SSRF incluido); None si no viene."""
    transcript_url = input_data.get("transcription_url")
    if _url_transcripcion_invalida(transcript_url):
        raise ValueError("input.transcription_url debe ser una URL no vacia")
    if transcript_url:
        transcript_url = transcript_url.strip()
        _validar_url_entrada(transcript_url, "transcripcion")
    return transcript_url


def _extension_transcripcion(transcript_url: str | None) -> str:
    """Extension permitida de la transcripción; '.txt' por defecto."""
    if transcript_url:
        return _get_extension(transcript_url, TRANSCRIPT_EXTENSIONS, ".txt")
    return ".txt"


def _validar_tipo_transcript_text(transcript_text: Any) -> None:
    """Aborta si transcription_text no es texto."""
    if transcript_text is not None and not isinstance(transcript_text, str):
        raise ValueError("input.transcription_text debe ser texto")


def _validar_tamano_transcript_text(transcript_text: str) -> None:
    """Aborta si transcription_text supera el máximo permitido."""
    if transcript_text and len(transcript_text.encode("utf-8")) > MAX_TRANSCRIPT_BYTES:
        raise ValueError("input.transcription_text supera el maximo de 10 MB")


def _transcript_text_de(input_data: dict[str, Any]) -> str | None:
    """Valida y devuelve transcription_text del input."""
    transcript_text = input_data.get("transcription_text")
    _validar_tipo_transcript_text(transcript_text)
    _validar_tamano_transcript_text(transcript_text)
    return transcript_text


def _resultado_fallo(result, video_id: str) -> dict[str, Any]:
    """Respuesta FAILED a partir del resultado del engine."""
    error_msg = f"{result.error_tipo}: {result.error}" if result.error_tipo else result.error
    logger.error("procesar_video fallo: %s", error_msg)
    return {
        "status": "FAILED",
        "video_id": video_id,
        "error": error_msg,
        "error_tipo": result.error_tipo,
        "error_detalle": result.error_detalle,
        "transcription_segments": [],
    }


def _descargar_transcripcion(transcript_url: str | None, transcript_text: str | None, transcript_path: Path) -> None:
    """Descarga la transcripción de la URL o escribe el texto provisto."""
    # Descargar o escribir transcripcion
    if transcript_url:
        logger.info("Descargando transcripcion a %s...", transcript_path)
        _download_file(transcript_url, transcript_path, MAX_TRANSCRIPT_BYTES)
        logger.info("Transcripcion descargada: %s bytes", transcript_path.stat().st_size)
    else:
        logger.info("Escribiendo transcripcion desde texto...")
        transcript_path.write_text(transcript_text or "", encoding="utf-8")


def _ts_a_segundos_handler(ts_str: str) -> float:
    """Convierte 'HH:MM:SS', 'MM:SS' o segundos sueltos a float."""
    parts = ts_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(ts_str)


def _clip_vertical_dict(idx: int, clip: Any, r2_url: str, clip_start: float, clip_end: float) -> dict[str, Any]:
    """Entrada del clip vertical para la respuesta del handler."""
    return {
        "index": idx,
        "url_r2": r2_url,
        "titulo": clip.titulo_sugerido,
        "hook_texto": clip.hook_texto,
        "score": clip.score,
        "inicio": clip.inicio,
        "fin": clip.fin,
        "duracion": int(clip_end - clip_start),
        "criterio_principal": clip.criterio_principal,
        "primer_segundo": clip.primer_segundo,
        "motivo": clip.motivo,
    }


def _hook_texto_de(clip: Any) -> str | None:
    """Hook del clip o None si esta vacio."""
    return clip.hook_texto or None


def _subir_clip_a_r2(vertical_path: str, idx: int, bucket: str, video_id: str, clip: Any, clip_start: float, clip_end: float) -> dict[str, Any] | None:
    """Sube el clip vertical a R2; None si falla el upload."""
    try:
        r2_key = f"clips/{video_id}/{idx}_vertical.mp4"
        r2_url = _upload_to_r2(vertical_path, bucket, r2_key)

        logger.info("Clip %s subido a R2: %s", idx + 1, r2_url)

        return _clip_vertical_dict(idx, clip, r2_url, clip_start, clip_end)

    except Exception as exc:
        logger.warning("Error subiendo clip %s a R2: %s", idx + 1, exc)
        return None


def _procesar_clip_vertical(video_path: str, transcription_segments: list, clip: Any, idx: int, bucket: str, video_id: str) -> dict[str, Any] | None:
    """Procesa un clip a vertical 9:16 con subs+hook y lo sube a R2. None si falla."""
    from video_processor import process_clip_vertical

    # Convertir timestamps de string a segundos
    clip_start = _ts_a_segundos_handler(clip.inicio)
    clip_end = _ts_a_segundos_handler(clip.fin)

    # Procesar clip vertical
    horizontal_path = clip.archivo
    vertical_path = horizontal_path.replace(".mp4", "_vertical.mp4")

    success = process_clip_vertical(
        input_video=str(video_path),
        output_video=vertical_path,
        segments=transcription_segments,
        clip_start=clip_start,
        clip_end=clip_end,
        hook_text=_hook_texto_de(clip)
    )

    if not success or not os.path.exists(vertical_path):
        logger.warning("Clip %s fallo el procesamiento vertical, saltando", idx + 1)
        return None

    return _subir_clip_a_r2(vertical_path, idx, bucket, video_id, clip, clip_start, clip_end)


MAX_RENDER_WORKERS = 3


def _procesar_clips_verticales(video_path: str, transcription_segments: list, clips: list, bucket: str, video_id: str) -> list:
    """Procesa los clips en paralelo (ThreadPoolExecutor) preservando el orden.

    El trabajo es subprocess-bound (ffmpeg/R2), así que threads no compiten por
    el GIL; cada clip usa su propio TemporaryDirectory y paths únicos, sin
    colisiones entre workers.
    """
    with ThreadPoolExecutor(max_workers=MAX_RENDER_WORKERS) as pool:
        futures = {
            idx: pool.submit(_procesar_clip_vertical, video_path, transcription_segments, clip, idx, bucket, video_id)
            for idx, clip in enumerate(clips)
        }
        resultados = [futuro.result() for futuro in futures.values()]
    return _filtrar_verticales(resultados)


def _filtrar_verticales(resultados: list) -> list:
    """Descarta los Nones (clips fallidos) preservando el orden original."""
    return [resultado for resultado in resultados if resultado is not None]


def process_video_job(job: dict[str, Any]) -> dict[str, Any]:
    """Handler principal de RunPod.

    Recibe un job con video_url y transcription_url/transcription_text,
    descarga los archivos, ejecuta engine.py, y retorna los clips generados.

    RunPod input example:
        {"input": {
            "video_url": "https://storage.example/video.mp4",
            "transcription_url": "https://storage.example/transcript.txt"
        }}

    O alternativamente:
        {"input": {
            "video_url": "https://storage.example/video.mp4",
            "transcription_text": "0:00 - Primer segmento\n0:30 - Segundo..."
        }}
    """
    logger.info("Iniciando procesamiento...")

    input_data = _validar_input(job)

    video_url, video_extension = _video_url_de(input_data)

    # Extraer transcription_url o transcription_text
    transcript_url = _validar_transcript_url(input_data)
    transcript_extension = _extension_transcripcion(transcript_url)
    transcript_text = _transcript_text_de(input_data)

    video_id = str(input_data.get("video_id") or uuid.uuid4())

    logger.info("video_id=%s | video_url=%s...", video_id, video_url[:80])

    with tempfile.TemporaryDirectory(prefix="clipsai_runpod_") as work_dir:
        work_path = Path(work_dir)
        video_path = work_path / f"video{video_extension}"
        transcript_path = work_path / f"transcription{transcript_extension}"

        # Descargar video
        logger.info("Descargando video a %s...", video_path)
        _download_file(video_url, video_path, MAX_VIDEO_BYTES)
        logger.info("Video descargado: %s bytes", video_path.stat().st_size)

        _descargar_transcripcion(transcript_url, transcript_text, transcript_path)

        # Importar SOLO engine.py (sin FastAPI, sin DB)
        logger.info("Importando engine.py...")
        from engine import procesar_video

        # Ejecutar el pipeline de procesamiento
        logger.info("Ejecutando procesar_video(%s, %s)...", video_path, transcript_path)
        result = procesar_video(str(video_path), str(transcript_path))

        if not result.exito:
            return _resultado_fallo(result, video_id)

        bucket = os.getenv("BUCKET_NAME", "clipsai-videos").strip()
        return _respuesta_completa(result, video_id, video_path, bucket)


def _respuesta_completa(result, video_id: str, video_path: Path, bucket: str) -> dict[str, Any]:
    """Procesa los clips del engine a verticales 9:16 y arma la respuesta COMPLETED."""
    clips = result.clips
    transcription_segments = getattr(result, 'transcription_segments', None) or []
    logger.info(
        "Engine OK: %s clips horizontales generados, %s segmentos de transcripción",
        len(clips),
        len(transcription_segments),
    )

    # Procesar clips horizontales a verticales 9:16 con subs+hook y subir a R2
    logger.info("Procesando clips verticales 9:16 + subs + hook...")
    from video_processor import process_clip_vertical

    clips_verticales = _procesar_clips_verticales(video_path, transcription_segments, clips, bucket, video_id)

    logger.info("%s clips verticales procesados y subidos a R2", len(clips_verticales))

    response = {
        "status": "COMPLETED",
        "video_id": video_id,
        "engine": "clipsai_native",
        "clips": clips_verticales,
        "clip_count": len(clips_verticales),
        "output_folder": result.carpeta_salida,
        "transcription_segments": transcription_segments,
    }

    # Mensaje informativo si no hay clips
    if len(clips_verticales) == 0:
        response["message"] = "No se pudieron procesar clips verticales. Revisa los logs para más detalles."

    return response


# Alias para compatibilidad con runpod.serverless.start({"handler": handler})
handler = process_video_job


if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler})
