from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, TypedDict

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Carga .env segura sin parents[3] fijo que causa IndexError en /app
_cur_hook = Path(__file__).resolve()
_env_candidates: list[Path] = []
for _idx in (3, 2, 1, 0):
    if _idx < len(_cur_hook.parents):
        _env_candidates.append(_cur_hook.parents[_idx] / ".env")
# También buscar raíz por marcador (engine.py / backend_fastapi) sin desbordar
for _p in _cur_hook.parents:
    try:
        cand = _p / ".env"
        if cand not in _env_candidates and cand.exists():
            _env_candidates.append(cand)
    except Exception:
        continue
for _p in _env_candidates:
    try:
        load_dotenv(dotenv_path=_p, override=False)
    except Exception:
        continue


class HookSegment(TypedDict):
    text: str
    start_time: float
    end_time: float
    duration: float


class HookClip(TypedDict):
    title: str
    start_time: float
    end_time: float
    hook: HookSegment
    viral_score: int
    reasoning: str


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5").strip()
ANTHROPIC_VERSION = os.getenv("ANTHROPIC_VERSION", "2023-06-01").strip()
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_ENDPOINT = os.getenv("OPENROUTER_ENDPOINT", "https://openrouter.ai/api/v1/chat/completions").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", os.getenv("OPENAI_MODEL", "anthropic/claude-3.5-sonnet")).strip()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
API_ENDPOINT = os.getenv("API_ENDPOINT", "https://api.deepseek.com/v1/chat/completions").strip()
MODEL = os.getenv("MODEL", "deepseek-chat").strip() or os.getenv("OPENAI_MODEL", "deepseek-chat").strip()

TIMEOUT = 120
MAX_RETRIES = 3


def _key_openai_valida() -> bool:
    """True si OPENAI_API_KEY parece una key de OpenAI válida."""
    return bool(OPENAI_API_KEY) and OPENAI_API_KEY.startswith("sk-")


def _provider_openai_compatible() -> str:
    """Proveedor openai/openrouter/deepseek según las keys disponibles; vacío si no hay."""
    if _key_openai_valida():
        return "openai"
    if OPENROUTER_API_KEY:
        return "openrouter"
    if DEEPSEEK_API_KEY:
        return "deepseek"
    return ""


def _get_provider() -> str:
    """Proveedor LLM a usar según las API keys configuradas."""
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return _provider_openai_compatible() or "none"


def _format_transcript(segments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for s in segments:
        try:
            st = float(s.get("start", s.get("start_time", 0)))
            en = float(s.get("end", s.get("end_time", 0)))
            txt = str(s.get("text", "")).strip()
            if not txt:
                continue
            lines.append(f"[{st:.1f} - {en:.1f}] {txt}")
        except Exception:
            continue
    return "\n".join(lines)


def _build_hook_prompt(transcript_text: str, duration_hint: float | None = None) -> str:
    dur_info = f"Duracion total video: {duration_hint:.1f}s" if duration_hint else "Duracion total: desconocida"
    return f"""Eres un editor viral experto en TikTok/Reels/Shorts en español rioplatense, especializado en alto impacto y retencion 9:16. Analizas transcripciones con timestamps de Whisper y detectas ganchos virales con TEASER HOOK.

TAREA: Identifica 1 a 3 clips principales (15-60s) con mayor viralidad, y para CADA clip selecciona la frase mas potente/contundente de 3-6s CONTENIDA DENTRO DEL CLIP para usar como TEASER inicial. El video final sera: [Hook 3-6s][Clip completo 15-60s] concatenados. El hook DEBE estar temporalmente dentro del clip.

{dur_info}

TRANSCRIPCION CON TIMESTAMPS (start - end en segundos):
{transcript_text}

CRITERIOS TEASER HOOK - ALTO IMPACTO Y FLUIDEZ:
- Criterio #1 - IMPACTO Y FUERZA NARRATIVA (PRIORIDAD ABSOLUTA): Prioriza declaraciones contundentes, picos emocionales, datos contundentes o remates potentes. Triunfos, definiciones de partido, giros narrativos, sentencias con energia, numeros que sorprenden o cierres que dejan sin aliento. Elige la frase que por si sola haga que nadie pueda scrollear.
- Criterio #2 - FLUIDEZ Y CIERRE: La frase de ~5s DEBE tener sentido completo por si sola. Es un teaser autonomo: no selecciones fragmentos que terminen en muletillas o conectores colgando como "pero me parece que...", "eh...", "o sea...", "y bueno...". Debe sonar redonda, con sujeto+predicado y cierre claro. Si la frase queda trunca, descártala.
- EQUILIBRIO: Valora tanto afirmaciones positivas e intensas (celebracion, revancha, logro) como opiniones criticas con sustancia. El criterio no es polemica gratuita sino alta retencion visual/auditiva: energia, claridad y fuerza narrativa.

SCORING viral_score - ESTRUCTURA CLARA:
- 80-100 para clips con estructura clara: Gancho potente de apertura (contundente, completo, energetico) + Clip coherente que sostiene el interes hasta el cierre. El hook debe ser una frase redonda de alto impacto.
- 65-79 para hooks correctos pero menos memorables o clip con pequenos baches.
- <65 para hooks truncos, tibios sin energia o con muletillas finales.

CRITERIOS VIRALIDAD BASE (ordena por potencial):
- revelacion/exclusiva 10, controversia 9, dato impactante 8, emocional 7, tactico 6, prediccion 5
- Señales extra: dato con numeros, energia vocal, remate potente

REGLAS ESTRICTAS:
- Clip: 15.0 <= (end_time - start_time) <= 60.0
- Hook: 4.5 <= duration <= 5.5 (OBJETIVO 5.0s - teaser de video estandarizado), y hook.start_time >= clip.start_time y hook.end_time <= clip.end_time
- Hook duration = hook.end_time - hook.start_time debe ser 4.5-5.5
- Usa timestamps EXACTOS de la transcripcion (no inventes fuera de rango)
- hook.text debe coincidir literal con frase de la transcripcion en ese rango y ser frase completa sin muletilla final
- viral_score 80-100 para estructura gancho potente + clip coherente (ver scoring arriba)
- Devuelve SOLO JSON valido sin markdown, sin texto antes/después

FORMATO JSON OBLIGATORIO:
{{
  "clips": [
    {{
      "title": "Titulo del clip (max 60 chars, rioplatense, con dato concreto)",
      "start_time": 10.0,
      "end_time": 55.0,
      "hook": {{
        "text": "Frase de 5 segundos mas picante",
        "start_time": 32.5,
        "end_time": 37.5,
        "duration": 5.0
      }},
      "viral_score": 90,
      "reasoning": "Explicacion por que este gancho atrae retencion en 1 oracion"
    }}
  ]
}}

VALIDACION:
- Si no hay momentos virales, devuelve {{"clips": []}}
- Max 3 clips, ordenados por viral_score descendente
- hook.text 5-15 palabras, mayusculas no requeridas
"""


def _esperar_retry_429(resp, attempt: int, retries: int) -> bool:
    """True si hay que reintentar tras un 429 (aplica Retry-After)."""
    if resp.status_code == 429 and attempt < retries:
        retry_after = int(resp.headers.get("Retry-After", 2 * attempt))
        time.sleep(retry_after)
        return True
    return False


def _logear_fallo_red(exc: Exception, attempt: int, retries: int, timeout: int) -> None:
    """TimeoutError/ConnectionError si era el último intento; si no, reintenta."""
    if isinstance(exc, requests.exceptions.Timeout):
        if attempt == retries:
            raise TimeoutError(f"LLM timeout {timeout}s tras {retries} intentos") from exc
        return
    if attempt == retries:
        raise ConnectionError(f"LLM conexion fallo: {exc}") from exc


def _post_with_retry(url: str, headers: dict[str, str], body: dict[str, Any], timeout: int = TIMEOUT, retries: int = MAX_RETRIES) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=timeout)
            if _esperar_retry_429(resp, attempt, retries):
                continue
            return resp
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            _logear_fallo_red(exc, attempt, retries, timeout)
        time.sleep(2 * attempt)
    raise ConnectionError(f"LLM fallo tras reintentos: {last_exc}")


def _texto_de_contenido(data: dict) -> str:
    """Texto acumulado de los bloques de texto de la respuesta Anthropic."""
    txt = ""
    for blk in data.get("content", []):
        if blk.get("type") == "text" and blk.get("text"):
            txt += blk["text"]
    return txt


def _call_anthropic(prompt: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY no configurada")
    headers = {"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    body: dict[str, Any] = {"model": ANTHROPIC_MODEL, "max_tokens": 4096, "thinking": {"type": "disabled"}, "messages": [{"role": "user", "content": prompt}]}
    resp = _post_with_retry(ANTHROPIC_ENDPOINT, headers, body)
    if resp.status_code != 200:
        raise ConnectionError(f"Anthropic {resp.status_code}: {resp.text[:800]}")
    data = resp.json()
    txt = _texto_de_contenido(data)
    if not txt:
        raise ValueError(f"Anthropic respuesta sin texto: {data}")
    return txt


def _key_openai_compatible() -> str:
    """API key del proveedor OpenAI-compatible (openrouter tiene prioridad)."""
    if OPENROUTER_API_KEY:
        return OPENROUTER_API_KEY
    return OPENAI_API_KEY or DEEPSEEK_API_KEY


def _endpoint_y_modelo() -> tuple[str, str]:
    """Endpoint y modelo según el proveedor OpenAI-compatible configurado."""
    if OPENROUTER_API_KEY:
        return OPENROUTER_ENDPOINT, OPENROUTER_MODEL
    if DEEPSEEK_API_KEY and not OPENAI_API_KEY:
        return "https://api.deepseek.com/v1/chat/completions", os.getenv("MODEL", "deepseek-chat")
    return API_ENDPOINT, MODEL


def _call_openai_compatible(prompt: str) -> str:
    key = _key_openai_compatible()
    if not key:
        raise ValueError("OPENAI_API_KEY / OPENROUTER_API_KEY / DEEPSEEK_API_KEY no configurada")
    endpoint, model = _endpoint_y_modelo()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "HTTP-Referer": "https://clipsai.local", "X-Title": "ClipsAI"}
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.4, "max_tokens": 4096}
    resp = _post_with_retry(endpoint, headers, body)
    if resp.status_code != 200:
        raise ConnectionError(f"OpenAI-compatible {resp.status_code}: {resp.text[:800]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise ValueError(f"Respuesta OpenAI invalida: {data}") from exc


def _call_llm(prompt: str) -> str:
    provider = _get_provider()
    try:
        if provider == "anthropic":
            return _call_anthropic(prompt)
        if provider in ("openai", "deepseek", "openrouter"):
            return _call_openai_compatible(prompt)
    except Exception:
        logger.exception("Fallo LLM provider=%s", provider)
        raise
    raise ValueError("Ninguna API LLM configurada (ANTHROPIC_API_KEY u OPENAI_API_KEY/OPENROUTER_API_KEY/DEEPSEEK_API_KEY en .env)")


def _parse_json_strict(raw: str) -> dict[str, Any]:
    m = re.search(r"\{[\s\S]*\}", raw)
    candidate = m.group(0) if m else raw
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([\}\]])", r"\1", candidate)
        return json.loads(fixed)


def _datos_crudos_de_clip(c) -> tuple:
    """Convierte los campos crudos del clip LLM a tipos numéricos/texto (puede lanzar)."""
    title = str(c.get("title", "")).strip()[:80]
    st = float(c.get("start_time", 0))
    en = float(c.get("end_time", 0))
    hook_raw = c.get("hook", {})
    hk_text = str(hook_raw.get("text", "")).strip()
    hk_st = float(hook_raw.get("start_time", 0))
    hk_en = float(hook_raw.get("end_time", 0))
    hk_dur = float(hook_raw.get("duration", hk_en - hk_st))
    score = int(c.get("viral_score", c.get("score", 70)))
    reasoning = str(c.get("reasoning", c.get("motivo", ""))).strip()
    return title, st, en, hk_text, hk_st, hk_en, hk_dur, score, reasoning


def _datos_no_vacios(title: str, hk_text: str) -> bool:
    """True si el título y el texto del hook no están vacíos."""
    return bool(title) and bool(hk_text)


def _clip_llm_valido(st: float, en: float, hk_st: float, hk_en: float, title: str, hk_text: str) -> bool:
    """True si título/hook no vacíos, duraciones 15-60 y 3-6, y hook dentro del clip."""
    if not _datos_no_vacios(title, hk_text):
        return False
    if not (15.0 <= (en - st) <= 60.0):
        return False
    if not (3.0 <= (hk_en - hk_st) <= 6.0):
        return False
    return st <= hk_st < hk_en <= en


def _score_acotado(score: int) -> int:
    """Score dentro de 0-100 (clamp si vino fuera de rango)."""
    if 0 <= score <= 100:
        return score
    return max(0, min(100, score))


def _clip_validado(c) -> HookClip | None:
    """HookClip validado desde un clip crudo del LLM; None si no cumple el esquema."""
    try:
        title, st, en, hk_text, hk_st, hk_en, hk_dur, score, reasoning = _datos_crudos_de_clip(c)
        if not _clip_llm_valido(st, en, hk_st, hk_en, title, hk_text):
            return None
        return HookClip(title=title, start_time=st, end_time=en, hook=HookSegment(text=hk_text, start_time=hk_st, end_time=hk_en, duration=hk_dur), viral_score=_score_acotado(score), reasoning=reasoning)
    except Exception:
        return None


def _validate_clips(data: dict[str, Any]) -> list[HookClip]:
    clips_raw = data.get("clips", [])
    if not isinstance(clips_raw, list):
        raise ValueError("JSON 'clips' debe ser lista")
    validated: list[HookClip] = []
    for c in clips_raw:
        valido = _clip_validado(c)
        if valido is not None:
            validated.append(valido)
    validated.sort(key=lambda x: x["viral_score"], reverse=True)
    return validated[:3]


def _exigir_provider_hooks() -> str:
    """Proveedor LLM; RuntimeError si no hay ninguna API configurada."""
    provider = _get_provider()
    if provider == "none":
        raise RuntimeError("Error en API de Claude: ANTHROPIC_API_KEY no configurada (revisar .env y docker-compose.yml ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY})")
    return provider


def _prompt_y_llamada_hooks(segments: list[dict[str, Any]], duration_hint: float | None) -> tuple[str, list[HookClip]]:
    """(raw, clips) del LLM de hooks; ValueError si la transcripción está vacía."""
    transcript_text = _format_transcript(segments)
    if not transcript_text.strip():
        raise ValueError("Transcripcion vacia")
    prompt = _build_hook_prompt(transcript_text, duration_hint)
    raw = _call_llm(prompt)
    data = _parse_json_strict(raw)
    return raw, _validate_clips(data)


def _logear_exito_hooks(provider: str) -> None:
    """Log de confirmación del análisis exitoso según el proveedor."""
    if provider == "anthropic":
        logger.info("Análisis de virabilidad completado exitosamente vía Claude API")
    else:
        logger.info("Análisis de virabilidad completado exitosamente vía %s API", provider)


def _publicar_hooks_exitosos(provider: str, segments: list[dict[str, Any]], duration_hint: float | None) -> list[HookClip]:
    """Pipeline exitoso del análisis de hooks (logs incluidos)."""
    raw, clips = _prompt_y_llamada_hooks(segments, duration_hint)
    # Log de confirmación cuando Claude responde exitosamente
    _logear_exito_hooks(provider)
    if not clips:
        raise RuntimeError(f"Error en API de Claude: validación dejó 0 clips — raw: {raw[:500]}")
    # Selección semántica vía LLM tiene prioridad sobre heurística nativa (sin fallback)
    logger.info("Hook: usando resultado semántico de %s (%s clips validados)", provider, len(clips))
    return clips


def _relanzar_error_hooks(e: Exception) -> None:
    """Propaga el error con prefijo 'Error en API de Claude' si no lo tiene."""
    if "Error en la API de Claude" not in str(e):
        raise RuntimeError(f"Error en API de Claude: {e}") from e
    raise


def detect_hooks(segments: list[dict[str, Any]], duration_hint: float | None = None, mock: bool = False) -> list[HookClip]:
    # Modo mock explícito para tests
    if mock:
        return _mock_hooks(segments)
    # Integración nativa obligatoria: sin ANTHROPIC_API_KEY debe fallar explícitamente, sin fallback heurístico
    provider = _exigir_provider_hooks()
    try:
        return _publicar_hooks_exitosos(provider, segments, duration_hint)
    except RuntimeError as e:
        # Propagar con prefijo requerido si no lo tiene
        _relanzar_error_hooks(e)
    except Exception as e:
        logger.exception("detect_hooks fallo")
        raise RuntimeError(f"Error en API de Claude: {e}") from e


def _ventana_clip_mock(segments: list[dict[str, Any]]) -> tuple[float, float]:
    """Ventana [clip_start, clip_end] del clip mock."""
    total_start = float(segments[0].get("start", 0))
    total_end = float(segments[-1].get("end", total_start + 30))
    total_dur = total_end - total_start
    clip_start = total_start + max(0, total_dur * 0.1)
    clip_end = min(total_end, clip_start + 40)
    if clip_end - clip_start < 15:
        clip_end = clip_start + 15
    return clip_start, clip_end


def _ventana_hook_mock(clip_start: float, clip_end: float) -> tuple[float, float]:
    """Ventana [hook_start, hook_end] de 5s dentro del clip mock."""
    mid = (clip_start + clip_end) / 2
    hook_start = max(clip_start, mid - 2.5)
    hook_end = hook_start + 5.0
    if hook_end > clip_end:
        hook_end = clip_end
        hook_start = hook_end - 5
    return hook_start, hook_end


def _texto_hook_mock(segments: list[dict[str, Any]], hook_start: float, hook_default: str) -> str:
    """Texto del hook mock: frase del segmento más cercano al inicio del hook."""
    for s in segments:
        try:
            if abs(float(s.get("start", 0)) - hook_start) < 2:
                return str(s.get("text", hook_default)).strip().upper()[:60]
        except Exception:
            continue
    return hook_default


def _mock_hooks(segments: list[dict[str, Any]]) -> list[HookClip]:
    if not segments:
        return []
    clip_start, clip_end = _ventana_clip_mock(segments)
    hook_start, hook_end = _ventana_hook_mock(clip_start, clip_end)
    hook_text = _texto_hook_mock(segments, hook_start, "ESTA ES LA FRASE MAS PICANTE DEL CLIP")
    return [HookClip(title="Clip viral detectado (mock)", start_time=round(clip_start, 1), end_time=round(clip_end, 1), hook=HookSegment(text=hook_text, start_time=round(hook_start, 1), end_time=round(hook_end, 1), duration=round(hook_end - hook_start, 1)), viral_score=88, reasoning="Mock hook: frase central con mayor intensidad para teaser")]


def _segundo_de_timestamp_linea(ts: str) -> float:
    """Segundos de un timestamp HH:MM:SS / MM:SS / SS de una línea de transcript."""
    if ":" in ts:
        parts = ts.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return int(parts[0]) * 60 + float(parts[1])
    return float(ts)


def _segmento_de_linea_transcript(line: str) -> dict[str, Any] | None:
    """Segmento {'start','end','text'} de una línea; None si el timestamp es inválido."""
    if " - " not in line:
        return {"start": 0, "end": 3, "text": line}
    ts, txt = line.split(" - ", 1)
    try:
        sec = _segundo_de_timestamp_linea(ts)
    except Exception:
        return None
    return {"start": sec, "end": sec + 3, "text": txt}


def _segmentos_de_archivo_transcript(text: str) -> list[dict[str, Any]]:
    """Segmentos parseados del archivo de transcript."""
    segs: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        seg = _segmento_de_linea_transcript(line)
        if seg is not None:
            segs.append(seg)
    return segs


def detect_hooks_from_transcript_file(transcript_path: str | Path, mock: bool = False) -> list[HookClip]:
    p = Path(transcript_path)
    if not p.is_file():
        raise FileNotFoundError(f"Transcripcion no encontrada: {p}")
    text = p.read_text(encoding="utf-8")
    return detect_hooks(_segmentos_de_archivo_transcript(text), mock=mock)
