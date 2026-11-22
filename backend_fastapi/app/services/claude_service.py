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
ANTHROPIC_WORKSPACE_ID = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
# Modelo primario: CLAUDE_MODEL (nuevo) con fallback a ANTHROPIC_MODEL (legacy) y default seguro.
CLAUDE_MODEL = (
    os.getenv("CLAUDE_MODEL", "").strip()
    or os.getenv("ANTHROPIC_MODEL", "").strip()
    or "claude-sonnet-5-5"
)
CLAUDE_FALLBACK_MODEL = os.getenv("ANTHROPIC_FALLBACK_MODEL", "claude-haiku-5-5")
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


def _palabra_si_en_rango(start: float, end: float, text: str) -> dict[str, Any] | None:
    """Palabra si el texto no está vacío y el rango es válido; None si no."""
    if not (text and start >= 0 and end >= start):
        return None
    return {"start": start, "end": end, "text": text}


def _palabra_valida(raw_word) -> dict[str, Any] | None:
    """Palabra con (start, end, text) válidos; None si falta algún dato."""
    if not isinstance(raw_word, dict):
        return None
    try:
        start = float(raw_word["start"])
        end = float(raw_word["end"])
        text = str(raw_word.get("text", raw_word.get("word", ""))).strip()
    except (KeyError, TypeError, ValueError):
        return None
    return _palabra_si_en_rango(start, end, text)


def _palabras_de_segmento(segment) -> list[dict[str, Any]]:
    """Palabras válidas de un segmento (lista vacía si no trae 'words')."""
    raw_words = segment.get("words")
    if not isinstance(raw_words, list):
        return []
    words: list[dict[str, Any]] = []
    for raw_word in raw_words:
        word = _palabra_valida(raw_word)
        if word is not None:
            words.append(word)
    return words


def _palabras_de_segmentos(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extrae y valida los timestamps por palabra de los segmentos Whisper."""
    words: list[dict[str, Any]] = []
    for segment in segments:
        if isinstance(segment, dict):
            words.extend(_palabras_de_segmento(segment))
    return words


def _oracion_map(posicion: int, current_words: list[dict[str, Any]]) -> dict[str, Any]:
    """Entrada del sentence_map para un grupo de palabras consecutivas."""
    return {
        "id": f"S_{posicion}",
        "start": current_words[0]["start"],
        "end": current_words[-1]["end"],
        "text": " ".join(item["text"] for item in current_words),
        "words": current_words,
    }


def _oracion_pendiente_de_palabras(sentence_map: list[dict[str, Any]], current_words: list[dict[str, Any]]) -> None:
    """Agrega la oración pendiente con las palabras restantes (si hay alguna)."""
    if current_words:
        sentence_map.append(_oracion_map(len(sentence_map) + 1, current_words))


def build_sentence_map(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa timestamps de palabra contiguos en oraciones identificadas S_1, S_2..."""
    words = _palabras_de_segmentos(segments)

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
            sentence_map.append(_oracion_map(len(sentence_map) + 1, current_words))
            current_words = []

    _oracion_pendiente_de_palabras(sentence_map, current_words)
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
                                    # Opcional (issue #116): tono del SFX del teaser; default none.
                                    "sfx_mood": {
                                        "type": "string",
                                        "enum": ["tension", "impact", "transition", "none"],
                                    },
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
- Opcional: sfx_mood por hook_candidate ("tension" | "impact" | "transition" | "none") según el tono del teaser; default "none" si no aplica
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


def _es_error_not_found_sdk(err_type: str, err_msg: str) -> bool:
    """True si el tipo de excepción o el mensaje indican NotFoundError del SDK."""
    return "notfounderror" in err_type or "not_found_error" in err_msg


def _es_error_modelo_invalido(err_msg: str) -> bool:
    """True si el mensaje indica modelo inválido o no encontrado."""
    return "model not found" in err_msg or "invalid model" in err_msg or "model_not_found" in err_msg


def _es_error_404_sin_auth(err_msg: str) -> bool:
    """True si hay un 404 en el mensaje sin ser un error de autenticación."""
    return "404" in err_msg and "authentication" not in err_msg


def _is_model_not_found_error(exc: Exception) -> bool:
    """Detecta error 404 / modelo inexistente de Anthropic para fallback."""
    err_type = type(exc).__name__.lower()
    err_msg = str(exc).lower()
    if _es_error_not_found_sdk(err_type, err_msg):
        return True
    if _es_error_modelo_invalido(err_msg):
        return True
    return _es_error_404_sin_auth(err_msg)


def _crear_cliente_anthropic(key: str) -> Any:
    """Cliente del SDK anthropic con timeout y workspace opcional."""
    import anthropic  # type: ignore

    sdk_kwargs: dict[str, Any] = {"api_key": key, "timeout": TIMEOUT}
    if ANTHROPIC_WORKSPACE_ID:
        sdk_kwargs["default_headers"] = {"anthropic-workspace-id": ANTHROPIC_WORKSPACE_ID}
    return anthropic.Anthropic(**sdk_kwargs)


def _llamar_sdk_anthropic(client: Any, prompt: str, tool: dict, tool_choice: dict, model: str) -> str | None:
    """Llama al SDK y extrae el tool_use. Devuelve None si la respuesta fue texto libre (se propagará)."""
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
    return _extraer_tool_use_sdk(msg)


def _tool_input_sdk_de_bloque(blk) -> str | None:
    """Input JSON del tool_use export_viral_clips en un bloque del SDK; None si no aplica."""
    if (
        getattr(blk, "type", "") == "tool_use"
        and getattr(blk, "name", "") == "export_viral_clips"
    ):
        tool_input = getattr(blk, "input", None)
        if isinstance(tool_input, dict):
            logger.info("Claude devolvió resultado mediante export_viral_clips (SDK)")
            return json.dumps(tool_input, ensure_ascii=False)
    return None


def _recorrer_contenido_sdk(msg) -> tuple[str, str | None]:
    """Recorre los bloques del contenido SDK. Devuelve (txt acumulado, tool_input_json)."""
    txt = ""
    for blk in getattr(msg, "content", []):
        extraido = _tool_input_sdk_de_bloque(blk)
        if extraido is not None:
            return txt, extraido
        if getattr(blk, "type", "") == "text":
            txt += getattr(blk, "text", "")
    return txt, None


def _levantar_error_sin_tool_use(txt: str) -> None:
    """RuntimeError según si el SDK devolvió texto libre o nada de tool_use."""
    if not txt:
        # no se recibió tool_use
        raise RuntimeError("Error en API de Claude: no se recibió tool_use de export_viral_clips")
    # Claude devolvió texto libre en vez de export_viral_clips
    raise RuntimeError("Error en API de Claude: Claude devolvió texto libre en vez de export_viral_clips")


def _extraer_tool_use_sdk(msg: Any) -> str | None:
    """Extrae el input de export_viral_clips desde la respuesta del SDK. None si no vino."""
    try:
        txt, extraido = _recorrer_contenido_sdk(msg)
    except Exception:
        txt = str(msg)
        extraido = None
    if extraido is not None:
        return extraido
    _levantar_error_sin_tool_use(txt)


def _es_error_de_timeout_sdk(exc: Exception) -> bool:
    err_type = type(exc).__name__
    err_msg = str(exc)
    return (
        err_type in ("APIConnectionError", "APITimeoutError")
        or "APIConnectionError" in err_type
        or "APITimeoutError" in err_type
        or "timeout" in err_msg.lower()
        or "timed out" in err_msg.lower()
    )


def _es_error_auth_sdk(err_msg: str, lowered: str) -> bool:
    """True si el error es de autenticación/permisos (401, auth, invalid)."""
    return "401" in err_msg or "authentication" in lowered or "invalid" in lowered


def _es_error_cuota_sdk(err_msg: str, lowered: str) -> bool:
    """True si el error es de cuota/rate limit (quota, rate, 429)."""
    return "quota" in lowered or "rate" in lowered or "429" in err_msg


def _relanzar_timeout_sdk(e: Exception) -> None:
    """Convierte un timeout del SDK en RuntimeError con el formato requerido."""
    err_type = type(e).__name__
    err_msg = str(e)
    logger.error(f"Error en API de Claude: {err_type} timeout {TIMEOUT}s — {err_msg}")
    raise RuntimeError(f"Error en Claude: {err_type} timeout {TIMEOUT}s — {err_msg}") from e


def _tratar_error_sdk(e: Exception) -> None:
    """Clasifica el error del SDK: timeout (relanza), auth/cuota (relanza) o fallback a requests."""
    # Captura explícita de APIConnectionError y APITimeoutError (spec: timeout 60.0, max_retries 2)
    if _es_error_de_timeout_sdk(e):
        _relanzar_timeout_sdk(e)
    # Si SDK falla con 401/cuota, propagar como Error en la API de Claude
    err_msg = str(e)
    lowered = err_msg.lower()
    if _es_error_auth_sdk(err_msg, lowered):
        raise RuntimeError(f"Error en API de Claude: {err_msg}") from e
    if _es_error_cuota_sdk(err_msg, lowered):
        raise RuntimeError(f"Error en API de Claude: {err_msg}") from e
    # Para otros errores, intentar fallback a requests
    logger.warning("Claude SDK fallo (%s), intentando requests", e)


def _tool_input_de_bloque(blk) -> str | None:
    """Input JSON del tool_use export_viral_clips en un bloque HTTP; None si no aplica."""
    if blk.get("type") == "tool_use" and blk.get("name") == "export_viral_clips":
        tool_input = blk.get("input")
        if isinstance(tool_input, dict):
            logger.info("Claude devolvió resultado mediante export_viral_clips (requests)")
            return json.dumps(tool_input, ensure_ascii=False)
    return None


def _txt_texto_de_bloques(data: dict) -> str:
    """Texto libre acumulado de los bloques de texto de la respuesta HTTP."""
    txt = ""
    for blk in data.get("content", []):
        if blk.get("type") == "text" and blk.get("text"):
            txt += blk["text"]
    return txt


def _extraer_tool_use_requests(data: dict) -> str:
    """Extrae el tool_use desde la respuesta JSON de la API HTTP. RuntimeError si no vino."""
    for blk in data.get("content", []):
        extraido = _tool_input_de_bloque(blk)
        if extraido is not None:
            return extraido
    if _txt_texto_de_bloques(data):
        raise RuntimeError("Error en API de Claude: Claude devolvió texto libre en vez de export_viral_clips")
    raise RuntimeError("Error en API de Claude: no se recibió tool_use de export_viral_clips")


def _cabeceras_anthropic(key: str) -> dict[str, str]:
    """Cabeceras HTTP para la API de Anthropic (workspace opcional)."""
    headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    if ANTHROPIC_WORKSPACE_ID:
        headers["anthropic-workspace-id"] = ANTHROPIC_WORKSPACE_ID
    return headers


def _respuesta_429(resp, attempt: int) -> bool:
    """True si hay que esperar y reintentar tras un 429 (aplica Retry-After)."""
    if resp.status_code == 429 and attempt < MAX_RETRIES:
        retry_after = int(resp.headers.get("Retry-After", 2 * attempt))
        time.sleep(retry_after)
        return True
    return False


def _exigir_200_anthropic(resp) -> None:
    """RuntimeError si la API HTTP devolvió un status distinto de 200."""
    if resp.status_code != 200:
        raise RuntimeError(f"Error en API de Claude: {resp.status_code} {resp.text[:800]}")


def _logear_error_red_requests(exc: Exception, attempt: int) -> None:
    """Log del fallo de red del intento; RuntimeError si era el último intento."""
    es_timeout = isinstance(exc, requests.exceptions.Timeout)
    if es_timeout:
        logger.error(f"Error en API de Claude: timeout {TIMEOUT}s (intento {attempt}/{MAX_RETRIES}) — {exc}")
    else:
        logger.error(f"Error en API de Claude: conexion fallo (intento {attempt}/{MAX_RETRIES}) — {exc}")
    if attempt == MAX_RETRIES:
        if es_timeout:
            raise RuntimeError(f"Error en Claude: timeout {TIMEOUT}s tras {MAX_RETRIES} intentos — {exc}") from exc
        raise RuntimeError(f"Error en Claude: conexion fallo {exc}") from exc


def _intento_requests(headers: dict, body: dict, attempt: int) -> str | None:
    """Un intento HTTP a la API de Anthropic. None si hay que reintentar."""
    try:
        resp = requests.post(ANTHROPIC_ENDPOINT, headers=headers, json=body, timeout=TIMEOUT)
        if _respuesta_429(resp, attempt):
            return None
        _exigir_200_anthropic(resp)
        return _extraer_tool_use_requests(resp.json())
    except RuntimeError as exc:
        # Ya viene con prefijo "Error en API de Claude"
        logger.error(f"Error en API de Claude: {exc}")
        raise
    except requests.exceptions.RequestException as exc:
        _logear_error_red_requests(exc, attempt)
        return None


def _pedir_con_requests(key: str, tool: dict, tool_choice: dict, model: str, prompt: str) -> str:
    """Fallback requests directo con reintentos (429 → Retry-After; timeout → reintento)."""
    headers = _cabeceras_anthropic(key)
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [tool],
        "tool_choice": tool_choice,
    }
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        resultado = _intento_requests(headers, body, attempt)
        if resultado is not None:
            return resultado
        time.sleep(2 * attempt)
    logger.error(f"Error en API de Claude: fallo tras reintentos {last_err}")
    raise RuntimeError(f"Error en Claude: fallo tras reintentos {last_err}")


def _call_anthropic_with_model(prompt: str, sentence_ids: list[str], model: str) -> str:
    key = _get_key()
    if not key:
        logger.error("Error en API de Claude: ANTHROPIC_API_KEY no configurada (revisar .env y docker-compose.yml ANTHROPIC_API_KEY)")
        raise RuntimeError("Error en API de Claude: ANTHROPIC_API_KEY no configurada (revisar .env y docker-compose.yml ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY})")
    tool = _build_export_viral_clips_tool(sentence_ids)
    tool_choice = {"type": "tool", "name": "export_viral_clips"}
    # Intentar SDK anthropic si está instalado — con timeout explícito 60-90s
    try:
        client = _crear_cliente_anthropic(key)
        resultado = _llamar_sdk_anthropic(client, prompt, tool, tool_choice, model)
        if resultado is not None:
            return resultado
    except ImportError:
        pass
    except Exception as e:
        _tratar_error_sdk(e)

    # Fallback requests directo
    return _pedir_con_requests(key, tool, tool_choice, model, prompt)


def _call_anthropic(prompt: str, sentence_ids: list[str]) -> str:
    """Intenta con CLAUDE_MODEL y, si el modelo no existe (404), reintenta con haiku."""
    try:
        return _call_anthropic_with_model(prompt, sentence_ids, CLAUDE_MODEL)
    except Exception as primary_err:
        if not _is_model_not_found_error(primary_err):
            raise
        logger.warning(
            "Claude modelo '%s' no disponible (%s); reintentando con fallback '%s'",
            CLAUDE_MODEL, primary_err, CLAUDE_FALLBACK_MODEL,
        )
        return _call_anthropic_with_model(prompt, sentence_ids, CLAUDE_FALLBACK_MODEL)


def _reparar_json_raw(raw: str) -> dict:
    """Repara y parsea la respuesta cruda como objeto JSON."""
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
    return data


def _reparar_clips_raw(data: dict) -> list:
    """Extrae 'clips' reparando el string anidado si hace falta."""
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
    return clips_raw


def _es_id_oracion(valor: str) -> bool:
    """True si el valor es un ID de oración S_<n>."""
    return re.fullmatch(r"S_\d+", valor) is not None


def _tiene_campos_de_timestamp(c: dict) -> bool:
    """True si el clip crudo trae campos de timestamp flotante (no permitidos)."""
    return any(key in c for key in ("start", "end", "start_time", "end_time"))


def _tipos_de_clip_validos(raw_hook_candidates, raw_has_hook) -> bool:
    """True si hook_candidates es lista y has_hook es booleano."""
    return isinstance(raw_hook_candidates, list) and isinstance(raw_has_hook, bool)


def _formato_de_clip_valido(start_id: str, end_id: str, title: str, raw_hook_candidates, raw_has_hook) -> bool:
    """True si IDs de oración, título y tipos cumplen el esquema del clip."""
    if not (_es_id_oracion(start_id) and _es_id_oracion(end_id)):
        return False
    if not title:
        return False
    return _tipos_de_clip_validos(raw_hook_candidates, raw_has_hook)


def _score_normalizado(score: float) -> float | None:
    """Score 1-10; normaliza la escala 0-100. None si no es válido."""
    if 1 <= score <= 10:
        return score
    # Normalizar si vino 0-100
    if 10 < score <= 100:
        return score / 10
    return None


def _campos_base_de_clip(c: dict) -> tuple | None:
    """Campos crudos del clip validados en formato; None si no cumplen el esquema."""
    if _tiene_campos_de_timestamp(c):
        return None
    start_sentence_id = str(c.get("start_sentence_id", "")).strip()
    end_sentence_id = str(c.get("end_sentence_id", "")).strip()
    score = float(c.get("score", c.get("viral_score", 0)))
    title = str(c.get("title", "")).strip()[:60]
    raw_hook_candidates = c.get("hook_candidates", [])
    raw_has_hook = c.get("has_hook")
    if not _formato_de_clip_valido(start_sentence_id, end_sentence_id, title, raw_hook_candidates, raw_has_hook):
        return None
    score = _score_normalizado(score)
    if score is None:
        return None
    return start_sentence_id, end_sentence_id, score, title, raw_hook_candidates, raw_has_hook


def _has_hook_efectivo(raw_has_hook: bool, hook_candidates: list[dict]) -> bool:
    """has_hook real: solo si hay un candidato con score >= 8 y standalone."""
    return raw_has_hook and any(
        candidate["curiosity_score"] >= 8 and candidate["makes_sense_standalone"]
        for candidate in hook_candidates
    )


def _validar_clip_candidato(c: dict) -> dict | None:
    """Valida un clip crudo de Claude. None si no cumple el esquema."""
    campos = _campos_base_de_clip(c)
    if campos is None:
        return None
    start_sentence_id, end_sentence_id, score, title, raw_hook_candidates, raw_has_hook = campos
    hook_candidates = _validar_hook_candidates(raw_hook_candidates)
    return {
        "start_sentence_id": start_sentence_id,
        "end_sentence_id": end_sentence_id,
        "score": score,
        "title": title,
        "hook_candidates": hook_candidates,
        "has_hook": _has_hook_efectivo(raw_has_hook, hook_candidates),
    }


def _rango_curiosity_valido(curiosity_score: int, standalone) -> bool:
    """True si curiosity_score está en 1-10 y standalone es booleano."""
    return 1 <= curiosity_score <= 10 and isinstance(standalone, bool)


def _ids_hook_validos(hook_start_id: str, hook_end_id: str) -> bool:
    """True si ambos extremos del hook son IDs de oración válidos."""
    return _es_id_oracion(hook_start_id) and _es_id_oracion(hook_end_id)


_SFX_MOODS = ("tension", "impact", "transition", "none")


def _sfx_mood_de(candidate) -> str:
    """sfx_mood del hook candidate con whitelist; "none" si falta o es inválido (issue #116)."""
    mood = str(candidate.get("sfx_mood", "none")).strip().lower() if isinstance(candidate, dict) else "none"
    return mood if mood in _SFX_MOODS else "none"


def _curiosity_de_candidate(candidate) -> int | None:
    """curiosity_score como entero; None si no es numérico."""
    try:
        return int(candidate.get("curiosity_score", 0))
    except (TypeError, ValueError):
        return None


def _datos_hook_candidate(candidate) -> tuple | None:
    """(start_id, end_id, curiosity, standalone) del candidate; None si es inválido."""
    if not isinstance(candidate, dict):
        return None
    hook_start_id = str(candidate.get("start_sentence_id", "")).strip()
    hook_end_id = str(candidate.get("end_sentence_id", "")).strip()
    standalone = candidate.get("makes_sense_standalone")
    curiosity_score = _curiosity_de_candidate(candidate)
    if curiosity_score is None:
        return None
    return hook_start_id, hook_end_id, curiosity_score, standalone


def _hook_candidate_valido(candidate) -> dict | None:
    """Candidate de hook validado (IDs S_n, curiosity 1-10, standalone bool); None si no."""
    datos = _datos_hook_candidate(candidate)
    if datos is None:
        return None
    hook_start_id, hook_end_id, curiosity_score, standalone = datos
    if _ids_hook_validos(hook_start_id, hook_end_id) and _rango_curiosity_valido(curiosity_score, standalone):
        return {
            "start_sentence_id": hook_start_id,
            "end_sentence_id": hook_end_id,
            "curiosity_score": curiosity_score,
            "makes_sense_standalone": standalone,
            "sfx_mood": _sfx_mood_de(candidate),
        }
    return None


def _validar_hook_candidates(raw_hook_candidates: list) -> list[dict[str, Any]]:
    """Valida los primeros 5 hook candidates (IDs S_n, curiosity 1-10, standalone bool)."""
    hook_candidates: list[dict[str, Any]] = []
    for candidate in raw_hook_candidates[:5]:
        valido = _hook_candidate_valido(candidate)
        if valido is not None:
            hook_candidates.append(valido)
    return hook_candidates


def _parse_and_validate(raw: str) -> list[dict[str, Any]]:
    data = _reparar_json_raw(raw)
    clips_raw = _reparar_clips_raw(data)
    validated: list[dict[str, Any]] = []
    for c in clips_raw:
        try:
            validado = _validar_clip_candidato(c)
            if validado is not None:
                validated.append(validado)
        except Exception:
            continue
    # Ordenar por score descendente, max 3
    validated.sort(key=lambda x: x["score"], reverse=True)
    return validated[:3]


def _exigir_key_anthropic() -> None:
    """RuntimeError si ANTHROPIC_API_KEY no está configurada."""
    key = _get_key()
    if not key:
        raise RuntimeError("Error en API de Claude: ANTHROPIC_API_KEY no configurada")


def _sentence_ids_de_map(sentence_map: list[dict[str, Any]]) -> list[str]:
    """IDs de las oraciones del sentence_map."""
    return [str(sentence["id"]) for sentence in sentence_map]


def _preparar_prompt_claude(
    segments: list[dict[str, Any]],
    duration_hint: float | None,
    sentence_map: list[dict[str, Any]] | None,
) -> tuple[str, list[str]]:
    """(prompt, sentence_ids); RuntimeError si faltan segmentos, key o transcript."""
    if not segments:
        raise RuntimeError("Error en API de Claude: no hay segmentos de transcripción para analizar")
    _exigir_key_anthropic()
    if sentence_map is None:
        sentence_map = build_sentence_map(segments)
    transcript_text = _format_sentence_map(sentence_map)
    if not transcript_text.strip():
        raise RuntimeError("Error en API de Claude: transcripción vacía")
    sentence_ids = _sentence_ids_de_map(sentence_map)
    return _build_claude_prompt(transcript_text, sentence_ids, duration_hint), sentence_ids


def _posiciones_hook_validas(hook_start_id: str, hook_end_id: str, sentence_positions: dict) -> bool:
    """True si los IDs del hook existen y están en orden válido."""
    return (
        hook_start_id in sentence_positions
        and hook_end_id in sentence_positions
        and sentence_positions[hook_start_id] <= sentence_positions[hook_end_id]
    )


def _datos_hook_candidate_posicion(candidate) -> tuple | None:
    """(start_id, end_id, curiosity, standalone) crudos del candidate; None si es inválido."""
    if not isinstance(candidate, dict):
        return None
    hook_start_id = str(candidate.get("start_sentence_id", ""))
    hook_end_id = str(candidate.get("end_sentence_id", ""))
    curiosity_score = _curiosity_de_candidate(candidate)
    if curiosity_score is None:
        return None
    return hook_start_id, hook_end_id, curiosity_score, candidate.get("makes_sense_standalone")


def _hook_candidate_posicion_valido(candidate, sentence_positions: dict) -> dict | None:
    """Candidate de hook validado contra las posiciones del sentence_map; None si no."""
    datos = _datos_hook_candidate_posicion(candidate)
    if datos is None:
        return None
    hook_start_id, hook_end_id, curiosity_score, standalone = datos
    if _posiciones_hook_validas(hook_start_id, hook_end_id, sentence_positions) and _rango_curiosity_valido(
        curiosity_score, standalone
    ):
        return {
            "start_sentence_id": hook_start_id,
            "end_sentence_id": hook_end_id,
            "curiosity_score": curiosity_score,
            "makes_sense_standalone": standalone,
            "sfx_mood": _sfx_mood_de(candidate),
        }
    return None


def _clip_en_rango_valido(clip: dict, sentence_positions: dict) -> bool:
    """True si start/end del clip existen y están en orden."""
    start_id = clip["start_sentence_id"]
    end_id = clip["end_sentence_id"]
    return (
        start_id in sentence_positions
        and end_id in sentence_positions
        and sentence_positions[start_id] <= sentence_positions[end_id]
    )


def _has_hook_final(clip: dict) -> bool:
    """has_hook recalculado sobre los candidates ya filtrados."""
    return bool(clip["has_hook"]) and any(
        candidate["curiosity_score"] >= 8 and candidate["makes_sense_standalone"]
        for candidate in clip["hook_candidates"]
    )


def _candidates_validos_de_clip(clip: dict, sentence_positions: dict) -> list[dict[str, Any]]:
    """Hook candidates del clip validados contra las posiciones del sentence_map."""
    valid_candidates: list[dict[str, Any]] = []
    for candidate in clip["hook_candidates"]:
        valido = _hook_candidate_posicion_valido(candidate, sentence_positions)
        if valido is not None:
            valid_candidates.append(valido)
    return valid_candidates


def _filtrar_clips_posiciones(clips: list[dict[str, Any]], sentence_positions: dict) -> list[dict[str, Any]]:
    """Filtra clips y hook candidates por orden/posiciones de oraciones."""
    valid_clips: list[dict[str, Any]] = []
    for clip in clips:
        if not _clip_en_rango_valido(clip, sentence_positions):
            continue
        clip["hook_candidates"] = _candidates_validos_de_clip(clip, sentence_positions)
        clip["has_hook"] = _has_hook_final(clip)
        valid_clips.append(clip)
    return valid_clips


def select_clips_via_claude(
    segments: list[dict[str, Any]],
    duration_hint: float | None = None,
    sentence_map: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Función principal: recibe transcripción con timestamps y devuelve clips vía Claude.

    Lanza RuntimeError con prefijo "Error en API de Claude: ..." si falta key o falla la API.
    No hace fallback heurístico.
    """
    prompt, sentence_ids = _preparar_prompt_claude(segments, duration_hint, sentence_map)
    raw = _call_anthropic(prompt, sentence_ids)
    clips = _parse_and_validate(raw)
    sentence_positions = {sentence_id: index for index, sentence_id in enumerate(sentence_ids)}
    clips = _filtrar_clips_posiciones(clips, sentence_positions)
    if not clips:
        raise RuntimeError(f"Error en API de Claude: validación dejó 0 clips — raw: {raw[:500]}")
    return clips
