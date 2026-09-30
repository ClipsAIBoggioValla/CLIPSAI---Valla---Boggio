"""Servicio nativo Claude (Anthropic) — selección semántica obligatoria de clips.

Este módulo vive 100% dentro de backend_fastapi (sin depender del monorepo externo)
y es usado tanto en Docker (/app) como en local. No tiene fallback heurístico:
si ANTHROPIC_API_KEY falta o la API falla, lanza RuntimeError con mensaje
"Error en API de Claude: ..." para que el job quede FAILED explícitamente.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
from json_repair import repair_json
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Carga .env segura (sin parents fijo)
_cur = Path(__file__).resolve()
for _idx in (3, 2, 1, 0):
    if _idx < len(_cur.parents):
        try:
            load_dotenv(dotenv_path=_cur.parents[_idx] / ".env", override=False)
        except Exception:
            pass

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022").strip() or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514").strip()
# Compat: si .env trae claude-sonnet-4, usarlo; si no, default haiku/sonnet
if not ANTHROPIC_MODEL:
    ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
ANTHROPIC_VERSION = os.getenv("ANTHROPIC_VERSION", "2023-06-01").strip()
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"

TIMEOUT = 60.0
MAX_RETRIES = 2


def _get_key() -> str:
    # Releer por si .env cambió o Settings lo actualizó
    key = os.getenv("ANTHROPIC_API_KEY", "").strip() or ANTHROPIC_API_KEY.strip()
    # También intentar via Settings si está disponible
    if not key:
        try:
            from ..config import get_settings

            s = get_settings()
            key = (getattr(s, "anthropic_api_key", "") or "").strip()
        except Exception:
            pass
    return key


def _has_strong_punctuation(word_text: str) -> bool:
    cleaned = word_text.rstrip("\"'’”»)]}")
    return cleaned.endswith((".", "?", "!"))


def build_sentence_map(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa timestamps de palabra contiguos en oraciones identificadas S_1, S_2..."""
    words: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        raw_words = segment.get("words")
        if not isinstance(raw_words, list):
            continue
        for raw_word in raw_words:
            if not isinstance(raw_word, dict):
                continue
            try:
                start = float(raw_word["start"])
                end = float(raw_word["end"])
                text = str(raw_word.get("text", raw_word.get("word", ""))).strip()
                if text and start >= 0 and end >= start:
                    words.append({"start": start, "end": end, "text": text})
            except (KeyError, TypeError, ValueError):
                continue

    if not words:
        raise RuntimeError(
            "No hay timestamps a nivel de palabra de Whisper; no se pueden resolver cortes precisos"
        )
    words.sort(key=lambda word: (word["start"], word["end"]))

    sentence_map: list[dict[str, Any]] = []
    current_words: list[dict[str, Any]] = []
    for word in words:
        current_words.append(word)
        if _has_strong_punctuation(word["text"]):
            sentence_map.append(
                {
                    "id": f"S_{len(sentence_map) + 1}",
                    "start": current_words[0]["start"],
                    "end": current_words[-1]["end"],
                    "text": " ".join(item["text"] for item in current_words),
                    "words": current_words,
                }
            )
            current_words = []

    if current_words:
        sentence_map.append(
            {
                "id": f"S_{len(sentence_map) + 1}",
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
                "text": " ".join(item["text"] for item in current_words),
                "words": current_words,
            }
        )
    return sentence_map


def _format_sentence_map(sentence_map: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for sentence in sentence_map:
        word_items = sentence.get("words", [])
        formatted_words = " ".join(
            f"[{float(word['start']):.3f}-{float(word['end']):.3f}] {word['text']}"
            for word in word_items
        )
        lines.append(
            f"[{sentence['id']}] sentence={float(sentence['start']):.3f}-"
            f"{float(sentence['end']):.3f}s | words: {formatted_words}"
        )
    return "\n".join(lines)


def _format_transcript(segments: list[dict[str, Any]]) -> str:
    """Compatibilidad interna: formatea segmentos como mapa de oraciones+palabras."""
    return _format_sentence_map(build_sentence_map(segments))


def _build_output_schema(sentence_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["clips"],
        "properties": {
            "clips": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "start_sentence_id",
                        "end_sentence_id",
                        "score",
                        "title",
                        "hook_candidates",
                        "has_hook",
                    ],
                    "properties": {
                        "start_sentence_id": {"type": "string", "enum": sentence_ids},
                        "end_sentence_id": {"type": "string", "enum": sentence_ids},
                        "score": {"type": "number", "minimum": 1, "maximum": 10},
                        "title": {"type": "string", "maxLength": 60},
                        "hook_candidates": {
                            "type": "array",
                            "maxItems": 5,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "start_sentence_id",
                                    "end_sentence_id",
                                    "curiosity_score",
                                    "makes_sense_standalone",
                                ],
                                "properties": {
                                    "start_sentence_id": {"type": "string", "enum": sentence_ids},
                                    "end_sentence_id": {"type": "string", "enum": sentence_ids},
                                    "curiosity_score": {"type": "integer", "minimum": 1, "maximum": 10},
                                    "makes_sense_standalone": {"type": "boolean"},
                                },
                            },
                        },
                        "has_hook": {"type": "boolean"},
                    },
                },
            }
        },
    }


def _build_export_viral_clips_tool(sentence_ids: list[str]) -> dict[str, Any]:
    return {
        "name": "export_viral_clips",
        "description": "Devuelve clips y candidatos de teaser estructurados por IDs de oración.",
        "input_schema": _build_output_schema(sentence_ids),
    }


def _build_claude_prompt(
    transcript_text: str,
    sentence_ids: list[str],
    duration_hint: float | None = None,
) -> str:
    dur_info = f"Duracion total video: {duration_hint:.1f}s" if duration_hint else "Duracion total: desconocida"
    schema_text = json.dumps(_build_output_schema(sentence_ids), ensure_ascii=False, indent=2)
    return f"""Eres un editor viral experto en TikTok/Reels/Shorts en español rioplatense. Analizas transcripciones con timestamps y seleccionas clips con alto potencial viral.

{dur_info}

TRANSCRIPCION CON IDS DE ORACION Y TIMESTAMPS DE CADA PALABRA:
{transcript_text}

TAREA: Selecciona 1 a 3 clips de 15-60s que contengan ideas completas y con mayor virabilidad. Para cada clip devuelve JSON estricto con:
- start_sentence_id: ID de la primera oración completa del clip
- end_sentence_id: ID de la última oración completa del clip
- score: puntuación virabilidad 1-10 (float, 1=bajo, 10=máximo)
- title: título del clip (max 60 chars, rioplatense, concreto)
- hook_candidates: array de hasta 5 oraciones completas que puedan funcionar como teaser hook; pueden aparecer antes, dentro o después del cuerpo del clip
- has_hook: true solo si existe al menos un candidato con curiosity_score >= 8 y makes_sense_standalone=true; de lo contrario false
- Prioriza hook_candidates completos que duren entre 2.5 y 5.5 segundos según los timestamps de palabra

CRITERIOS VIRALIDAD (ordena por potencial): revelacion 10, controversia 9, dato impactante 8, emocional 7, tactico 6, prediccion 5. Valora energía, dato con números, remate potente.

REGLAS ESTRICTAS:
- Devuelve exclusivamente IDs existentes de la lista permitida: {", ".join(sentence_ids)}
- No devuelvas ni estimes timestamps flotantes; los límites de tiempo se resolverán desde las palabras de Whisper
- Selecciona límites de oración completos; mantén juntas las palabras consecutivas de cada oración
- Cada hook_candidate debe tener start_sentence_id, end_sentence_id, curiosity_score (entero 1-10) y makes_sense_standalone (booleano)
- Prohibido iniciar hook_candidates con conectores o muletillas: "Y...", "Bueno...", "Entonces...", "Porque...", "O sea...", "Eh...", "Este..."
- Un hook válido es una oración completa con sujeto, verbo y predicado, o una pregunta directa con autonomía semántica propia
- Evalúa curiosidad y autonomía independientemente; si ningún candidato alcanza curiosity_score >= 8 y autonomía true, has_hook debe ser false
- Si has_hook=false, no marques ningún candidato como seleccionado; puedes devolver hook_candidates vacío
- score 1-10, prioriza 8-10 para clips con gancho potente
- Devuelve SOLO JSON válido sin markdown

JSON SCHEMA OBLIGATORIO (no añadir propiedades ni timestamps):
{schema_text}

VALIDACION:
- Si no hay momentos virales, devuelve {{"clips": []}}
- Max 3 clips, ordenados por score descendente
"""


def _call_anthropic(prompt: str, sentence_ids: list[str]) -> str:
    key = _get_key()
    if not key:
        logger.error("Error en API de Claude: ANTHROPIC_API_KEY no configurada (revisar .env y docker-compose.yml ANTHROPIC_API_KEY)")
        raise RuntimeError("Error en API de Claude: ANTHROPIC_API_KEY no configurada (revisar .env y docker-compose.yml ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY})")
    tool = _build_export_viral_clips_tool(sentence_ids)
    tool_choice = {"type": "tool", "name": "export_viral_clips"}
    # Intentar SDK anthropic si está instalado — con timeout explícito 60-90s
    try:
        import anthropic  # type: ignore

        client = anthropic.Anthropic(api_key=key, timeout=TIMEOUT)
        # Usar modelo configurado (sonnet o haiku)
        model = ANTHROPIC_MODEL or "claude-3-5-sonnet-20241022"
        # anthropic SDK usa max_tokens y messages — envuelto en try/except con timeout
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                tools=[tool],
                tool_choice=tool_choice,
            )
        except Exception as sdk_e:
            err_msg = str(sdk_e)
            # Detectar timeout / API key / rate limit
            if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
                logger.error(f"Error en API de Claude: timeout {TIMEOUT}s — {err_msg}")
                raise RuntimeError(f"Error en Claude: timeout {TIMEOUT}s — {err_msg}") from sdk_e
            raise
        # Extraer texto
        txt = ""
        try:
            for blk in getattr(msg, "content", []):
                if (
                    getattr(blk, "type", "") == "tool_use"
                    and getattr(blk, "name", "") == "export_viral_clips"
                ):
                    tool_input = getattr(blk, "input", None)
                    if isinstance(tool_input, dict):
                        logger.info("Claude devolvió resultado mediante export_viral_clips (SDK)")
                        return json.dumps(tool_input, ensure_ascii=False)
                if getattr(blk, "type", "") == "text":
                    txt += getattr(blk, "text", "")
        except Exception:
            txt = str(msg)
        if not txt:
            raise RuntimeError("Error en API de Claude: no se recibió tool_use de export_viral_clips")
        raise RuntimeError("Error en API de Claude: Claude devolvió texto libre en vez de export_viral_clips")
    except ImportError:
        pass
    except Exception as e:
        # Captura explícita de APIConnectionError y APITimeoutError (spec: timeout 60.0, max_retries 2)
        err_type = type(e).__name__
        err_msg = str(e)
        if err_type in ("APIConnectionError", "APITimeoutError") or "APIConnectionError" in err_type or "APITimeoutError" in err_type or "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
            logger.error(f"Error en API de Claude: {err_type} timeout {TIMEOUT}s — {err_msg}")
            raise RuntimeError(f"Error en Claude: {err_type} timeout {TIMEOUT}s — {err_msg}") from e
        # Si SDK falla con 401/cuota, propagar como Error en la API de Claude
        if "401" in err_msg or "authentication" in err_msg.lower() or "invalid" in err_msg.lower():
            raise RuntimeError(f"Error en API de Claude: {err_msg}") from e
        if "quota" in err_msg.lower() or "rate" in err_msg.lower() or "429" in err_msg:
            raise RuntimeError(f"Error en API de Claude: {err_msg}") from e
        # Para otros errores, intentar fallback a requests
        logger.warning("Claude SDK fallo (%s), intentando requests", e)

    # Fallback requests directo
    headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    body: dict[str, Any] = {
        "model": ANTHROPIC_MODEL or "claude-3-5-sonnet-20241022",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [tool],
        "tool_choice": tool_choice,
    }
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(ANTHROPIC_ENDPOINT, headers=headers, json=body, timeout=TIMEOUT)
            if resp.status_code == 429 and attempt < MAX_RETRIES:
                retry_after = int(resp.headers.get("Retry-After", 2 * attempt))
                time.sleep(retry_after)
                continue
            if resp.status_code != 200:
                raise RuntimeError(f"Error en API de Claude: {resp.status_code} {resp.text[:800]}")
            data = resp.json()
            txt = ""
            for blk in data.get("content", []):
                if blk.get("type") == "tool_use" and blk.get("name") == "export_viral_clips":
                    tool_input = blk.get("input")
                    if isinstance(tool_input, dict):
                        logger.info("Claude devolvió resultado mediante export_viral_clips (requests)")
                        return json.dumps(tool_input, ensure_ascii=False)
                if blk.get("type") == "text" and blk.get("text"):
                    txt += blk["text"]
            if txt:
                raise RuntimeError("Error en API de Claude: Claude devolvió texto libre en vez de export_viral_clips")
            raise RuntimeError("Error en API de Claude: no se recibió tool_use de export_viral_clips")
        except requests.exceptions.Timeout as exc:
            last_err = exc
            logger.error(f"Error en API de Claude: timeout {TIMEOUT}s (intento {attempt}/{MAX_RETRIES}) — {exc}")
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Error en Claude: timeout {TIMEOUT}s tras {MAX_RETRIES} intentos — {exc}") from exc
        except requests.exceptions.RequestException as exc:
            last_err = exc
            logger.error(f"Error en API de Claude: conexion fallo (intento {attempt}/{MAX_RETRIES}) — {exc}")
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Error en Claude: conexion fallo {exc}") from exc
        except RuntimeError as exc:
            # Ya viene con prefijo "Error en API de Claude"
            logger.error(f"Error en API de Claude: {exc}")
            raise
        time.sleep(2 * attempt)
    logger.error(f"Error en API de Claude: fallo tras reintentos {last_err}")
    raise RuntimeError(f"Error en Claude: fallo tras reintentos {last_err}")


def _parse_and_validate(raw: str) -> list[dict[str, Any]]:
    try:
        repaired_string = repair_json(raw, return_objects=False)
        data = json.loads(repaired_string)
    except Exception as exc:
        raise RuntimeError(
            f"Error en API de Claude: JSON inválido incluso tras json-repair: {exc} — raw: {raw[:800]}"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Error en API de Claude: la respuesta reparada debe ser un objeto JSON, got {type(data)}"
        )
    clips_raw = data.get("clips", [])
    if isinstance(clips_raw, str):
        try:
            repaired_clips = repair_json(clips_raw, return_objects=False)
            clips_raw = json.loads(repaired_clips)
        except Exception as exc:
            raise RuntimeError(
                f"Error en API de Claude: 'clips' llegó como string y no se pudo reparar como array: {exc}"
            ) from exc
    if not isinstance(clips_raw, list):
        raise RuntimeError(
            f"Error en API de Claude: JSON 'clips' debe ser una lista tras el reparseo, got {type(clips_raw)}"
        )
    validated: list[dict[str, Any]] = []
    for c in clips_raw:
        try:
            if any(key in c for key in ("start", "end", "start_time", "end_time")):
                continue
            start_sentence_id = str(c.get("start_sentence_id", "")).strip()
            end_sentence_id = str(c.get("end_sentence_id", "")).strip()
            score = float(c.get("score", c.get("viral_score", 0)))
            title = str(c.get("title", "")).strip()[:60]
            raw_hook_candidates = c.get("hook_candidates", [])
            raw_has_hook = c.get("has_hook")
            if (
                not re.fullmatch(r"S_\d+", start_sentence_id)
                or not re.fullmatch(r"S_\d+", end_sentence_id)
                or not title
                or not isinstance(raw_hook_candidates, list)
                or not isinstance(raw_has_hook, bool)
            ):
                continue
            if not (1 <= score <= 10):
                # Normalizar si vino 0-100
                if 10 < score <= 100:
                    score = score / 10
                else:
                    continue
            hook_candidates: list[dict[str, Any]] = []
            for candidate in raw_hook_candidates[:5]:
                if not isinstance(candidate, dict):
                    continue
                hook_start_id = str(candidate.get("start_sentence_id", "")).strip()
                hook_end_id = str(candidate.get("end_sentence_id", "")).strip()
                standalone = candidate.get("makes_sense_standalone")
                try:
                    curiosity_score = int(candidate.get("curiosity_score", 0))
                except (TypeError, ValueError):
                    continue
                if (
                    re.fullmatch(r"S_\d+", hook_start_id)
                    and re.fullmatch(r"S_\d+", hook_end_id)
                    and 1 <= curiosity_score <= 10
                    and isinstance(standalone, bool)
                ):
                    hook_candidates.append(
                        {
                            "start_sentence_id": hook_start_id,
                            "end_sentence_id": hook_end_id,
                            "curiosity_score": curiosity_score,
                            "makes_sense_standalone": standalone,
                        }
                    )
            has_hook = raw_has_hook and any(
                candidate["curiosity_score"] >= 8 and candidate["makes_sense_standalone"]
                for candidate in hook_candidates
            )
            validated.append(
                {
                    "start_sentence_id": start_sentence_id,
                    "end_sentence_id": end_sentence_id,
                    "score": score,
                    "title": title,
                    "hook_candidates": hook_candidates,
                    "has_hook": has_hook,
                }
            )
        except Exception:
            continue
    # Ordenar por score descendente, max 3
    validated.sort(key=lambda x: x["score"], reverse=True)
    return validated[:3]


def select_clips_via_claude(
    segments: list[dict[str, Any]],
    duration_hint: float | None = None,
    sentence_map: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Función principal: recibe transcripción con timestamps y devuelve clips vía Claude.

    Lanza RuntimeError con prefijo "Error en API de Claude: ..." si falta key o falla la API.
    No hace fallback heurístico.
    """
    if not segments:
        raise RuntimeError("Error en API de Claude: no hay segmentos de transcripción para analizar")
    key = _get_key()
    if not key:
        raise RuntimeError("Error en API de Claude: ANTHROPIC_API_KEY no configurada")
    if sentence_map is None:
        sentence_map = build_sentence_map(segments)
    transcript_text = _format_sentence_map(sentence_map)
    if not transcript_text.strip():
        raise RuntimeError("Error en API de Claude: transcripción vacía")
    sentence_ids = [str(sentence["id"]) for sentence in sentence_map]
    prompt = _build_claude_prompt(transcript_text, sentence_ids, duration_hint)
    raw = _call_anthropic(prompt, sentence_ids)
    clips = _parse_and_validate(raw)
    sentence_positions = {sentence_id: index for index, sentence_id in enumerate(sentence_ids)}
    valid_clips: list[dict[str, Any]] = []
    for clip in clips:
        start_id = clip["start_sentence_id"]
        end_id = clip["end_sentence_id"]
        if (
            start_id not in sentence_positions
            or end_id not in sentence_positions
            or sentence_positions[start_id] > sentence_positions[end_id]
        ):
            continue

        valid_candidates: list[dict[str, Any]] = []
        for candidate in clip["hook_candidates"]:
            if not isinstance(candidate, dict):
                continue
            hook_start_id = str(candidate.get("start_sentence_id", ""))
            hook_end_id = str(candidate.get("end_sentence_id", ""))
            try:
                curiosity_score = int(candidate.get("curiosity_score", 0))
            except (TypeError, ValueError):
                continue
            standalone = candidate.get("makes_sense_standalone")
            if (
                hook_start_id in sentence_positions
                and hook_end_id in sentence_positions
                and sentence_positions[hook_start_id] <= sentence_positions[hook_end_id]
                and 1 <= curiosity_score <= 10
                and isinstance(standalone, bool)
            ):
                valid_candidates.append(
                    {
                        "start_sentence_id": hook_start_id,
                        "end_sentence_id": hook_end_id,
                        "curiosity_score": curiosity_score,
                        "makes_sense_standalone": standalone,
                    }
                )
        clip["hook_candidates"] = valid_candidates
        clip["has_hook"] = bool(clip["has_hook"]) and any(
            candidate["curiosity_score"] >= 8 and candidate["makes_sense_standalone"]
            for candidate in valid_candidates
        )
        valid_clips.append(clip)
    clips = valid_clips
    if not clips:
        raise RuntimeError(f"Error en API de Claude: validación dejó 0 clips — raw: {raw[:500]}")
    return clips
