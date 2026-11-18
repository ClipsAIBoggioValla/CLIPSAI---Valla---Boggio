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


def _score_normalizado(score_raw: int) -> int:
    """Score a escala 0-100 (multiplicado por 10 si venía 0-10)."""
    return max(0, min(100, score_raw * 10 if score_raw <= 10 else score_raw))


def _inicio_b(item: dict) -> str:
    """Timestamp de inicio del clip crudo."""
    return str(item.get("inicio") or "00:00:00")


def _fin_b(item: dict) -> str:
    """Timestamp de fin del clip crudo."""
    return str(item.get("fin") or "00:00:30")


def _headline_b(item: dict) -> str:
    """Headline del clip con fallbacks y tope de 120 chars."""
    return str(item.get("titulo_sugerido") or item.get("headline") or "Clip viral")[:120]


def _criterio_b(item: dict) -> str:
    """Criterio/emotional trigger del clip."""
    return str(item.get("criterio_principal") or "revelación")


def _motivo_b(item: dict) -> str:
    """Motivo viral del clip."""
    return str(item.get("motivo") or "Momento viral detectado")


def _hook_b(item: dict, headline: str) -> str:
    """Hook del clip; recorte del headline si no viene."""
    return str(item.get("hook_texto") or headline[:20])


def _campos_clip(item: dict) -> dict | None:
    """Campos normalizados del clip crudo. None si la ventana es inválida."""
    inicio = _inicio_b(item)
    fin = _fin_b(item)
    start = _ts_to_seconds(inicio)
    end = _ts_to_seconds(fin)
    if end <= start:
        return None
    headline = _headline_b(item)
    return {
        "start": start,
        "end": end,
        "score": _score_normalizado(int(item.get("score", 7))),
        "headline": headline,
        "criterio": _criterio_b(item),
        "motivo": _motivo_b(item),
        "hook": _hook_b(item, headline),
        "audio_score": int(item.get("audio_score", 7)),
    }


def _viral_report_de(item: dict, campos: dict) -> dict:
    """Reporte viral estándar para el candidato."""
    audio_score = campos["audio_score"]
    return {
        "hook_strength": int(min(100, audio_score * 10 if audio_score <= 10 else audio_score)),
        "emotional_trigger": campos["criterio"],
        "trend_alignment": int(min(100, campos["score"])),
        "clarity": int(85),
        "viral_reason": campos["motivo"],
        "suggested_hashtags": item.get("suggested_hashtags") or [f"#{campos['criterio']}", "#clipsai"],
        "call_to_action": campos["hook"],
    }


def _candidatos_de(raw: List[dict], max_candidates: int) -> List[ViralClipCandidate]:
    """Convierte los clips crudos del LLM en candidatos válidos."""
    cands: List[ViralClipCandidate] = []
    for item in raw[:max_candidates]:
        try:
            campos = _campos_clip(item)
            if campos is None:
                continue
            cands.append(
                ViralClipCandidate(
                    clip_id=str(uuid.uuid4()),
                    start_time=float(campos["start"]),
                    end_time=float(campos["end"]),
                    score=int(campos["score"]),
                    headline=campos["headline"],
                    viral_report=_viral_report_de(item, campos),
                )
            )
        except Exception:
            continue
    return cands


def _importar_obtener_clips_ia():
    """Importa perezosamente obtener_clips_ia de main.py ajustando sys.path."""
    try:
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from main import obtener_clips_ia  # type: ignore
    except Exception as e:
        raise RuntimeError(f"No se pudo importar obtener_clips_ia: {e}") from e
    return obtener_clips_ia


def _datos_audio_de(audio: AudioFeatures | None) -> List[dict]:
    """Eventos de audio del input; [] si no aplica."""
    return audio.events if audio and audio.events else []


def _datos_enriquecidos_de(audio: AudioFeatures | None) -> dict | None:
    """Momentos virales como datos enriquecidos; None si no aplica."""
    return {"eventos": audio.viral_moments} if audio and audio.viral_moments else None


def _raw_de_llm(transcript_text: str, datos_audio: List[dict], datos_enriquecidos: dict | None) -> List[dict]:
    """Clips crudos del LLM; traduce los fallos a RuntimeError."""
    obtener_clips_ia = _importar_obtener_clips_ia()

    try:
        return obtener_clips_ia(transcript_text, datos_audio, datos_enriquecidos)
    except Exception as e:
        raise RuntimeError(f"obtener_clips_ia falló: {e}") from e


class ViralityEngine(IViralityEngine):
    async def score(
        self, transcript: TranscriptData, audio: AudioFeatures, max_candidates: int = 10
    ) -> List[ViralClipCandidate]:
        transcript_text = _transcript_to_text(transcript)
        datos_audio = _datos_audio_de(audio)
        datos_enriquecidos = _datos_enriquecidos_de(audio)

        raw = _raw_de_llm(transcript_text, datos_audio, datos_enriquecidos)

        cands = _candidatos_de(raw, max_candidates)

        if not cands:
            raise RuntimeError("ViralityEngine: LLM no retornó candidatos válidos")
        return cands

    async def generate_report(self, candidate: ViralClipCandidate) -> dict:
        return candidate.viral_report
