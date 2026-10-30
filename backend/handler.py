"""RunPod Serverless handler for the ClipsAI video-analysis engine.

Este handler es COMPLETAMENTE independiente de FastAPI y PostgreSQL.
Solo usa engine.py para procesar video + transcripcion -> clips.
Después de generar clips horizontales, los procesa a verticales 9:16 con subs+hook
y los sube a R2, devolviendo URLs en vez de paths locales.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


# Asegurar que el root del proyecto este en sys.path para importar engine.py
# En RunPod, el codigo se monta en /app
_project_root = os.environ.get("PROJECT_ROOT", "/app")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


MAX_VIDEO_BYTES = 500 * 1024 * 1024
MAX_TRANSCRIPT_BYTES = 10 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
TRANSCRIPT_EXTENSIONS = {".txt", ".srt", ".vtt"}


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
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError(f"boto3 no está instalado: {exc}") from exc
    
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    endpoint_url = os.getenv("AWS_ENDPOINT_URL", "").strip() or None
    
    if not access_key or not secret_key:
        raise RuntimeError("Faltan AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY para subir a R2")
    
    s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=os.getenv("AWS_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )
    
    try:
        print(f"[R2 Upload] Subiendo {file_path} -> {bucket}/{key}")
        s3.upload_file(file_path, bucket, key)
        
        # Construir URL pública
        # Formato: https://<bucket>.<account>.r2.cloudflarestorage.com/<key>
        # O usar endpoint_url si está configurado
        if endpoint_url:
            url = f"{endpoint_url.rstrip('/')}/{bucket}/{key}"
        else:
            # Fallback: construir URL estándar de R2
            # El account ID debe estar en AWS_ACCOUNT_ID
            account_id = os.getenv("AWS_ACCOUNT_ID", "").strip()
            if account_id:
                url = f"https://{bucket}.{account_id}.r2.cloudflarestorage.com/{key}"
            else:
                # Sin account ID, usar endpoint_url o fallar
                raise RuntimeError("AWS_ACCOUNT_ID no configurado y AWS_ENDPOINT_URL vacío")
        
        print(f"[R2 Upload] ✓ Subido: {url}")
        return url
        
    except Exception as exc:
        raise RuntimeError(f"Error subiendo a R2: {exc}") from exc


def _download_file(url: str, destination: Path, max_bytes: int) -> None:
    """Descarga un archivo desde una URL sin cargarlo todo en memoria."""
    total = 0
    try:
        with requests.get(url, stream=True, timeout=(10, 120), allow_redirects=True) as response:
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError(f"El archivo supera el maximo permitido de {max_bytes // (1024 * 1024)} MB")

            with destination.open("wb") as output:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"El archivo supera el maximo permitido de {max_bytes // (1024 * 1024)} MB")
                    output.write(chunk)
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
    print("[RunPod Handler] Iniciando procesamiento...")
    
    if not isinstance(job, dict):
        raise ValueError("El job de RunPod debe ser un objeto JSON")
    
    input_data = job.get("input")
    if not isinstance(input_data, dict):
        raise ValueError("Falta job['input'] con los parametros de procesamiento")

    # Extraer video_url
    video_url = input_data.get("video_url")
    if not isinstance(video_url, str) or not video_url.strip():
        raise ValueError("Falta el parametro obligatorio input.video_url")
    video_url = video_url.strip()
    video_extension = _get_extension(video_url, VIDEO_EXTENSIONS, ".mp4")

    # Extraer transcription_url o transcription_text
    transcript_url = input_data.get("transcription_url")
    if transcript_url is not None and (not isinstance(transcript_url, str) or not transcript_url.strip()):
        raise ValueError("input.transcription_url debe ser una URL no vacia")
    if transcript_url:
        transcript_extension = _get_extension(transcript_url, TRANSCRIPT_EXTENSIONS, ".txt")
    else:
        transcript_extension = ".txt"

    transcript_text = input_data.get("transcription_text")
    if transcript_text is not None and not isinstance(transcript_text, str):
        raise ValueError("input.transcription_text debe ser texto")
    if transcript_text and len(transcript_text.encode("utf-8")) > MAX_TRANSCRIPT_BYTES:
        raise ValueError("input.transcription_text supera el maximo de 10 MB")

    video_id = str(input_data.get("video_id") or uuid.uuid4())
    
    print(f"[RunPod Handler] video_id={video_id}")
    print(f"[RunPod Handler] video_url={video_url[:80]}...")

    with tempfile.TemporaryDirectory(prefix="clipsai_runpod_") as work_dir:
        work_path = Path(work_dir)
        video_path = work_path / f"video{video_extension}"
        transcript_path = work_path / f"transcription{transcript_extension}"

        # Descargar video
        print(f"[RunPod Handler] Descargando video a {video_path}...")
        _download_file(video_url, video_path, MAX_VIDEO_BYTES)
        print(f"[RunPod Handler] Video descargado: {video_path.stat().st_size} bytes")

        # Descargar o escribir transcripcion
        if transcript_url:
            print(f"[RunPod Handler] Descargando transcripcion a {transcript_path}...")
            _download_file(transcript_url, transcript_path, MAX_TRANSCRIPT_BYTES)
            print(f"[RunPod Handler] Transcripcion descargada: {transcript_path.stat().st_size} bytes")
        else:
            print(f"[RunPod Handler] Escribiendo transcripcion desde texto...")
            transcript_path.write_text(transcript_text or "", encoding="utf-8")

        # Importar SOLO engine.py (sin FastAPI, sin DB)
        print("[RunPod Handler] Importando engine.py...")
        from engine import procesar_video

        # Ejecutar el pipeline de procesamiento
        print(f"[RunPod Handler] Ejecutando procesar_video({video_path}, {transcript_path})...")
        result = procesar_video(str(video_path), str(transcript_path))

        if not result.exito:
            error_msg = f"{result.error_tipo}: {result.error}" if result.error_tipo else result.error
            print(f"[RunPod Handler] ERROR: {error_msg}")
            return {
                "status": "FAILED",
                "video_id": video_id,
                "error": error_msg,
                "error_tipo": result.error_tipo,
                "error_detalle": result.error_detalle,
                "transcription_segments": [],
            }

        clips = result.clips
        transcription_segments = getattr(result, 'transcription_segments', None) or []
        print(f"[RunPod Handler] EXITO: {len(clips)} clips horizontales generados, {len(transcription_segments)} segmentos de transcripción")

        # Procesar clips horizontales a verticales 9:16 con subs+hook y subir a R2
        print("[RunPod Handler] Procesando clips verticales 9:16 + subs + hook...")
        from video_processor import process_clip_vertical
        
        bucket = os.getenv("BUCKET_NAME", "clipsai-videos").strip()
        clips_verticales = []
        
        for idx, clip in enumerate(clips):
            print(f"[RunPod Handler] Procesando clip {idx+1}/{len(clips)}...")
            
            # Convertir timestamps de string a segundos
            def ts_to_seconds(ts_str: str) -> float:
                parts = ts_str.split(":")
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    return int(parts[0]) * 60 + float(parts[1])
                return float(ts_str)
            
            clip_start = ts_to_seconds(clip.inicio)
            clip_end = ts_to_seconds(clip.fin)
            
            # Procesar clip vertical
            horizontal_path = clip.archivo
            vertical_path = horizontal_path.replace(".mp4", "_vertical.mp4")
            
            success = process_clip_vertical(
                input_video=str(video_path),
                output_video=vertical_path,
                segments=transcription_segments,
                clip_start=clip_start,
                clip_end=clip_end,
                hook_text=clip.hook_texto if clip.hook_texto else None
            )
            
            if not success or not os.path.exists(vertical_path):
                print(f"[RunPod Handler] ⚠ Clip {idx+1} falló procesamiento vertical, saltando")
                continue
            
            # Subir a R2
            try:
                r2_key = f"clips/{video_id}/{idx}_vertical.mp4"
                r2_url = _upload_to_r2(vertical_path, bucket, r2_key)
                
                clips_verticales.append({
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
                })
                
                print(f"[RunPod Handler] ✓ Clip {idx+1} subido a R2: {r2_url}")
                
            except Exception as exc:
                print(f"[RunPod Handler] ⚠ Error subiendo clip {idx+1} a R2: {exc}")
                continue
        
        print(f"[RunPod Handler] {len(clips_verticales)} clips verticales procesados y subidos a R2")

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
