from __future__ import annotations

from backend.core.interfaces import ITranscriber
from backend.core.schemas import TranscriptData, WordToken


class WhisperTranscriber(ITranscriber):
    """Stub Track A — wrapper sobre whisper_transcriber.py / faster-whisper."""

    async def transcribe(self, video_path: str, language: str = "es") -> TranscriptData:
        try:
            from whisper_transcriber import transcribir_video  # legacy

            words_raw = await transcribir_video(video_path)  # type: ignore
            words = [WordToken(**w) for w in (words_raw or [])]
        except Exception:
            words = [WordToken(word="hola", start=0.0, end=0.5)]

        return TranscriptData(video_id="stub", language=language, words=words)
