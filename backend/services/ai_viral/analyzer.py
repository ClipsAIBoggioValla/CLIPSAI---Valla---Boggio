from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import List

from backend.core.schemas import TranscriptData, ViralClipCandidate, WordToken


def _words_to_text(words: List[WordToken], limit: int = 60) -> str:
    return " ".join(w.word for w in words[:limit])


def _mock_candidates_from_transcript(transcript: TranscriptData) -> List[ViralClipCandidate]:
    n = len(transcript.words)
    if n < 10:
        return []
    cands: List[ViralClipCandidate] = []
    segments = [
        (0, min(30, n - 1), "Hook revelación — el dato que nadie contó", 92, "revelación"),
        (max(0, n // 3), min(n - 1, n // 3 + 35), "Controversia en vivo — la frase que encendió el debate", 88, "controversia"),
        (max(0, n // 2), min(n - 1, n // 2 + 28), "Momento emocional — se quiebra al recordarlo", 85, "emocional"),
    ]
    for idx, (s_idx, e_idx, headline, score, trigger) in enumerate(segments):
        if e_idx <= s_idx:
            continue
        s_word = transcript.words[s_idx]
        e_word = transcript.words[e_idx]
        cands.append(
            ViralClipCandidate(
                clip_id=f"mock-{idx+1}-{uuid.uuid4().hex[:6]}",
                start_time=float(s_word.start),
                end_time=float(e_word.end),
                score=int(score),
                headline=headline,
                viral_report={
                    "hook_strength": int(score),
                    "emotional_trigger": trigger,
                    "trend_alignment": 70 + idx * 2,
                    "clarity": 85,
                    "viral_reason": f"Mock candidato {idx+1} basado en {trigger} con texto '{_words_to_text(transcript.words[s_idx:e_idx+2])[:80]}...'",
                    "suggested_hashtags": ["#viral", "#clipsai", f"#{trigger}"],
                    "call_to_action": "Mira hasta el final y comentá qué opinás",
                },
            )
        )
    return cands


async def analyze_transcript(
    transcript: TranscriptData, use_mock: bool = False
) -> List[ViralClipCandidate]:
    if use_mock:
        fixture = Path("tests/fixtures/mock_transcript.json")
        alt = Path("backend/tests/fixtures/mock_transcript.json")
        src = fixture if fixture.exists() else alt
        if src.exists():
            data = json.loads(src.read_text(encoding="utf-8"))
            transcript = TranscriptData.model_validate(data)
        return _mock_candidates_from_transcript(transcript)

    try:
        from backend.track_b.virality.engine import ViralityEngine

        engine = ViralityEngine()
        from backend.core.schemas import AudioFeatures

        audio = AudioFeatures(video_id=transcript.video_id, duration_seconds=0, events=[], viral_moments=[])
        return await engine.score(transcript, audio, max_candidates=10)
    except Exception as e:
        raise RuntimeError(f"LLM virality failed: {e}") from e
