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


def _has_audio_track(video_path: str) -> bool:
    """Verifica con FFprobe si el video contiene pista de audio válida.

    Ejecuta: ffprobe -v error -show_entries stream=codec_type -of default=noprint_wrappers=1:nokey=1 /path/to/video.mp4
    Retorna True si encuentra al menos un stream con codec_type=audio.
    """
    src = Path(video_path)
    if not src.is_file():
        return False
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1", str(src)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        # stdout contiene líneas con codec_type, ej: "video\naudio" o "audio"
        types = [t.strip().lower() for t in result.stdout.strip().splitlines() if t.strip()]
        return "audio" in types
    except FileNotFoundError:
        # ffprobe no instalado -> asumir que sí tiene audio para no bloquear, Whisper lo detectará
        return True
    except Exception:
        return True


def extract_audio_wav(video_path: str, wav_path: str | None = None) -> str:
    if not os.path.exists(video_path):
        raise RuntimeError(f"El archivo de video NO existe en la ruta del contenedor: {video_path}")
    src = Path(video_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video no encontrado: {video_path}")
    # Verificación previa de pista de audio antes de extraer (requerido por prompt)
    if not _has_audio_track(video_path):
        raise ValueError("El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.")
    _check_ffmpeg()
    if wav_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        wav_path = tmp.name
    out = Path(wav_path)
    out.parent.mkdir(parents=True, exist_ok=True)
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
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            fallback_cmd: list[str] = ["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(out)]
            fb_res = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=180)
            if fb_res.returncode != 0 or not out.exists() or out.stat().st_size == 0:
                raise RuntimeError(f"Fallo en FFmpeg al extraer audio WAV: {res.stderr} | Fallback: {fb_res.stderr} (WAV 0 bytes)")
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError(f"Fallo en FFmpeg al extraer audio WAV: {res.stderr} (0 bytes)")
    except RuntimeError:
        raise
    except FileNotFoundError as exc:
        raise RuntimeError(f"FFmpeg no instalado: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        err = exc.stderr.decode(errors="ignore")[:1200] if exc.stderr else str(exc)
        raise RuntimeError(f"Extraccion de audio fallida: {err}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timeout 180s extrayendo audio") from exc
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"No se genero WAV valido en {out}")
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


def transcribe_wav(
    wav_path: str,
    language: str = "es",
    model_name: str = "large-v3-turbo",
    config: WhisperConfig | None = None,
) -> list[TranscriptionSegment]:
    wav = Path(wav_path)
    if not wav.is_file():
        raise FileNotFoundError(f"WAV no encontrado: {wav_path}")
    cfg = config or WhisperConfig(language=language, model_name=model_name)
    lang = cfg.language or language
    model_id = cfg.model_name or model_name
    resolved_model = _MODEL_MAP.get(model_id, model_id)
    device, compute_type = _detect_device_and_compute(cfg.device, cfg.compute_type)
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper no instalado. Instalar con: pip install faster-whisper"
        ) from exc
    try:
        model = WhisperModel(resolved_model, device=device, compute_type=compute_type, local_files_only=True)
    except Exception as exc:
        raise RuntimeError(f"No se pudo cargar modelo Whisper '{resolved_model}' ({device}/{compute_type}): {exc}") from exc
    # Diagnóstico y verificación de audio antes de Whisper (requerido por prompt)
    try:
        import os
        wav_size = os.path.getsize(str(wav))
        import logging
        logging.getLogger(__name__).info(f"Archivo WAV extraído correctamente: {wav} ({wav_size} bytes)")
        if wav_size < 10000:
            raise RuntimeError(f"El archivo WAV extraído está casi vacío o corrupto ({wav_size} bytes). Revisa la fuente del video.")
    except RuntimeError:
        raise
    except Exception:
        pass
    try:
        segments_gen, _info = model.transcribe(
            str(wav),
            language="es",
            word_timestamps=True,
            vad_filter=cfg.vad_filter,
            beam_size=5,
            temperature=0.0,
        )
        segments: list[TranscriptionSegment] = []
        for seg in segments_gen:
            text = str(seg.text).strip()
            if not text:
                continue
            start = float(seg.start)
            end = float(seg.end)
            if end < start:
                end = start + 0.5
            word_timings: list[TranscriptionWord] = []
            for word in getattr(seg, "words", None) or []:
                try:
                    word_start = float(word.start)
                    word_end = float(word.end)
                    word_text = str(word.word).strip()
                    if word_text and word_end >= word_start:
                        word_timings.append(
                            TranscriptionWord(start=word_start, end=word_end, text=word_text)
                        )
                except (AttributeError, TypeError, ValueError):
                    continue
            segments.append(
                TranscriptionSegment(start=start, end=end, text=text, words=word_timings)
            )
        # Log de texto crudo retornado por Whisper para auditoría
        try:
            import logging
            raw_text = " ".join([s.get("text","") if isinstance(s, dict) else str(getattr(s, "text", "")) for s in segments])
            logging.getLogger(__name__).info(f"Texto detectado por Whisper: '{raw_text[:800]}'")
        except Exception:
            pass
        # Si Whisper no devolvió palabras, inspeccionar antes de error (requerido por prompt)
        if not segments:
            try:
                import os
                wav_size2 = os.path.getsize(str(wav))
            except Exception:
                wav_size2 = 0
            try:
                raw = " ".join([str(getattr(s, "text", "")) for s in segments_gen]) if "segments_gen" in locals() else ""
            except Exception:
                raw = ""
            raise RuntimeError(f"Whisper procesó el audio ({wav_size2} bytes) pero devolvió 0 segmentos. Texto crudo: '{raw[:500]}'")
        return segments
    except ValueError:
        raise
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Transcripcion fallida: {exc}") from exc


def transcribe_video(
    video_path: str,
    language: str = "es",
    model_name: str = "large-v3-turbo",
    keep_wav: bool = False,
) -> list[TranscriptionSegment]:
    # Verificación previa de pista de audio antes de Whisper (FFprobe)
    if not _has_audio_track(video_path):
        raise ValueError("El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.")
    wav_path: str | None = None
    try:
        # Extrae WAV temporal a 16kHz mono antes de Whisper (evita fallos lectura directa MP4)
        wav_path = extract_audio_wav(video_path)
        segments = transcribe_wav(wav_path, language=language, model_name=model_name)
        if not segments:
            raise ValueError("El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.")
        return segments
    except ValueError:
        raise
    finally:
        if wav_path and not keep_wav:
            try:
                Path(wav_path).unlink(missing_ok=True)
            except Exception:
                pass


def transcribe_audio(wav_path: str, language: str = "es", model_name: str = "large-v3-turbo") -> list[TranscriptionSegment]:
    """Alias requerido por engine.py: transcribe directamente un WAV 16kHz ya extraído."""
    return transcribe_wav(wav_path, language=language, model_name=model_name)


def transcribe_video_to_segments(
    video_path: str,
    language: str = "es",
    model_name: str = "large-v3-turbo",
) -> list[TranscriptionSegment]:
    return transcribe_video(video_path, language=language, model_name=model_name)
