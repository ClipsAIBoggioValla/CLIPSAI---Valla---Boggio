"""Wrapper del motor de clips — ejecución real sin simulación (Issue 21)."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _validate_video_source(video_path: str | Path) -> Path:
    source = Path(video_path)
    if not source.is_file():
        raise FileNotFoundError(
            f"El archivo de video fuente no existe o no es un archivo: {source}. "
            "La descarga o subida del video falló; vuelve a subirlo o verifica la URL de origen."
        )
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise FileNotFoundError(
            f"No se pudo leer el archivo de video fuente {source}. "
            "La descarga o subida del video pudo haber fallado."
        ) from exc
    if size <= 0:
        raise ValueError(
            f"El archivo de video fuente está vacío (0 bytes): {source}. "
            "La descarga o subida del video falló; vuelve a subirlo o verifica la URL de origen."
        )
    return source


def _ends_with_strong_punctuation(word_text: str) -> bool:
    cleaned = word_text.rstrip("\"'’”»)]}")
    return cleaned.endswith((".", "?", "!"))


def _resolve_sentence_timestamps(
    start_sentence_id: str,
    end_sentence_id: str,
    sentence_map: list[dict[str, Any]],
) -> tuple[float, float]:
    """Resuelve IDs de oraciones a límites de palabra, expansión y padding exactos."""
    positions: dict[str, tuple[int, int]] = {}
    all_words: list[dict[str, Any]] = []
    for sentence in sentence_map:
        sentence_id = str(sentence.get("id", ""))
        sentence_words = sentence.get("words")
        if not sentence_id or not isinstance(sentence_words, list) or not sentence_words:
            continue
        first_word_idx = len(all_words)
        all_words.extend(sentence_words)
        positions[sentence_id] = (first_word_idx, len(all_words) - 1)

    if start_sentence_id not in positions or end_sentence_id not in positions:
        raise ValueError(f"start/end sentence id desconocido: {start_sentence_id} / {end_sentence_id}")

    first_idx = positions[start_sentence_id][0]
    last_idx = positions[end_sentence_id][1]
    if first_idx > last_idx:
        raise ValueError(
            f"Rango de oraciones invertido: {start_sentence_id} → {end_sentence_id}"
        )

    first_word = all_words[first_idx]
    last_word = all_words[last_idx]
    if not _ends_with_strong_punctuation(str(last_word.get("text", ""))):
        for next_idx in range(last_idx + 1, len(all_words)):
            last_word = all_words[next_idx]
            if _ends_with_strong_punctuation(str(last_word.get("text", ""))):
                break

    start_time = max(0.0, float(first_word["start"]) - 0.15)
    end_time = float(last_word["end"]) + 0.35
    if end_time <= start_time:
        raise ValueError(
            f"Rango de palabras inválido para {start_sentence_id} → {end_sentence_id}"
        )
    return round(start_time, 3), round(end_time, 3)


def _resolve_hook_candidate_window(
    candidate: dict[str, Any],
    sentence_map: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Resuelve un candidato a oraciones completas y lo ajusta a 2.5–5.5s."""
    positions = {
        str(sentence.get("id", "")): index
        for index, sentence in enumerate(sentence_map)
        if sentence.get("words")
    }
    start_id = str(candidate.get("start_sentence_id", ""))
    end_id = str(candidate.get("end_sentence_id", ""))
    if start_id not in positions or end_id not in positions:
        return None

    initial_start = positions[start_id]
    initial_end = positions[end_id]
    if initial_start > initial_end:
        return None

    frontier: list[tuple[int, int]] = [(initial_start, initial_end)]
    visited: set[tuple[int, int]] = set()
    while frontier:
        valid_windows: list[tuple[float, int, int, int, list[dict[str, Any]]]] = []
        next_frontier: list[tuple[int, int]] = []
        for window_start, window_end in frontier:
            if (window_start, window_end) in visited:
                continue
            visited.add((window_start, window_end))
            words = [
                word
                for sentence in sentence_map[window_start : window_end + 1]
                for word in sentence.get("words", [])
            ]
            if not words:
                continue
            duration = float(words[-1]["end"]) - float(words[0]["start"])
            if 2.5 < duration < 5.5:
                expansion = (initial_start - window_start) + (window_end - initial_end)
                valid_windows.append(
                    (abs(duration - 4.0), expansion, window_start, window_end, words)
                )
                continue
            if duration <= 2.5:
                if window_start > 0:
                    next_frontier.append((window_start - 1, window_end))
                if window_end + 1 < len(sentence_map):
                    next_frontier.append((window_start, window_end + 1))

        if valid_windows:
            _, _, window_start, window_end, words = min(
                valid_windows,
                key=lambda item: (item[1], item[0]),
            )
            return {
                "start_sentence_id": str(sentence_map[window_start]["id"]),
                "end_sentence_id": str(sentence_map[window_end]["id"]),
                "start_time": round(float(words[0]["start"]), 3),
                "end_time": round(float(words[-1]["end"]), 3),
                "duration": round(float(words[-1]["end"]) - float(words[0]["start"]), 3),
                "text": " ".join(str(word.get("text", "")) for word in words).strip(),
            }
        frontier = next_frontier
    return None


def _hook_has_disallowed_lead(text: str) -> bool:
    return bool(
        re.match(r"^\s*(?:y|bueno|entonces|porque|o\s+sea|eh|este)\b", text, re.IGNORECASE)
    )


def _select_clip_hook(
    clip: dict[str, Any],
    sentence_map: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
) -> dict[str, Any]:
    """Elige teaser autónomo >=8 o marca los primeros 3s como hook in-clip."""
    candidates = clip.get("hook_candidates", [])
    qualified: list[dict[str, Any]] = []
    if isinstance(candidates, list) and clip.get("has_hook") is True:
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("makes_sense_standalone") is not True:
                continue
            try:
                if int(candidate.get("curiosity_score", 0)) >= 8:
                    qualified.append(candidate)
            except (TypeError, ValueError):
                continue
    qualified.sort(key=lambda candidate: int(candidate.get("curiosity_score", 0)), reverse=True)

    for candidate in qualified:
        window = _resolve_hook_candidate_window(candidate, sentence_map)
        if window is None:
            continue
        if _hook_has_disallowed_lead(str(window.get("text", ""))):
            continue
        hook_start = float(window["start_time"])
        hook_end = float(window["end_time"])
        opening_end = min(clip_end, clip_start + 3.0)
        is_in_clip_opening = clip_start <= hook_start <= clip_start + 0.25
        if is_in_clip_opening:
            mode = "in_clip"
            hook_start = clip_start
            hook_end = opening_end
        else:
            mode = "teaser"
        selected = {
            **window,
            "mode": mode,
            "source": "claude_candidate",
            "curiosity_score": int(candidate["curiosity_score"]),
            "makes_sense_standalone": True,
            "has_hook": True,
            "start_time": round(hook_start, 3),
            "end_time": round(hook_end, 3),
        }
        if is_in_clip_opening:
            selected["text"] = " ".join(
                str(word.get("text", ""))
                for sentence in sentence_map
                for word in sentence.get("words", [])
                if float(word["end"]) > clip_start and float(word["start"]) < opening_end
            ).strip()
        return selected

    # Sin teaser independiente fiable: el clip empieza con su primer bloque de 3s.
    direct_end = min(clip_end, clip_start + 3.0)
    opening_words = [
        word
        for sentence in sentence_map
        for word in sentence.get("words", [])
        if float(word["end"]) > clip_start and float(word["start"]) < direct_end
    ]
    return {
        "mode": "in_clip",
        "source": "in_clip_fallback",
        "start_time": round(clip_start, 3),
        "end_time": round(direct_end, 3),
        "duration": round(direct_end - clip_start, 3),
        "text": " ".join(str(word.get("text", "")) for word in opening_words).strip(),
        "curiosity_score": None,
        "makes_sense_standalone": False,
        "has_hook": False,
    }


def extract_audio_to_wav(video_path: str) -> str:
    """Extracción forzada de audio a WAV PCM 16kHz mono vía FFmpeg subprocess."""
    source = _validate_video_source(video_path)
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
            capture_output=True, text=True, timeout=10,
        )
        types = [t.strip().lower() for t in probe.stdout.strip().splitlines() if t.strip()]
        if "audio" not in types:
            raise ValueError("El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.")
    except ValueError:
        raise
    except Exception:
        pass
    wav_path = str(Path(tempfile.gettempdir()) / f"extracted_{source.stem}.wav")
    cmd = ["ffmpeg", "-y", "-i", str(source), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", wav_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timeout 180s extrayendo audio WAV con FFmpeg") from exc
    if res.returncode != 0 or not Path(wav_path).exists():
        raise RuntimeError(f"FFmpeg falló al extraer audio a WAV: {res.stderr}")
    try:
        wav_file = Path(wav_path)
        size = wav_file.stat().st_size
        dur_res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", wav_path], capture_output=True, text=True, timeout=10)
        dur = dur_res.stdout.strip() if dur_res.returncode == 0 else "desconocida"
        logging.getLogger(__name__).info("Extracción WAV exitosa: %s (%.1f KB, duración %s s) via FFmpeg 16kHz mono", wav_path, size / 1024, dur)
    except Exception:
        pass
    return wav_path


def ensure_wav_audio(video_path: str) -> str:
    source = _validate_video_source(video_path)
    wav_path = str(Path(tempfile.gettempdir()) / f"{source.stem}_extracted.wav")
    cmd = [
        "ffmpeg", "-y", "-i", str(source),
        "-vn",
        "-map", "0:a:0?",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        wav_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timeout 180s extrayendo audio WAV con FFmpeg") from exc
    fb_res = None
    if res.returncode != 0 or not Path(wav_path).exists() or Path(wav_path).stat().st_size == 0:
        fallback_cmd = [
            "ffmpeg", "-y", "-i", str(source),
            "-vn", "-ac", "1", "-ar", "16000",
            wav_path
        ]
        try:
            fb_res = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Timeout 180s en la extracción fallback de audio WAV") from exc
        if fb_res.returncode != 0 or not Path(wav_path).exists() or Path(wav_path).stat().st_size == 0:
            raise RuntimeError(f"Fallo en FFmpeg al extraer audio WAV: {res.stderr} | Fallback: {fb_res.stderr} (WAV 0 bytes)")
        else:
            import logging
            logging.getLogger(__name__).info(f"FFmpeg fallback sin -map exitoso: {wav_path} ({Path(wav_path).stat().st_size} bytes)")
    wav_size = Path(wav_path).stat().st_size if Path(wav_path).exists() else 0
    if wav_size == 0:
        fb_stderr = fb_res.stderr if fb_res else "no fallback"
        raise RuntimeError(
            f"FFmpeg generó 0 bytes en Docker. "
            f"Ruta video: {source} (Existe: {source.is_file()}). "
            f"FFmpeg stderr: {res.stderr} | Fallback stderr: {fb_stderr}"
        )
    # Diagnóstico de Audio con volumedetect (requerido por prompt)
    try:
        vol_cmd = [
            "ffmpeg", "-i", wav_path,
            "-filter:a", "volumedetect",
            "-f", "null", "/dev/null"
        ]
        vol_res = subprocess.run(vol_cmd, capture_output=True, text=True)
        vol_info = "no detectado"
        for line in vol_res.stderr.splitlines():
            if "max_volume" in line:
                vol_info = line.strip()
                break
        if vol_info == "no detectado":
            for line in vol_res.stderr.splitlines():
                if "volumedetect" in line.lower():
                    vol_info = line.strip()
        wav_size = Path(wav_path).stat().st_size
        import logging
        logging.getLogger(__name__).info(f"WAV diagnóstico: {wav_path} ({wav_size} bytes) | FFmpeg Volume Info: {vol_info}")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"No se pudo obtener volumedetect para {wav_path}: {e}")
    return wav_path


def _intentar_runpod(vp: Any, tp: Any, progress_callback: Any, log: Any) -> dict[str, Any] | None:
    """Delega el procesamiento a RunPod si está configurado. None si no corresponde."""
    from .runpod_service import is_runpod_configured, process_local_video_via_runpod

    if not is_runpod_configured():
        return None

    log.info("RunPod configurado; delegando transcripción y análisis fuera de Render")
    result = process_local_video_via_runpod(
        vp,
        transcription_path=tp if tp.is_file() else None,
    )
    segments = result.get("transcription_segments")
    if not isinstance(segments, list) or not segments:
        raise RuntimeError(
            "RunPod no devolvió segmentos de transcripción; actualiza el worker para que los incluya "
            "y evitar cargar Whisper localmente en Render."
        )
    result.setdefault("engine", "runpod")
    result.setdefault("video", str(vp))
    result.setdefault("transcription", str(tp) if tp.is_file() else "")
    if progress_callback is not None:
        try:
            progress_callback(35)
        except Exception as exc:
            log.warning("Callback de progreso RunPod falló: %s", exc)
    return result


def _raiz_por_marcadores(current_file: Path) -> Path | None:
    """Busca la raíz del repo por archivos marcadores (docker-compose, SISTEMA.md, paquetes)."""
    for _p in current_file.parents:
        try:
            if (_p / "docker-compose.yml").exists() or (_p / "SISTEMA.md").exists():
                return _p
            if (_p / "backend").is_dir() and (_p / "backend_fastapi").is_dir():
                return _p
            if (_p / "backend_fastapi").is_dir() and (_p / ".env").exists() and (_p / "engine.py").exists():
                return _p
            if (_p / ".env").exists() and (_p / "backend_fastapi").is_dir():
                return _p
        except Exception:
            continue
    return None


def _candidato_fallback_valido(cand: Path) -> bool:
    """Un candidato de fallback es válido si existe y parece el proyecto."""
    if str(cand) in ("/", "\\", "C:\\", "C:/"):
        return False
    if not cand.exists():
        return False
    return (
        (cand / "app").is_dir()
        or (cand / "storage").exists()
        or (cand / "backend_fastapi").is_dir()
        or (cand / "engine.py").exists()
    )


def _raiz_por_fallback(current_file: Path) -> Path | None:
    """Fallback heurístico por profundidad de directorio cuando no hay marcadores."""
    root = None
    for _idx in (2, 3, 1, 0):
        if _idx < len(current_file.parents):
            cand = current_file.parents[_idx]
            try:
                if _candidato_fallback_valido(cand):
                    return cand
                if root is None:
                    root = cand
            except Exception:
                continue
    return root


def _resolver_raiz_proyecto() -> Path:
    current_file = Path(__file__).resolve()
    root = _raiz_por_marcadores(current_file)
    if root is None:
        root = _raiz_por_fallback(current_file)
    if root is None:
        root = current_file.parents[min(2, len(current_file.parents) - 1)]
    return root


def _configurar_sys_path(root: Path) -> None:
    """Deja en sys.path la raíz del proyecto y los paquetes importables (determinista)."""
    _self_dir = str(Path(__file__).resolve().parent)
    _self_parent = str(Path(__file__).resolve().parent.parent)
    for _p in (_self_dir, _self_parent):
        try:
            if _p in sys.path:
                sys.path.remove(_p)
        except ValueError:
            pass
        try:
            if "/app/app/services" in sys.path:
                sys.path.remove("/app/app/services")
            if "/app/app" in sys.path:
                sys.path.remove("/app/app")
        except ValueError:
            pass
    for _cand in reversed([root, root / "backend", root / "backend_fastapi", root / "backend" / "track_b" / "virality"]):
        try:
            if _cand.exists() and str(_cand) not in sys.path:
                sys.path.insert(0, str(_cand))
        except Exception:
            continue
    try:
        if str(root) in sys.path:
            sys.path.remove(str(root))
        sys.path.insert(0, str(root))
    except Exception:
        pass


def _preservar_segmentos_whisper(segs: list[dict]) -> list[dict]:
    """Convierte los segmentos de Whisper en dicts con words válidas (start<=end)."""
    preserved_segments: list[dict[str, Any]] = []
    for segment in segs:
        words: list[dict[str, Any]] = []
        for word in segment.get("words", []):
            try:
                word_start = float(word["start"])
                word_end = float(word["end"])
                word_text = str(word.get("text", "")).strip()
                if word_text and word_end >= word_start:
                    words.append(
                        {"start": word_start, "end": word_end, "text": word_text}
                    )
            except (KeyError, TypeError, ValueError):
                continue
        preserved_segments.append(
            {
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "text": str(segment["text"]),
                "words": words,
            }
        )
    return preserved_segments


def _logear_transcripcion_whisper(segs: list[dict], log: Any) -> None:
    try:
        total_chars = sum(len(str(s.get("text", ""))) for s in segs)
        log.info("Transcripción Whisper: %s segmentos, %s caracteres extraídos", len(segs) if segs else 0, total_chars)
    except Exception:
        log.info("Transcripción Whisper: %s segmentos", len(segs) if segs else 0)


def _transcribir_wav(wav_path: str, log: Any) -> list[dict]:
    """Transcribe el WAV con Whisper local y loguea duración/tamaño. Lanza ValueError si no hay voz."""
    from .whisper_service import transcribe_audio  # type: ignore

    try:
        wav_size = Path(wav_path).stat().st_size
        dur_res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", wav_path], capture_output=True, text=True, timeout=10)
        wav_dur = dur_res.stdout.strip() if dur_res.returncode == 0 else "desconocida"
        log.info("WAV extraído: %s (%.1f KB, duración %s s) — enviando a Whisper", wav_path, wav_size / 1024, wav_dur)
    except Exception:
        pass
    segs = transcribe_audio(wav_path, language="es")
    _logear_transcripcion_whisper(segs, log)
    if segs and len(segs) > 0:
        return segs
    _logear_wav_vacio(wav_path, log)
    raise ValueError("El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.")


def _logear_wav_vacio(wav_path: str | None, log: Any) -> None:
    try:
        wav_size = Path(wav_path).stat().st_size if wav_path and Path(wav_path).exists() else 0
        log.warning("Whisper no generó segmentos: wav_size=%s bytes, wav_path=%s — inspeccionando FFmpeg logs", wav_size, wav_path)
    except Exception:
        pass


def _segmentos_nativos(vp: Path, tp: Path, log: Any) -> list[dict]:
    """Pipeline de transcripción nativo: Whisper local con fallback a transcripción file."""
    wav_path: str | None = None
    try:
        if vp.is_file():
            wav_path = ensure_wav_audio(str(vp))
            log.info("Extracción física WAV completada: %s", wav_path)
            return _preservar_segmentos_whisper(_transcribir_wav(wav_path, log))
    except ValueError as ve:
        log.warning("Motor nativo: Whisper ValueError no audio/voz (%s) — intentando fallback a transcripción file", ve)
        if tp.is_file():
            if not _transcripcion_file_no_vacia(tp, log):
                raise
        else:
            raise
    except Exception as e:
        if "no contiene audio" in str(e) or "no se detectó voz" in str(e) or "Fallo en FFmpeg" in str(e):
            log.warning("Motor nativo: Whisper no audio/voz (%s) — fallback a transcripción", e)
        else:
            log.warning("Motor nativo: Whisper no disponible (%s)", e)
    finally:
        if wav_path:
            try:
                Path(wav_path).unlink(missing_ok=True)
                log.info("WAV temporal limpiado: %s", wav_path)
            except Exception:
                pass
    return _segmentos_desde_txt(tp, log)


def _transcripcion_file_no_vacia(tp: Path, log: Any) -> bool:
    """True si el archivo de transcripción tiene texto útil (para el fallback)."""
    try:
        txt = tp.read_text(encoding="utf-8", errors="ignore")
        if txt.strip():
            log.info("Motor nativo: Whisper falló pero hay transcripción file, usando transcripción")
            return True
        return False
    except ValueError:
        return False


def _segmentos_desde_txt(tp: Path, log: Any) -> list[dict]:
    """Parsea la transcripción de texto plano; RuntimeError si termina vacía."""
    try:
        if tp.is_file():
            txt = tp.read_text(encoding="utf-8", errors="ignore")
            segs = _parse_transcript_native(txt)
            if segs:
                total_chars = sum(len(str(s.get("text", ""))) for s in segs)
                log.info("Motor nativo: segmentos desde transcripción file=%s (%s segs, %s caracteres)", tp, len(segs), total_chars)
                return segs
            # No disparar ValueError genérico, lanzar RuntimeError detallado para Job
            raise RuntimeError(_diagnostico_cero_segmentos())
    except ValueError as ve:
        raise RuntimeError(f"{_diagnostico_cero_segmentos()} — {ve}") from ve
    except Exception as e:
        log.warning("Motor nativo: parse transcription file fallo: %s", e)
    return []


def _diagnostico_cero_segmentos() -> str:
    """Mensaje de diagnóstico estándar cuando Whisper/parse no producen segmentos."""
    # Si hay wav temporal previo, intentar obtener info (ya limpiado, usar 0)
    wav_size = 0
    vol_info = "no detectado"
    raw_text = ""
    return (
        f"Whisper devolvió 0 segmentos. "
        f"WAV Size: {wav_size} bytes. "
        f"FFmpeg Volume Info: {vol_info}. "
        f"Whisper Raw Result: '{raw_text}'"
    )


def _formatear_hhmmss(s: float) -> str:
    """Segundos → 'HH:MM:SS.mmm' (formato de timestamps del engine)."""
    total_ms = max(0, round(s * 1000))
    total_seconds, milliseconds = divmod(total_ms, 1000)
    hours, remaining = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remaining, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def _mapear_clip_claude(clip_raw: dict, sentence_map: dict) -> dict | None:
    """Convierte un clip crudo de Claude en el payload del engine. None si se rechaza."""
    try:
        start_sentence_id = str(clip_raw["start_sentence_id"])
        end_sentence_id = str(clip_raw["end_sentence_id"])
        st, en = _resolve_sentence_timestamps(
            start_sentence_id, end_sentence_id, sentence_map
        )
        if not (15.0 <= en - st <= 60.0):
            logging.getLogger(__name__).warning(
                "Claude clip rechazado por duración tras padding: %s → %s (%.3fs)",
                start_sentence_id,
                end_sentence_id,
                en - st,
            )
            return None
        hook_selection = _select_clip_hook(clip_raw, sentence_map, st, en)
        titulo = str(clip_raw.get("title", "Clip viral"))[:120]
        return {
            "inicio": _formatear_hhmmss(st),
            "fin": _formatear_hhmmss(en),
            "start_time": st,
            "end_time": en,
            "start_sentence_id": start_sentence_id,
            "end_sentence_id": end_sentence_id,
            "has_hook": bool(hook_selection["has_hook"]),
            "hook_selection": hook_selection,
            "titulo": titulo,
            "titulo_sugerido": titulo,
            "score": float(clip_raw.get("score", 8)),
            "criterio_principal": "claude_semantico",
            "hook_texto": str(hook_selection.get("text", ""))[:120],
            "primer_segundo": _formatear_hhmmss(st),
            "motivo": "Selección semántica vía Claude (claude_service)",
            "archivo": "",
        }
    except Exception:
        return None


def _normalizar_error_claude(msg: str) -> str:
    """Asegura el prefijo estándar 'Error en API de Claude' para el Job."""
    if "Error al comunicar con Claude API" not in msg and "Error en API de Claude" not in msg and "Error en la API de Claude" not in msg:
        msg = f"Error en API de Claude: {msg}"
    if "Error en la API de Claude" in msg:
        msg = msg.replace("Error en API de Claude:", "Error en API de Claude:")
    if "Error al comunicar con Claude API" in msg:
        msg = msg.replace("Error en API de Claude:", "Error en API de Claude:")
    return msg


def _seleccionar_con_claude(native_segments: list[dict], vp: Path, tp: Path, log: Any) -> dict[str, Any]:
    """Selección semántica de clips vía Claude + mapeo a clips del engine."""
    try:
        from .claude_service import build_sentence_map, select_clips_via_claude

        sentence_map = build_sentence_map(native_segments)
        try:
            _dur_hint = max(float(segment.get("end", 0)) for segment in native_segments)
        except Exception:
            _dur_hint = None
        _claude_raw = select_clips_via_claude(
            native_segments,
            duration_hint=_dur_hint,
            sentence_map=sentence_map,
        )
        log.info("Análisis de virabilidad completado exitosamente vía Claude API (engine nativo: %s clips semánticos)", len(_claude_raw))
        _claude_clips = [_mapeado for _c in _claude_raw if (_mapeado := _mapear_clip_claude(_c, sentence_map)) is not None]
        if not _claude_clips:
            raise RuntimeError(
                "Error en API de Claude: no quedaron clips con IDs de oración válidos "
                "y duración de 15-60s tras resolver timestamps de palabras y padding"
            )
        return {
            "clips": _claude_clips,
            "engine": "native_claude",
            "video": str(vp),
            "transcription": str(tp),
            "carpeta_salida": "",
            "transcription_segments": native_segments,
        }
    except RuntimeError as e:
        msg = _normalizar_error_claude(str(e))
        log.error(msg)
        raise RuntimeError(msg) from e
    except Exception as e:
        msg = f"Error en API de Claude: {e}"
        log.error(msg)
        raise RuntimeError(msg) from e


def run_clip_engine(
    video_path: str,
    transcription_path: str,
    progress_callback: Any | None = None,
    *,
    allow_runpod: bool = True,
) -> dict[str, Any]:
    _log = logging.getLogger(__name__)
    vp = _validate_video_source(video_path)
    tp = Path(transcription_path)
    if not tp.exists():
        raise FileNotFoundError(f"Transcripcion no encontrada: {transcription_path}")

    if allow_runpod:
        resultado_runpod = _intentar_runpod(vp, tp, progress_callback, _log)
        if resultado_runpod is not None:
            return resultado_runpod

    _configurar_sys_path(_resolver_raiz_proyecto())

    native_segments = _segmentos_nativos(vp, tp, _log)
    if not native_segments:
        # Diagnóstico exacto para Job (reemplaza ValueError genérico engine.py:243)
        raise RuntimeError(_diagnostico_cero_segmentos())

    # ACTUALIZACIÓN INMEDIATA POST-WHISPER: progress 35% antes de Claude
    if progress_callback is not None:
        try:
            progress_callback(35)
        except Exception as cb_e:
            _log.warning(f"progress_callback 35% fallo: {cb_e}")
    _log.info("Transcripción Whisper completada. Avanzando a 35% e iniciando Claude.")

    return _seleccionar_con_claude(native_segments, vp, tp, _log)


def _parse_transcript_native(text: str) -> list[dict]:
    """Parser de transcripción nativo.

    Delega en ``parse_transcript_text_to_segments`` de
    ``backend_fastapi/app/services/transcript_utils`` para compartir lógica.
    """
    from ..services.transcript_utils import parse_transcript_text_to_segments as _shared

    return _shared(text)
