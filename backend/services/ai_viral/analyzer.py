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


def _transcript_to_text(transcript: TranscriptData) -> str:
    lines: List[str] = []
    for w in transcript.words:
        h = int(w.start // 3600)
        m = int((w.start % 3600) // 60)
        s = int(w.start % 60)
        lines.append(f"{h:02d}:{m:02d}:{s:02d} - {w.word}")
    if transcript.raw_text:
        lines.append(f"__raw__ {transcript.raw_text[:500]}")
    return "\n".join(lines)


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


def _map_llm_to_candidates(raw_clips: List[dict]) -> List[ViralClipCandidate]:
    cands: List[ViralClipCandidate] = []
    for item in raw_clips:
        try:
            inicio = str(item.get("inicio") or item.get("start_time") or "00:00:00")
            fin = str(item.get("fin") or item.get("end_time") or "00:00:30")
            start = _ts_to_seconds(inicio)
            end = _ts_to_seconds(fin)
            if end <= start:
                continue
            score_raw = int(item.get("score", 7))
            score = max(0, min(100, score_raw * 10 if score_raw <= 10 else score_raw))
            headline = str(item.get("titulo_sugerido") or item.get("headline") or item.get("titulo") or "Clip viral")[:120]
            criterio = str(item.get("criterio_principal") or item.get("tipo_contenido") or "revelación")
            motivo = str(item.get("motivo") or item.get("viral_reason") or "Momento con alto potencial viral detectado por IA")
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
                        "hook_strength": int(min(100, max(0, audio_score * 10 if audio_score <= 10 else audio_score))),
                        "emotional_trigger": criterio,
                        "trend_alignment": int(min(100, score)),
                        "clarity": int(min(100, 80 + (score % 20))),
                        "viral_reason": motivo,
                        "suggested_hashtags": item.get("suggested_hashtags") or [f"#{criterio}", "#clipsai", "#viral"],
                        "call_to_action": item.get("call_to_action") or hook,
                    },
                )
            )
        except Exception:
            continue
    return cands


async def analyze_transcript(
    transcript: TranscriptData, use_mock: bool = False
) -> List[ViralClipCandidate]:
    if use_mock:
        fixture = Path("tests/fixtures/mock_transcript.json")
        alt = Path("backend/tests/fixtures/mock_transcript.json")
        alt2 = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "mock_transcript.json"
        src = None
        for p in (fixture, alt, alt2):
            if p.exists():
                src = p
                break
        if src and src.exists():
            data = json.loads(src.read_text(encoding="utf-8"))
            transcript = TranscriptData.model_validate(data)
        return _mock_candidates_from_transcript(transcript)

    try:
        import sys
        from pathlib import Path as _P

        root = _P(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from main import obtener_clips_ia  # type: ignore
    except Exception as e:
        raise RuntimeError(f"No se pudo importar obtener_clips_ia desde main.py: {e}") from e

    transcript_text = _transcript_to_text(transcript)
    datos_audio: List[dict] = []
    try:
        raw = obtener_clips_ia(transcript_text, datos_audio, None)
    except Exception as e:
        raise RuntimeError(f"obtener_clips_ia falló: {e}") from e

    candidates = _map_llm_to_candidates(raw)
    if not candidates:
        raise RuntimeError("LLM no retornó candidatos válidos")
    return candidates
