from __future__ import annotations

from backend.core.interfaces import IAudioAnalyzer
from backend.core.schemas import AudioFeatures


class AudioAnalyzer(IAudioAnalyzer):
    """Stub Track A — wrapper sobre audio_analyzer.py existente. No bloquea Track B."""

    async def analyze(self, video_path: str, video_id: str) -> AudioFeatures:
        try:
            from audio_analyzer import analizar_audio  # legacy

            events = analizar_audio(video_path, "audio.json")  # type: ignore
        except Exception:
            events = []

        return AudioFeatures(video_id=video_id, duration_seconds=0.0, events=events or [], viral_moments=[])
