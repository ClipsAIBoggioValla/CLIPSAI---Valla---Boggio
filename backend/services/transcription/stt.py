from __future__ import annotations

from backend.core.schemas import TranscriptData, WordToken


async def transcribe_stub(video_path: str, video_id: str, language: str = "es") -> TranscriptData:
    from backend.track_a.transcription.stt import WhisperTranscriber

    svc = WhisperTranscriber()
    tr = await svc.transcribe(video_path, language)
    tr.video_id = video_id
    return tr
