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


def _campo_inicio(item: dict) -> str:
    """Timestamp de inicio del clip crudo de la IA."""
    return str(item.get("inicio") or item.get("start_time") or "00:00:00")


def _campo_fin(item: dict) -> str:
    """Timestamp de fin del clip crudo de la IA."""
    return str(item.get("fin") or item.get("end_time") or "00:00:30")


def _score_normalizado(score_raw: int) -> int:
    """Score a escala 0-100 (multiplicado por 10 si venía 0-10)."""
    return max(0, min(100, score_raw * 10 if score_raw <= 10 else score_raw))


def _headline_de(item: dict) -> str:
    """Headline del clip con fallbacks y tope de 120 chars."""
    return str(item.get("titulo_sugerido") or item.get("headline") or item.get("titulo") or "Clip viral")[:120]


def _criterio_de(item: dict) -> str:
    """Criterio/emotional trigger del clip con fallbacks."""
    return str(item.get("criterio_principal") or item.get("tipo_contenido") or "revelación")


def _motivo_de(item: dict) -> str:
    """Motivo viral del clip con fallbacks."""
    return str(item.get("motivo") or item.get("viral_reason") or "Momento con alto potencial viral detectado por IA")


def _hook_de(item: dict, headline: str) -> str:
    """Hook del clip; recorte del headline si no viene."""
    return str(item.get("hook_texto") or headline[:20])


def _campos_clip_ia(item: dict) -> dict | None:
    """Campos normalizados del clip crudo. None si la ventana es inválida."""
    inicio = _campo_inicio(item)
    fin = _campo_fin(item)
    start = _ts_to_seconds(inicio)
    end = _ts_to_seconds(fin)
    if end <= start:
        return None
    score = _score_normalizado(int(item.get("score", 7)))
    headline = _headline_de(item)
    criterio = _criterio_de(item)
    motivo = _motivo_de(item)
    hook = _hook_de(item, headline)
    audio_score = int(item.get("audio_score", 7))
    return {
        "start": start,
        "end": end,
        "score": score,
        "headline": headline,
        "criterio": criterio,
        "motivo": motivo,
        "hook": hook,
        "audio_score": audio_score,
    }


def _viral_report_de(item: dict, campos: dict) -> dict:
    """Reporte viral estándar para el candidato."""
    audio_score = campos["audio_score"]
    criterio = campos["criterio"]
    return {
        "hook_strength": int(min(100, max(0, audio_score * 10 if audio_score <= 10 else audio_score))),
        "emotional_trigger": criterio,
        "trend_alignment": int(min(100, campos["score"])),
        "clarity": int(min(100, 80 + (campos["score"] % 20))),
        "viral_reason": campos["motivo"],
        "suggested_hashtags": item.get("suggested_hashtags") or [f"#{criterio}", "#clipsai", "#viral"],
        "call_to_action": item.get("call_to_action") or campos["hook"],
    }


def _map_llm_to_candidates(raw_clips: List[dict]) -> List[ViralClipCandidate]:
    cands: List[ViralClipCandidate] = []
    for item in raw_clips:
        try:
            campos = _campos_clip_ia(item)
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


def _ruta_transcript_mock() -> Path | None:
    """Primera ruta existente del fixture de transcript mock."""
    fixture = Path("tests/fixtures/mock_transcript.json")
    alt2 = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "mock_transcript.json"
    for p in (fixture, alt2):
        if p.exists():
            return p
    return None


def _cargar_transcript_mock() -> TranscriptData | None:
    """TranscriptData desde el fixture mock; None si no existe."""
    src = _ruta_transcript_mock()
    if src and src.exists():
        data = json.loads(src.read_text(encoding="utf-8"))
        return TranscriptData.model_validate(data)
    return None


def _candidatos_mock(transcript: TranscriptData) -> List[ViralClipCandidate]:
    """Candidatos mock, reemplazando el transcript por el fixture si existe."""
    nuevo = _cargar_transcript_mock()
    if nuevo is not None:
        transcript = nuevo
    return _mock_candidates_from_transcript(transcript)


def _importar_obtener_clips_ia():
    """Importa perezosamente obtener_clips_ia de main.py ajustando sys.path."""
    try:
        import sys
        from pathlib import Path as _P

        root = _P(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from main import obtener_clips_ia  # type: ignore
    except Exception as e:
        raise RuntimeError(f"No se pudo importar obtener_clips_ia desde main.py: {e}") from e
    return obtener_clips_ia


def _clips_de_llm(transcript_text: str) -> List[dict]:
    """Clips crudos del LLM a partir del texto de transcripción."""
    obtener_clips_ia = _importar_obtener_clips_ia()

    datos_audio: List[dict] = []
    try:
        return obtener_clips_ia(transcript_text, datos_audio, None)
    except Exception as e:
        raise RuntimeError(f"obtener_clips_ia falló: {e}") from e


async def analyze_transcript(
    transcript: TranscriptData, use_mock: bool = False
) -> List[ViralClipCandidate]:
    if use_mock:
        return _candidatos_mock(transcript)

    raw = _clips_de_llm(_transcript_to_text(transcript))

    candidates = _map_llm_to_candidates(raw)
    if not candidates:
        raise RuntimeError("LLM no retornó candidatos válidos")
    return candidates
