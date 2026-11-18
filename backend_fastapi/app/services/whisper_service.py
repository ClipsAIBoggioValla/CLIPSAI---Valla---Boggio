from __future__ import annotations

import os
# Timeouts obligatorios para Hugging Face / Whisper (evitar bloqueo indefinido)
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", os.environ.get("HUGGINGFACE_HUB_CACHE", "/tmp/huggingface_cache"))

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class TranscriptionWord(TypedDict):
    start: float
    end: float
    text: str


class TranscriptionSegment(TypedDict):
    start: float
    end: float
    text: str
    words: list[TranscriptionWord]


@dataclass(frozen=True)
class WhisperConfig:
    language: str = "es"
    model_name: str = "large-v3-turbo"
    device: str = "auto"
    compute_type: str = "auto"
    beam_size: int = 5
    vad_filter: bool = True


def _check_ffmpeg() -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg no instalado o no en PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg no disponible: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FFmpeg timeout al verificar version") from exc


def _ffprobe_codec_types(src: Path) -> str | None:
    """stdout de ffprobe con codec_type por stream; None si falla; '' si ffprobe no está (asumir audio)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1", str(src)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        # ffprobe no instalado o error al ejecutar -> asumir que sí tiene audio para no bloquear, Whisper lo detectará
        return ""
    if result.returncode != 0:
        return None
    return result.stdout


def _stdout_tiene_audio(stdout: str | None) -> bool:
    """True si el stdout de ffprobe lista algún stream de audio."""
    if stdout is None:
        return False
    # stdout contiene líneas con codec_type, ej: "video\naudio" o "audio"
    types = [t.strip().lower() for t in stdout.strip().splitlines() if t.strip()]
    return "audio" in types


def _has_audio_track(video_path: str) -> bool:
    """Verifica con FFprobe si el video contiene pista de audio válida.

    Ejecuta: ffprobe -v error -show_entries stream=codec_type -of default=noprint_wrappers=1:nokey=1 /path/to/video.mp4
    Retorna True si encuentra al menos un stream con codec_type=audio.
    """
    src = Path(video_path)
    if not src.is_file():
        return False
    stdout = _ffprobe_codec_types(src)
    if stdout is None:
        return False
    if stdout == "":
        # ffprobe no instalado -> asumir que sí tiene audio para no bloquear, Whisper lo detectará
        return True
    return _stdout_tiene_audio(stdout)


def _validate_video_source(video_path: str) -> Path:
    src = Path(video_path)
    if not src.is_file():
        raise FileNotFoundError(
            f"El archivo de video fuente no existe o no es un archivo: {video_path}. "
            "La descarga o subida del video falló; vuelve a subirlo o verifica la URL de origen."
        )
    try:
        size = src.stat().st_size
    except OSError as exc:
        raise FileNotFoundError(
            f"No se pudo leer el archivo de video fuente {video_path}. "
            "La descarga o subida del video pudo haber fallado."
        ) from exc
    if size <= 0:
        raise ValueError(
            f"El archivo de video fuente está vacío (0 bytes): {video_path}. "
            "La descarga o subida del video falló; vuelve a subirlo o verifica la URL de origen."
        )
    return src


def _wav_tmp_path() -> str:
    """Ruta de un WAV temporal único (delete=False)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    return tmp.name


def _wav_destino(wav_path: str | None) -> Path:
    """Path de salida del WAV (temporal único si no se indica ruta)."""
    if wav_path is None:
        wav_path = _wav_tmp_path()
    out = Path(wav_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def _wav_generado(res, out: Path) -> bool:
    """True si la extracción retornó 0 y produjo un WAV no vacío."""
    return res.returncode == 0 and out.exists() and out.stat().st_size > 0


def _extraer_wav_ffmpeg(src: Path, out: Path) -> None:
    """Ejecuta la extracción WAV principal y, si falla, el fallback. RuntimeError si ambas fallan."""
    # Extraer WAV temporal a 16kHz mono PCM para Whisper (evita fallos de lectura directa MP4)
    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-map", "0:a:0?",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(out),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if _wav_generado(res, out):
        return
    fallback_cmd: list[str] = ["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(out)]
    fb_res = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=180)
    if not _wav_generado(fb_res, out):
        raise RuntimeError(f"Fallo en FFmpeg al extraer audio WAV: {res.stderr} | Fallback: {fb_res.stderr} (WAV 0 bytes)")


def _stderr_de_called_process_error(exc) -> str:
    """stderr decodificado del error de subprocess (o str del error)."""
    if exc.stderr:
        return exc.stderr.decode(errors="ignore")[:1200]
    return str(exc)


def _error_de_extraccion_audio(exc: Exception) -> Exception:
    """Traduce un error de FFmpeg/subprocess a RuntimeError; devuelve exc sin cambios si es desconocido."""
    if isinstance(exc, FileNotFoundError):
        return RuntimeError(f"FFmpeg no instalado: {exc}")
    if isinstance(exc, subprocess.TimeoutExpired):
        return RuntimeError("Timeout 180s extrayendo audio")
    if isinstance(exc, subprocess.CalledProcessError):
        return RuntimeError(f"Extraccion de audio fallida: {_stderr_de_called_process_error(exc)}")
    return exc


def _ejecutar_extraccion(src: Path, out: Path) -> None:
    """Extrae el WAV con FFmpeg; RuntimeError ante fallos de ffmpeg/subprocess."""
    try:
        _extraer_wav_ffmpeg(src, out)
    except Exception as exc:
        translated = _error_de_extraccion_audio(exc)
        if translated is exc:
            raise
        raise translated from exc


def _exigir_wav_valido(out: Path) -> None:
    """RuntimeError si el WAV final no existe o está vacío."""
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"No se genero WAV valido en {out}")


def extract_audio_wav(video_path: str, wav_path: str | None = None) -> str:
    src = _validate_video_source(video_path)
    # Verificación previa de pista de audio antes de extraer (requerido por prompt)
    if not _has_audio_track(video_path):
        raise ValueError("El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.")
    _check_ffmpeg()
    out = _wav_destino(wav_path)
    _ejecutar_extraccion(src, out)
    _exigir_wav_valido(out)
    return str(out)


def _detect_device_and_compute(requested_device: str, requested_compute: str) -> tuple[str, str]:
    if requested_device != "auto" and requested_compute != "auto":
        return (requested_device, requested_compute)
    try:
        import torch

        if torch.cuda.is_available():
            return ("cuda", "float16")
    except Exception:
        pass
    return ("cpu", "int8")


_MODEL_MAP: dict[str, str] = {
    "large-v3-turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
    "turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
    "large-v3": "large-v3",
    "medium": "medium",
    "small": "small",
    "base": "base",
    "tiny": "tiny",
}


def _cargar_modelo_whisper(resolved_model: str, device: str, compute_type: str) -> Any:
    """Importa faster-whisper y carga el modelo. RuntimeError con detalle si falla."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper no instalado. Instalar con: pip install faster-whisper"
        ) from exc
    try:
        return WhisperModel(resolved_model, device=device, compute_type=compute_type, local_files_only=False)
    except Exception as exc:
        raise RuntimeError(f"No se pudo cargar modelo Whisper '{resolved_model}' ({device}/{compute_type}): {exc}") from exc


def _verificar_wav_extraido(wav: Path) -> None:
    """Diagnóstico y verificación de audio antes de Whisper (requerido por prompt)."""
    try:
        import os
        import logging

        wav_size = os.path.getsize(str(wav))
        logging.getLogger(__name__).info(f"Archivo WAV extraído correctamente: {wav} ({wav_size} bytes)")
        if wav_size < 10000:
            raise RuntimeError(f"El archivo WAV extraído está casi vacío o corrupto ({wav_size} bytes). Revisa la fuente del video.")
    except RuntimeError:
        raise
    except Exception:
        pass


def _words_de_segmento(seg: Any) -> list:
    """Lista cruda de words del segmento Whisper (vacía si no hay)."""
    return getattr(seg, "words", None) or []


def _palabra_de_whisper(word) -> TranscriptionWord | None:
    """TranscriptionWord válida de una word de Whisper; None si es inválida."""
    try:
        word_start = float(word.start)
        word_end = float(word.end)
        word_text = str(word.word).strip()
    except (AttributeError, TypeError, ValueError):
        return None
    if word_text and word_end >= word_start:
        return TranscriptionWord(start=word_start, end=word_end, text=word_text)
    return None


def _palabras_de_segmento(seg: Any) -> list[TranscriptionWord]:
    """Convierte las words de un segmento Whisper en TranscriptionWord válidas."""
    word_timings: list[TranscriptionWord] = []
    for word in _words_de_segmento(seg):
        palabra = _palabra_de_whisper(word)
        if palabra is not None:
            word_timings.append(palabra)
    return word_timings


def _texto_crudo_de_segmentos(segments: list) -> str:
    """Texto plano concatenado de los segmentos (para el log de auditoría)."""
    return " ".join([s.get("text","") if isinstance(s, dict) else str(getattr(s, "text", "")) for s in segments])


def _logear_texto_whisper(segments: list) -> None:
    """Log de texto crudo retornado por Whisper para auditoría (silencioso si falla)."""
    try:
        import logging
        raw_text = _texto_crudo_de_segmentos(segments)
        logging.getLogger(__name__).info(f"Texto detectado por Whisper: '{raw_text[:800]}'")
    except Exception:
        pass


def _colectar_segmentos(segments_gen: Any) -> list[TranscriptionSegment]:
    """Itera el generador de Whisper y colecta segmentos con texto y words."""
    segments: list[TranscriptionSegment] = []
    for seg in segments_gen:
        text = str(seg.text).strip()
        if not text:
            continue
        start = float(seg.start)
        end = float(seg.end)
        if end < start:
            end = start + 0.5
        segments.append(
            TranscriptionSegment(start=start, end=end, text=text, words=_palabras_de_segmento(seg))
        )
    # Log de texto crudo retornado por Whisper para auditoría
    _logear_texto_whisper(segments)
    return segments


def _texto_crudo_gen(segments_gen: Any) -> str:
    """Texto crudo del generador de Whisper; vacío si falla la lectura."""
    try:
        return " ".join([str(getattr(s, "text", "")) for s in segments_gen])
    except Exception:
        return ""


def _exigir_segmentos(segments: list[TranscriptionSegment], segments_gen: Any, wav: Path) -> None:
    """Si Whisper no devolvió palabras, inspeccionar antes de error (requerido por prompt)."""
    if segments:
        return
    try:
        import os
        wav_size2 = os.path.getsize(str(wav))
    except Exception:
        wav_size2 = 0
    raw = _texto_crudo_gen(segments_gen)
    raise RuntimeError(f"Whisper procesó el audio ({wav_size2} bytes) pero devolvió 0 segmentos. Texto crudo: '{raw[:500]}'")


def _config_whisper(config: WhisperConfig | None, language: str, model_name: str) -> WhisperConfig:
    """Config efectiva de Whisper (la provista o una nueva con language/model)."""
    return config or WhisperConfig(language=language, model_name=model_name)


def _modelo_resuelto(cfg: WhisperConfig, language: str, model_name: str) -> tuple[str, str, str]:
    """(resolved_model, device, compute_type) para cargar el modelo Whisper."""
    lang = cfg.language or language
    model_id = cfg.model_name or model_name
    resolved_model = _MODEL_MAP.get(model_id, model_id)
    device, compute_type = _detect_device_and_compute(cfg.device, cfg.compute_type)
    return resolved_model, device, compute_type


def _segmentos_de_modelo(model: Any, wav: Path, cfg: WhisperConfig) -> list[TranscriptionSegment]:
    """Ejecuta model.transcribe y colecta/exige los segmentos resultantes."""
    segments_gen, _info = model.transcribe(
        str(wav),
        language="es",
        word_timestamps=True,
        vad_filter=cfg.vad_filter,
        beam_size=5,
        temperature=0.0,
    )
    segments = _colectar_segmentos(segments_gen)
    _exigir_segmentos(segments, segments_gen, wav)
    return segments


def transcribe_wav(
    wav_path: str,
    language: str = "es",
    model_name: str = "large-v3-turbo",
    config: WhisperConfig | None = None,
) -> list[TranscriptionSegment]:
    wav = Path(wav_path)
    if not wav.is_file():
        raise FileNotFoundError(f"WAV no encontrado: {wav_path}")
    cfg = _config_whisper(config, language, model_name)
    resolved_model, device, compute_type = _modelo_resuelto(cfg, language, model_name)
    model = _cargar_modelo_whisper(resolved_model, device, compute_type)
    _verificar_wav_extraido(wav)
    try:
        return _segmentos_de_modelo(model, wav, cfg)
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise RuntimeError(f"Transcripcion fallida: {exc}") from exc


def _exigir_segmentos_runpod(remote_segments) -> None:
    """RuntimeError si RunPod no devolvió una lista no vacía de segmentos."""
    if not isinstance(remote_segments, list) or not remote_segments:
        raise RuntimeError(
            "RunPod no devolvió segmentos de transcripción; actualiza el worker para evitar cargar Whisper localmente en Render."
        )


def _segmento_runpod_normalizado(segment) -> TranscriptionSegment | None:
    """Segmento de RunPod normalizado a TranscriptionSegment; None si es inválido."""
    if not isinstance(segment, dict):
        return None
    try:
        start = float(segment["start"])
        end = float(segment["end"])
        text = str(segment.get("text", "")).strip()
    except (KeyError, TypeError, ValueError):
        return None
    if text and end > start:
        return {"start": start, "end": end, "text": text, "words": []}
    return None


def _segmentos_de_runpod(remote_segments) -> list[TranscriptionSegment]:
    """Segmentos normalizados desde la respuesta de RunPod; RuntimeError si el formato es inválido."""
    _exigir_segmentos_runpod(remote_segments)
    normalized_segments: list[TranscriptionSegment] = []
    for segment in remote_segments:
        normalizado = _segmento_runpod_normalizado(segment)
        if normalizado is not None:
            normalized_segments.append(normalizado)
    if not normalized_segments:
        raise RuntimeError("RunPod devolvió segmentos de transcripción en un formato inválido")
    return normalized_segments


def _transcripcion_via_runpod(video_source: Path) -> list[TranscriptionSegment] | None:
    """Transcripción vía RunPod si está configurado; None si no."""
    from .runpod_service import is_runpod_configured, process_local_video_via_runpod

    if not is_runpod_configured():
        return None
    result = process_local_video_via_runpod(video_source)
    return _segmentos_de_runpod(result.get("transcription_segments"))


def _borrar_wav_temporal(wav_path: str) -> None:
    """Borra el WAV temporal ignorando errores."""
    try:
        Path(wav_path).unlink(missing_ok=True)
    except Exception:
        pass


def _transcripcion_local(video_source: Path, language: str, model_name: str, keep_wav: bool) -> list[TranscriptionSegment]:
    """Transcripción local: WAV temporal + transcribe_wav (borra el WAV salvo keep_wav)."""
    # Verificación previa de pista de audio antes de Whisper (FFprobe)
    if not _has_audio_track(str(video_source)):
        raise ValueError("El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.")
    wav_path = extract_audio_wav(str(video_source))
    try:
        # Extrae WAV temporal a 16kHz mono antes de Whisper (evita fallos lectura directa MP4)
        segments = transcribe_wav(wav_path, language=language, model_name=model_name)
        if not segments:
            raise ValueError("El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.")
        return segments
    finally:
        if not keep_wav:
            _borrar_wav_temporal(wav_path)


def transcribe_video(
    video_path: str,
    language: str = "es",
    model_name: str = "large-v3-turbo",
    keep_wav: bool = False,
) -> list[TranscriptionSegment]:
    video_source = _validate_video_source(video_path)
    via_runpod = _transcripcion_via_runpod(video_source)
    if via_runpod is not None:
        return via_runpod
    return _transcripcion_local(video_source, language, model_name, keep_wav)


def transcribe_audio(wav_path: str, language: str = "es", model_name: str = "large-v3-turbo") -> list[TranscriptionSegment]:
    """Alias requerido por engine.py: transcribe directamente un WAV 16kHz ya extraído."""
    return transcribe_wav(wav_path, language=language, model_name=model_name)


def transcribe_video_to_segments(
    video_path: str,
    language: str = "es",
    model_name: str = "large-v3-turbo",
) -> list[TranscriptionSegment]:
    return transcribe_video(video_path, language=language, model_name=model_name)
