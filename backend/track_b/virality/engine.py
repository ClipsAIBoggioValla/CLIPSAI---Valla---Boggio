from __future__ import annotations

import uuid
from typing import List

from backend.core.interfaces import IViralityEngine
from backend.core.schemas import AudioFeatures, TranscriptData, ViralClipCandidate


class ViralityEngine(IViralityEngine):
    """Stub Track B — reutiliza main.py construir_prompt + obtener_clips_ia sin bloquear Track A."""

    async def score(
        self, transcript: TranscriptData, audio: AudioFeatures, max_candidates: int = 10
    ) -> List[ViralClipCandidate]:
        return [
            ViralClipCandidate(
                clip_id=str(uuid.uuid4()),
                start_time=10.0,
                end_time=55.0,
                score=88,
                headline="Hook revelación — stub",
                viral_report={
                    "hook_strength": 90,
                    "emotional_trigger": "revelación",
                    "trend_alignment": 70,
                    "clarity": 85,
                    "viral_reason": "Dato exclusivo + pico de energía audio",
                    "suggested_hashtags": ["#viral", "#clipsai"],
                    "call_to_action": "Mira hasta el final",
                },
            )
        ][:max_candidates]

    async def generate_report(self, candidate: ViralClipCandidate) -> dict:
        return candidate.viral_report
