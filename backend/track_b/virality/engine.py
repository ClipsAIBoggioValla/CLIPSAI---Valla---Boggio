from __future__ import annotations

import uuid
from typing import List

from backend.core.interfaces import IViralityEngine
from backend.core.schemas import AudioFeatures, TranscriptData, ViralClipCandidate


def _ts_to_seconds(ts: str) -> float:
    try:
        parts = ts.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(ts)
    except Exception:
        return 0.0


def _transcript_to_text(transcript: TranscriptData) -> str:
    lines: List[str] = []
    for w in transcript.words:
        h = int(w.start // 3600)
        m = int((w.start % 3600) // 60)
        s = int(w.start % 60)
        lines.append(f"{h:02d}:{m:02d}:{s:02d} - {w.word}")
    if transcript.raw_text:
        lines.append(transcript.raw_text[:800])
    return "\n".join(lines)


class ViralityEngine(IViralityEngine):
    async def score(
        self, transcript: TranscriptData, audio: AudioFeatures, max_candidates: int = 10
    ) -> List[ViralClipCandidate]:
        try:
            import sys
            from pathlib import Path

            root = Path(__file__).resolve().parents[3]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from main import obtener_clips_ia  # type: ignore
        except Exception as e:
            raise RuntimeError(f"No se pudo importar obtener_clips_ia: {e}") from e

        transcript_text = _transcript_to_text(transcript)
        datos_audio = audio.events if audio and audio.events else []
        datos_enriquecidos = {"eventos": audio.viral_moments} if audio and audio.viral_moments else None

        try:
            raw = obtener_clips_ia(transcript_text, datos_audio, datos_enriquecidos)
        except Exception as e:
            raise RuntimeError(f"obtener_clips_ia falló: {e}") from e

        cands: List[ViralClipCandidate] = []
        for item in raw[:max_candidates]:
            try:
                inicio = str(item.get("inicio") or "00:00:00")
                fin = str(item.get("fin") or "00:00:30")
                start = _ts_to_seconds(inicio)
                end = _ts_to_seconds(fin)
                if end <= start:
                    continue
                score_raw = int(item.get("score", 7))
                score = max(0, min(100, score_raw * 10 if score_raw <= 10 else score_raw))
                headline = str(item.get("titulo_sugerido") or item.get("headline") or "Clip viral")[:120]
                criterio = str(item.get("criterio_principal") or "revelación")
                motivo = str(item.get("motivo") or "Momento viral detectado")
                hook = str(item.get("hook_texto") or headline[:20])
                audio_score = int(item.get("audio_score", 7))
                cands.append(
                    ViralClipCandidate(
                        clip_id=str(uuid.uuid4()),
                        start_time=float(start),
                        end_time=float(end),
                        score=int(score),
                        headline=headline,
                        viral_report={
                            "hook_strength": int(min(100, audio_score * 10 if audio_score <= 10 else audio_score)),
                            "emotional_trigger": criterio,
                            "trend_alignment": int(min(100, score)),
                            "clarity": int(85),
                            "viral_reason": motivo,
                            "suggested_hashtags": item.get("suggested_hashtags") or [f"#{criterio}", "#clipsai"],
                            "call_to_action": hook,
                        },
                    )
                )
            except Exception:
                continue

        if not cands:
            raise RuntimeError("ViralityEngine: LLM no retornó candidatos válidos")
        return cands

    async def generate_report(self, candidate: ViralClipCandidate) -> dict:
        return candidate.viral_report
