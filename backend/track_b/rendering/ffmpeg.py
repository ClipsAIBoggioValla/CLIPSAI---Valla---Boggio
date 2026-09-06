from __future__ import annotations

from backend.core.interfaces import IRenderer
from backend.core.schemas import RenderConfig, TranscriptData, ViralClipCandidate


class FFmpegRenderer(IRenderer):
    """Stub Track B — Kinetic Captions + Auto-Crop 9:16 + Brand Kit + loudnorm."""

    async def render(
        self,
        video_path: str,
        candidate: ViralClipCandidate,
        transcript: TranscriptData,
        config: RenderConfig,
        output_path: str,
    ) -> str:
        # TODO: ffmpeg -ss start -t duration -vf "crop=ih*9/16:ih, scale=1080:1920, subtitles=ass" -c:v libx264 -c:a aac -loudnorm
        # hook + captions karaoke_yellow / neon_green / minimal_white + watermark/outro
        return output_path
