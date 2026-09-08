from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class TranscriptionSegment(TypedDict):
    start: float
    end: float
    text: str


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


def extract_audio_wav(video_path: str, wav_path: str | None = None) -> str:
    src = Path(video_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video no encontrado: {video_path}")
    _check_ffmpeg()
    if wav_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        wav_path = tmp.name
    out = Path(wav_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(out),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
    except FileNotFoundError as exc:
        raise RuntimeError(f"FFmpeg no instalado: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        err = exc.stderr.decode(errors="ignore")[:1200] if exc.stderr else str(exc)
        raise RuntimeError(f"Extraccion de audio fallida: {err}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timeout 120s extrayendo audio") from exc
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
        model = WhisperModel(resolved_model, device=device, compute_type=compute_type)
    except Exception as exc:
        raise RuntimeError(f"No se pudo cargar modelo Whisper '{resolved_model}' ({device}/{compute_type}): {exc}") from exc
    try:
        segments_gen, _info = model.transcribe(
            str(wav),
            language=lang,
            word_timestamps=False,
            vad_filter=cfg.vad_filter,
            beam_size=cfg.beam_size,
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
            segments.append(TranscriptionSegment(start=start, end=end, text=text))
        return segments
    except Exception as exc:
        raise RuntimeError(f"Transcripcion fallida: {exc}") from exc


def transcribe_video(
    video_path: str,
    language: str = "es",
    model_name: str = "large-v3-turbo",
    keep_wav: bool = False,
) -> list[TranscriptionSegment]:
    wav_path: str | None = None
    try:
        wav_path = extract_audio_wav(video_path)
        segments = transcribe_wav(wav_path, language=language, model_name=model_name)
        return segments
    finally:
        if wav_path and not keep_wav:
            try:
                Path(wav_path).unlink(missing_ok=True)
            except Exception:
                pass


def transcribe_video_to_segments(
    video_path: str,
    language: str = "es",
    model_name: str = "large-v3-turbo",
) -> list[TranscriptionSegment]:
    return transcribe_video(video_path, language=language, model_name=model_name)
