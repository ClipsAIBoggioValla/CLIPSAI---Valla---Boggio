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


def _oracion_mapeable(sentence: dict[str, Any]) -> bool:
    """True si la oración tiene id y lista de palabras no vacía."""
    sentence_id = str(sentence.get("id", ""))
    sentence_words = sentence.get("words")
    return bool(sentence_id) and isinstance(sentence_words, list) and bool(sentence_words)


def _posiciones_de_oraciones(
    sentence_map: list[dict[str, Any]],
) -> tuple[dict[str, tuple[int, int]], list[dict[str, Any]]]:
    """Índices (primero, último) de cada oración sobre la lista plana de palabras."""
    positions: dict[str, tuple[int, int]] = {}
    all_words: list[dict[str, Any]] = []
    for sentence in sentence_map:
        if not _oracion_mapeable(sentence):
            continue
        first_word_idx = len(all_words)
        all_words.extend(sentence.get("words"))
        positions[str(sentence.get("id", ""))] = (first_word_idx, len(all_words) - 1)
    return positions, all_words


def _extender_a_puntuacion_final(
    all_words: list[dict[str, Any]], last_idx: int
) -> dict[str, Any]:
    """Avanza hasta la primera palabra que termina con puntuación fuerte."""
    last_word = all_words[last_idx]
    if not _ends_with_strong_punctuation(str(last_word.get("text", ""))):
        for next_idx in range(last_idx + 1, len(all_words)):
            last_word = all_words[next_idx]
            if _ends_with_strong_punctuation(str(last_word.get("text", ""))):
                break
    return last_word


def _resolve_sentence_timestamps(
    start_sentence_id: str,
    end_sentence_id: str,
    sentence_map: list[dict[str, Any]],
) -> tuple[float, float]:
    """Resuelve IDs de oraciones a límites de palabra, expansión y padding exactos."""
    positions, all_words = _posiciones_de_oraciones(sentence_map)

    if start_sentence_id not in positions or end_sentence_id not in positions:
        raise ValueError(f"start/end sentence id desconocido: {start_sentence_id} / {end_sentence_id}")

    first_idx = positions[start_sentence_id][0]
    last_idx = positions[end_sentence_id][1]
    if first_idx > last_idx:
        raise ValueError(
            f"Rango de oraciones invertido: {start_sentence_id} → {end_sentence_id}"
        )

    first_word = all_words[first_idx]
    last_word = _extender_a_puntuacion_final(all_words, last_idx)

    start_time = max(0.0, float(first_word["start"]) - 0.15)
    end_time = float(last_word["end"]) + 0.35
    if end_time <= start_time:
        raise ValueError(
            f"Rango de palabras inválido para {start_sentence_id} → {end_sentence_id}"
        )
    return round(start_time, 3), round(end_time, 3)


def _posiciones_oraciones_con_words(sentence_map: list[dict[str, Any]]) -> dict[str, int]:
    """Índice de cada oración que trae palabras, por id."""
    return {
        str(sentence.get("id", "")): index
        for index, sentence in enumerate(sentence_map)
        if sentence.get("words")
    }


def _palabras_de_ventana(
    sentence_map: list[dict[str, Any]], window_start: int, window_end: int
) -> list[dict[str, Any]]:
    """Palabras planas de las oraciones dentro de la ventana."""
    return [
        word
        for sentence in sentence_map[window_start : window_end + 1]
        for word in sentence.get("words", [])
    ]


def _expansiones_ventana_corta(
    window_start: int, window_end: int, sentence_map: list[dict[str, Any]]
) -> list[tuple[int, int]]:
    """Ventanas vecinas cuando la duración quedó por debajo del mínimo."""
    expansiones: list[tuple[int, int]] = []
    if window_start > 0:
        expansiones.append((window_start - 1, window_end))
    if window_end + 1 < len(sentence_map):
        expansiones.append((window_start, window_end + 1))
    return expansiones


def _ventanas_vecinas(
    window_start: int,
    window_end: int,
    sentence_map: list[dict[str, Any]],
    duration: float,
) -> list[tuple[int, int]]:
    """Vecinas a explorar si la ventana es corta; [] en otro caso."""
    if duration <= 2.5:
        return _expansiones_ventana_corta(window_start, window_end, sentence_map)
    return []


def _evaluar_ventana(
    window_start: int,
    window_end: int,
    sentence_map: list[dict[str, Any]],
    initial_start: int,
    initial_end: int,
) -> tuple[tuple[float, int, int, int, list[dict[str, Any]]] | None, list[tuple[int, int]]]:
    """Evalúa una ventana: devuelve (registro_válido|None, vecinas)."""
    words = _palabras_de_ventana(sentence_map, window_start, window_end)
    if not words:
        return None, []
    duration = float(words[-1]["end"]) - float(words[0]["start"])
    if 2.5 < duration < 5.5:
        expansion = (initial_start - window_start) + (window_end - initial_end)
        return (abs(duration - 4.0), expansion, window_start, window_end, words), []
    return None, _ventanas_vecinas(window_start, window_end, sentence_map, duration)


def _ventana_frontier(
    frontier: list[tuple[int, int]],
    visited: set[tuple[int, int]],
    sentence_map: list[dict[str, Any]],
    initial_start: int,
    initial_end: int,
) -> tuple[list[tuple[float, int, int, int, list[dict[str, Any]]]], list[tuple[int, int]]]:
    """Recorre un nivel del frontier; devuelve (válidas, siguiente_frontier)."""
    valid_windows: list[tuple[float, int, int, int, list[dict[str, Any]]]] = []
    next_frontier: list[tuple[int, int]] = []
    for window_start, window_end in frontier:
        if (window_start, window_end) in visited:
            continue
        visited.add((window_start, window_end))
        registro, vecinas = _evaluar_ventana(
            window_start, window_end, sentence_map, initial_start, initial_end
        )
        if registro is not None:
            valid_windows.append(registro)
        next_frontier.extend(vecinas)
    return valid_windows, next_frontier


def _ventana_elegida(
    valid_windows: list[tuple[float, int, int, int, list[dict[str, Any]]]],
    sentence_map: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Elije la mejor ventana válida y construye el resultado."""
    if not valid_windows:
        return None
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


def _ids_en_positions(start_id: str, end_id: str, positions: dict[str, int]) -> bool:
    """True si ambos ids de oración existen en el mapa de posiciones."""
    return start_id in positions and end_id in positions


def _resolve_hook_candidate_window(
    candidate: dict[str, Any],
    sentence_map: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Resuelve un candidato a oraciones completas y lo ajusta a 2.5–5.5s."""
    positions = _posiciones_oraciones_con_words(sentence_map)
    start_id = str(candidate.get("start_sentence_id", ""))
    end_id = str(candidate.get("end_sentence_id", ""))
    if not _ids_en_positions(start_id, end_id, positions):
        return None

    initial_start = positions[start_id]
    initial_end = positions[end_id]
    if initial_start > initial_end:
        return None

    frontier: list[tuple[int, int]] = [(initial_start, initial_end)]
    visited: set[tuple[int, int]] = set()
    while frontier:
        valid_windows, next_frontier = _ventana_frontier(
            frontier, visited, sentence_map, initial_start, initial_end
        )
        ventana = _ventana_elegida(valid_windows, sentence_map)
        if ventana is not None:
            return ventana
        frontier = next_frontier
    return None


def _hook_has_disallowed_lead(text: str) -> bool:
    return bool(
        re.match(r"^\s*(?:y|bueno|entonces|porque|o\s+sea|eh|este)\b", text, re.IGNORECASE)
    )


def _candidato_descartable(candidate: Any) -> bool:
    """True si el candidato no es dict standalone."""
    return not isinstance(candidate, dict) or candidate.get("makes_sense_standalone") is not True


def _agregar_si_califica(qualified: list[dict[str, Any]], candidate: Any) -> None:
    """Agrega el candidato si es dict standalone con score >= 8."""
    if _candidato_descartable(candidate):
        return
    try:
        if int(candidate.get("curiosity_score", 0)) >= 8:
            qualified.append(candidate)
    except (TypeError, ValueError):
        pass


def _candidatos_calificados(clip: dict[str, Any]) -> list[dict[str, Any]]:
    """Candidatos standalone con curiosity_score >= 8, ordenados por score."""
    candidates = clip.get("hook_candidates", [])
    qualified: list[dict[str, Any]] = []
    if isinstance(candidates, list) and clip.get("has_hook") is True:
        for candidate in candidates:
            _agregar_si_califica(qualified, candidate)
    qualified.sort(key=lambda candidate: int(candidate.get("curiosity_score", 0)), reverse=True)
    return qualified


def _palabra_solapa_rango(word: dict[str, Any], inicio: float, fin: float) -> bool:
    """True si la palabra cruza la ventana [inicio, fin)."""
    return float(word["end"]) > inicio and float(word["start"]) < fin


def _palabras_en_rango(
    sentence_map: list[dict[str, Any]], inicio: float, fin: float
) -> list[dict[str, Any]]:
    """Palabras planas que cruzan la ventana [inicio, fin)."""
    return [
        word
        for sentence in sentence_map
        for word in sentence.get("words", [])
        if _palabra_solapa_rango(word, inicio, fin)
    ]


def _texto_palabras(words: list[dict[str, Any]]) -> str:
    """Une los textos de las palabras (para el hook in-clip)."""
    return " ".join(str(word.get("text", "")) for word in words).strip()


def _hook_en_apertura(hook_start: float, clip_start: float) -> bool:
    """True si el hook cae dentro de los primeros 0.25s del clip."""
    return clip_start <= hook_start <= clip_start + 0.25


def _hook_desde_candidato(
    candidate: dict[str, Any],
    window: dict[str, Any],
    sentence_map: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
) -> dict[str, Any] | None:
    """Construye el hook de un candidato válido; None si el texto tiene lead prohibido."""
    if _hook_has_disallowed_lead(str(window.get("text", ""))):
        return None
    hook_start = float(window["start_time"])
    hook_end = float(window["end_time"])
    opening_end = min(clip_end, clip_start + 3.0)
    is_in_clip_opening = _hook_en_apertura(hook_start, clip_start)
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
        selected["text"] = _texto_palabras(
            _palabras_en_rango(sentence_map, clip_start, opening_end)
        )
    return selected


def _select_clip_hook(
    clip: dict[str, Any],
    sentence_map: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
) -> dict[str, Any]:
    """Elige teaser autónomo >=8 o marca los primeros 3s como hook in-clip."""
    for candidate in _candidatos_calificados(clip):
        window = _resolve_hook_candidate_window(candidate, sentence_map)
        if window is None:
            continue
        selected = _hook_desde_candidato(
            candidate, window, sentence_map, clip_start, clip_end
        )
        if selected is not None:
            return selected

    # Sin teaser independiente fiable: el clip empieza con su primer bloque de 3s.
    direct_end = min(clip_end, clip_start + 3.0)
    opening_words = _palabras_en_rango(sentence_map, clip_start, direct_end)
    return {
        "mode": "in_clip",
        "source": "in_clip_fallback",
        "start_time": round(clip_start, 3),
        "end_time": round(direct_end, 3),
        "duration": round(direct_end - clip_start, 3),
        "text": _texto_palabras(opening_words),
        "curiosity_score": None,
        "makes_sense_standalone": False,
        "has_hook": False,
    }


def _tipos_de_stream_ffprobe(source: Path) -> list[str]:
    """Tipos de stream del video según ffprobe (lista vacía si falla)."""
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return []
    return [t.strip().lower() for t in probe.stdout.strip().splitlines() if t.strip()]


def _verificar_audio_ffprobe(source: Path) -> None:
    """Lanza ValueError si el video no contiene pista de audio; ignora fallos de ffprobe."""
    try:
        if "audio" not in _tipos_de_stream_ffprobe(source):
            raise ValueError("El video subido no contiene audio o no se detectó voz interpretable para generar subtítulos.")
    except ValueError:
        raise
    except Exception:
        pass


def _ffmpeg_cmd_wav(source: Path, wav_path: str) -> list[str]:
    """Comando ffmpeg estándar de extracción WAV PCM 16kHz mono."""
    return ["ffmpeg", "-y", "-i", str(source), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", wav_path]


def _registrar_extraccion_wav(wav_path: str) -> None:
    """Loguea tamaño y duración del WAV extraído (silencio ante errores)."""
    try:
        wav_file = Path(wav_path)
        size = wav_file.stat().st_size
        dur_res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", wav_path], capture_output=True, text=True, timeout=10)
        dur = dur_res.stdout.strip() if dur_res.returncode == 0 else "desconocida"
        logging.getLogger(__name__).info("Extracción WAV exitosa: %s (%.1f KB, duración %s s) via FFmpeg 16kHz mono", wav_path, size / 1024, dur)
    except Exception:
        pass


def extract_audio_to_wav(video_path: str) -> str:
    """Extracción forzada de audio a WAV PCM 16kHz mono vía FFmpeg subprocess."""
    source = _validate_video_source(video_path)
    _verificar_audio_ffprobe(source)
    wav_path = str(Path(tempfile.gettempdir()) / f"extracted_{source.stem}.wav")
    cmd = _ffmpeg_cmd_wav(source, wav_path)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timeout 180s extrayendo audio WAV con FFmpeg") from exc
    if res.returncode != 0 or not Path(wav_path).exists():
        raise RuntimeError(f"FFmpeg falló al extraer audio a WAV: {res.stderr}")
    _registrar_extraccion_wav(wav_path)
    return wav_path


def _comando_ffmpeg_map(source: Path, wav_path: str) -> list[str]:
    """Comando ffmpeg con -map 0:a:0? para extracción WAV."""
    return [
        "ffmpeg", "-y", "-i", str(source),
        "-vn",
        "-map", "0:a:0?",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        wav_path
    ]


def _comando_ffmpeg_fallback(source: Path, wav_path: str) -> list[str]:
    """Comando ffmpeg de respaldo sin -map para extracción WAV."""
    return ["ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", wav_path]


def _wav_invalido(wav_path: str) -> bool:
    """True si el WAV no existe o quedó en 0 bytes."""
    return not Path(wav_path).exists() or Path(wav_path).stat().st_size == 0


def _extraer_wav_primario(source: Path, wav_path: str):
    """Ejecuta ffmpeg con -map; lanza RuntimeError ante timeout."""
    try:
        return subprocess.run(_comando_ffmpeg_map(source, wav_path), capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timeout 180s extrayendo audio WAV con FFmpeg") from exc


def _extraer_wav_fallback(source: Path, wav_path: str, stderr: str):
    """Reintenta la extracción sin -map; lanza RuntimeError si falla. Devuelve el resultado."""
    try:
        fb_res = subprocess.run(_comando_ffmpeg_fallback(source, wav_path), capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timeout 180s en la extracción fallback de audio WAV") from exc
    if _wav_invalido(wav_path):
        raise RuntimeError(f"Fallo en FFmpeg al extraer audio WAV: {stderr} | Fallback: {fb_res.stderr} (WAV 0 bytes)")
    import logging
    logging.getLogger(__name__).info(f"FFmpeg fallback sin -map exitoso: {wav_path} ({Path(wav_path).stat().st_size} bytes)")
    return fb_res


def _validar_wav_final(wav_path: str, source: Path, res, fb_res) -> None:
    """Lanza RuntimeError si el WAV quedó en 0 bytes."""
    wav_size = Path(wav_path).stat().st_size if Path(wav_path).exists() else 0
    if wav_size == 0:
        fb_stderr = fb_res.stderr if fb_res else "no fallback"
        raise RuntimeError(
            f"FFmpeg generó 0 bytes en Docker. "
            f"Ruta video: {source} (Existe: {source.is_file()}). "
            f"FFmpeg stderr: {res.stderr} | Fallback stderr: {fb_stderr}"
        )


def _linea_con_clave(stderr: str, clave: str, lower: bool = False) -> str:
    """Primera línea cuyo texto contiene la clave; '' si no hay."""
    for line in stderr.splitlines():
        texto = line.lower() if lower else line
        if clave in texto:
            return line.strip()
    return ""


def _max_volume_detectado(stderr: str) -> str:
    """Primera línea con max_volume; si no, la de volumedetect; si no, 'no detectado'."""
    vol_info = _linea_con_clave(stderr, "max_volume")
    if vol_info:
        return vol_info
    return _linea_con_clave(stderr, "volumedetect", lower=True) or "no detectado"


def _diagnostico_volumen(wav_path: str) -> None:
    """Diagnóstico de Audio con volumedetect (requerido por prompt)."""
    try:
        vol_res = subprocess.run(
            [
                "ffmpeg", "-i", wav_path,
                "-filter:a", "volumedetect",
                "-f", "null", "/dev/null"
            ],
            capture_output=True, text=True
        )
        vol_info = _max_volume_detectado(vol_res.stderr)
        wav_size = Path(wav_path).stat().st_size
        import logging
        logging.getLogger(__name__).info(f"WAV diagnóstico: {wav_path} ({wav_size} bytes) | FFmpeg Volume Info: {vol_info}")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"No se pudo obtener volumedetect para {wav_path}: {e}")


def ensure_wav_audio(video_path: str) -> str:
    """Asegura un WAV PCM 16kHz mono; reintenta sin -map si falla."""
    source = _validate_video_source(video_path)
    wav_path = str(Path(tempfile.gettempdir()) / f"{source.stem}_extracted.wav")
    res = _extraer_wav_primario(source, wav_path)
    fb_res = None
    if res.returncode != 0 or _wav_invalido(wav_path):
        fb_res = _extraer_wav_fallback(source, wav_path, res.stderr)
    _validar_wav_final(wav_path, source, res, fb_res)
    # Diagnóstico de Audio con volumedetect (requerido por prompt)
    _diagnostico_volumen(wav_path)
    return wav_path


def _validar_segmentos_runpod(result: dict[str, Any]) -> None:
    """Lanza RuntimeError si RunPod no devolvió segmentos de transcripción."""
    segments = result.get("transcription_segments")
    if not isinstance(segments, list) or not segments:
        raise RuntimeError(
            "RunPod no devolvió segmentos de transcripción; actualiza el worker para que los incluya "
            "y evitar cargar Whisper localmente en Render."
        )


def _defaults_runpod(result: dict[str, Any], vp: Any, tp: Any) -> dict[str, Any]:
    """Rellena defaults engine/video/transcription del resultado RunPod."""
    result.setdefault("engine", "runpod")
    result.setdefault("video", str(vp))
    result.setdefault("transcription", str(tp) if tp.is_file() else "")
    return result


def _notificar_progreso_runpod(progress_callback: Any, log: Any) -> None:
    """Notifica 35% de progreso si hay callback (ignora fallos)."""
    if progress_callback is not None:
        try:
            progress_callback(35)
        except Exception as exc:
            log.warning("Callback de progreso RunPod falló: %s", exc)


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
    _validar_segmentos_runpod(result)
    result = _defaults_runpod(result, vp, tp)
    _notificar_progreso_runpod(progress_callback, log)
    return result


def _es_raiz_por_archivos(_p: Path) -> bool:
    """Marcadores sueltos: docker-compose.yml o SISTEMA.md."""
    return (_p / "docker-compose.yml").exists() or (_p / "SISTEMA.md").exists()


def _es_raiz_doble_backend(_p: Path) -> bool:
    """backend/ y backend_fastapi/ juntos indican raíz."""
    return (_p / "backend").is_dir() and (_p / "backend_fastapi").is_dir()


def _es_raiz_backend_env_engine(_p: Path) -> bool:
    """backend_fastapi/ + .env + engine.py a la vez."""
    return (_p / "backend_fastapi").is_dir() and (_p / ".env").exists() and (_p / "engine.py").exists()


def _es_raiz_env_backend(_p: Path) -> bool:
    """.env + backend_fastapi/ a la vez."""
    return (_p / ".env").exists() and (_p / "backend_fastapi").is_dir()


def _es_raiz_marcadores(_p: Path) -> bool:
    """True si el directorio parece la raíz del repo por archivos marcadores."""
    return (
        _es_raiz_por_archivos(_p)
        or _es_raiz_doble_backend(_p)
        or _es_raiz_backend_env_engine(_p)
        or _es_raiz_env_backend(_p)
    )


def _raiz_por_marcadores(current_file: Path) -> Path | None:
    """Busca la raíz del repo por archivos marcadores (docker-compose, SISTEMA.md, paquetes)."""
    for _p in current_file.parents:
        try:
            if _es_raiz_marcadores(_p):
                return _p
        except Exception:
            continue
    return None


def _candidato_parece_proyecto(cand: Path) -> bool:
    """True si el candidato contiene artefactos del proyecto."""
    return (
        (cand / "app").is_dir()
        or (cand / "storage").exists()
        or (cand / "backend_fastapi").is_dir()
        or (cand / "engine.py").exists()
    )


def _candidato_fallback_valido(cand: Path) -> bool:
    """Un candidato de fallback es válido si existe y parece el proyecto."""
    if str(cand) in ("/", "\\", "C:\\", "C:/"):
        return False
    if not cand.exists():
        return False
    return _candidato_parece_proyecto(cand)


def _candidato_fallback_o_base(cand: Path, root: Path | None) -> tuple[bool, Path | None]:
    """Devuelve (True, cand) si es raíz válida; (False, base) en otro caso."""
    try:
        if _candidato_fallback_valido(cand):
            return True, cand
        if root is None:
            root = cand
    except Exception:
        pass
    return False, root


def _raiz_por_fallback(current_file: Path) -> Path | None:
    """Fallback heurístico por profundidad de directorio cuando no hay marcadores."""
    root = None
    for _idx in (2, 3, 1, 0):
        if _idx < len(current_file.parents):
            encontrado, root = _candidato_fallback_o_base(current_file.parents[_idx], root)
            if encontrado:
                return root
    return root


def _resolver_raiz_proyecto() -> Path:
    current_file = Path(__file__).resolve()
    root = _raiz_por_marcadores(current_file)
    if root is None:
        root = _raiz_por_fallback(current_file)
    if root is None:
        root = current_file.parents[min(2, len(current_file.parents) - 1)]
    return root


def _quitar_de_sys_path(ruta: str) -> None:
    """Elimina una ruta de sys.path si está presente (ignora ValueError)."""
    try:
        if ruta in sys.path:
            sys.path.remove(ruta)
    except ValueError:
        pass


def _limpiar_sys_path_propio() -> None:
    """Saca de sys.path los directorios propios y rutas de app en Docker."""
    _self_dir = str(Path(__file__).resolve().parent)
    _self_parent = str(Path(__file__).resolve().parent.parent)
    for _p in (_self_dir, _self_parent):
        _quitar_de_sys_path(_p)
    _quitar_de_sys_path("/app/app/services")
    _quitar_de_sys_path("/app/app")


def _candidato_insertable(_cand: Path) -> bool:
    """True si el candidato existe y aún no está en sys.path."""
    return _cand.exists() and str(_cand) not in sys.path


def _insertar_candidatos_sys_path(root: Path) -> None:
    """Inserta al frente de sys.path los candidatos de paquetes existentes."""
    for _cand in reversed([root, root / "backend", root / "backend_fastapi", root / "backend" / "track_b" / "virality"]):
        try:
            if _candidato_insertable(_cand):
                sys.path.insert(0, str(_cand))
        except Exception:
            continue


def _forzar_raiz_sys_path(root: Path) -> None:
    """Coloca la raíz del proyecto al frente de sys.path (idempotente)."""
    try:
        if str(root) in sys.path:
            sys.path.remove(str(root))
        sys.path.insert(0, str(root))
    except Exception:
        pass


def _configurar_sys_path(root: Path) -> None:
    """Deja en sys.path la raíz del proyecto y los paquetes importables (determinista)."""
    _limpiar_sys_path_propio()
    _insertar_candidatos_sys_path(root)
    _forzar_raiz_sys_path(root)


def _palabra_whisper_valida(word: dict) -> dict[str, Any] | None:
    """Dict {start,end,text} de la palabra si es usable; None si no."""
    try:
        word_start = float(word["start"])
        word_end = float(word["end"])
        word_text = str(word.get("text", "")).strip()
        if word_text and word_end >= word_start:
            return {"start": word_start, "end": word_end, "text": word_text}
    except (KeyError, TypeError, ValueError):
        pass
    return None


def _words_de_segmento(segment: dict) -> list[dict[str, Any]]:
    """Palabras válidas del segmento en orden."""
    words: list[dict[str, Any]] = []
    for word in segment.get("words", []):
        word_data = _palabra_whisper_valida(word)
        if word_data is not None:
            words.append(word_data)
    return words


def _preservar_segmentos_whisper(segs: list[dict]) -> list[dict]:
    """Convierte los segmentos de Whisper en dicts con words válidas (start<=end)."""
    preserved_segments: list[dict[str, Any]] = []
    for segment in segs:
        preserved_segments.append(
            {
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "text": str(segment["text"]),
                "words": _words_de_segmento(segment),
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


def _limpiar_wav_temporal(wav_path: str | None, log: Any) -> None:
    """Elimina el WAV temporal si se creó (ignora fallos)."""
    if not wav_path:
        return
    try:
        Path(wav_path).unlink(missing_ok=True)
        log.info("WAV temporal limpiado: %s", wav_path)
    except Exception:
        pass


def _es_error_no_audio(e: Exception) -> bool:
    """True si el error indica falta de audio/voz o fallo de FFmpeg."""
    texto = str(e)
    return (
        "no contiene audio" in texto
        or "no se detectó voz" in texto
        or "Fallo en FFmpeg" in texto
    )


def _logear_error_whisper(e: Exception, log: Any) -> None:
    """Loguea el fallo de Whisper distinguiendo falta de audio/voz."""
    if _es_error_no_audio(e):
        log.warning("Motor nativo: Whisper no audio/voz (%s) — fallback a transcripción", e)
    else:
        log.warning("Motor nativo: Whisper no disponible (%s)", e)


def _relanzar_value_error_sin_transcripcion(tp: Path, log: Any, ve: ValueError) -> None:
    """Relanza el error si no hay transcripción file con texto útil."""
    if tp.is_file():
        if not _transcripcion_file_no_vacia(tp, log):
            raise ve
    else:
        raise ve


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
        _relanzar_value_error_sin_transcripcion(tp, log, ve)
    except Exception as e:
        _logear_error_whisper(e, log)
    finally:
        _limpiar_wav_temporal(wav_path, log)
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


def _segmentos_logueados(tp: Path, log: Any) -> list[dict]:
    """Segmentos desde txt; RuntimeError de diagnóstico si no hay ninguno."""
    txt = tp.read_text(encoding="utf-8", errors="ignore")
    segs = _parse_transcript_native(txt)
    if segs:
        total_chars = sum(len(str(s.get("text", ""))) for s in segs)
        log.info("Motor nativo: segmentos desde transcripción file=%s (%s segs, %s caracteres)", tp, len(segs), total_chars)
        return segs
    # No disparar ValueError genérico, lanzar RuntimeError detallado para Job
    raise RuntimeError(_diagnostico_cero_segmentos())


def _segmentos_desde_txt(tp: Path, log: Any) -> list[dict]:
    """Parsea la transcripción de texto plano; RuntimeError si termina vacía."""
    try:
        if tp.is_file():
            return _segmentos_logueados(tp, log)
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
            "emojis": clip_raw.get("emojis", []),
            "titulo": titulo,
            "titulo_sugerido": titulo,
            "social_copy": clip_raw.get("social_copy"),
            "score": float(clip_raw.get("score", 8)),
            "criterio_principal": "claude_semantico",
            "hook_texto": str(hook_selection.get("text", ""))[:120],
            "primer_segundo": _formatear_hhmmss(st),
            "motivo": "Selección semántica vía Claude (claude_service)",
            "archivo": "",
        }
    except Exception:
        return None


def _necesita_prefijo_claude(msg: str) -> bool:
    """True si el mensaje aún no trae el prefijo estándar de Claude."""
    return (
        "Error al comunicar con Claude API" not in msg
        and "Error en API de Claude" not in msg
        and "Error en la API de Claude" not in msg
    )


def _normalizar_error_claude(msg: str) -> str:
    """Asegura el prefijo estándar 'Error en API de Claude' para el Job."""
    if _necesita_prefijo_claude(msg):
        msg = f"Error en API de Claude: {msg}"
    if "Error en la API de Claude" in msg:
        msg = msg.replace("Error en API de Claude:", "Error en API de Claude:")
    if "Error al comunicar con Claude API" in msg:
        msg = msg.replace("Error en API de Claude:", "Error en API de Claude:")
    return msg


def _duracion_hint_segmentos(native_segments: list[dict]) -> float | None:
    """Duración máxima de los segmentos; None si no se puede calcular."""
    try:
        return max(float(segment.get("end", 0)) for segment in native_segments)
    except Exception:
        return None


def _mapear_clips_claude(claude_raw: list[dict], sentence_map: dict) -> list[dict]:
    """Clips crudos de Claude mapeados (descarta los rechazados)."""
    return [_mapeado for _c in claude_raw if (_mapeado := _mapear_clip_claude(_c, sentence_map)) is not None]


def _payload_claude(
    native_segments: list[dict], vp: Path, tp: Path, _claude_clips: list[dict]
) -> dict[str, Any]:
    """Payload del engine para clips seleccionados con Claude."""
    return {
        "clips": _claude_clips,
        "engine": "native_claude",
        "video": str(vp),
        "transcription": str(tp),
        "carpeta_salida": "",
        "transcription_segments": native_segments,
    }


def _seleccionar_con_claude(native_segments: list[dict], vp: Path, tp: Path, log: Any) -> dict[str, Any]:
    """Selección semántica de clips vía Claude + mapeo a clips del engine."""
    try:
        from .claude_service import build_sentence_map, select_clips_via_claude

        sentence_map = build_sentence_map(native_segments)
        _dur_hint = _duracion_hint_segmentos(native_segments)
        _claude_raw = select_clips_via_claude(
            native_segments,
            duration_hint=_dur_hint,
            sentence_map=sentence_map,
        )
        log.info("Análisis de virabilidad completado exitosamente vía Claude API (engine nativo: %s clips semánticos)", len(_claude_raw))
        _claude_clips = _mapear_clips_claude(_claude_raw, sentence_map)
        if not _claude_clips:
            raise RuntimeError(
                "Error en API de Claude: no quedaron clips con IDs de oración válidos "
                "y duración de 15-60s tras resolver timestamps de palabras y padding"
            )
        return _payload_claude(native_segments, vp, tp, _claude_clips)
    except RuntimeError as e:
        msg = _normalizar_error_claude(str(e))
        log.error(msg)
        raise RuntimeError(msg) from e
    except Exception as e:
        msg = f"Error en API de Claude: {e}"
        log.error(msg)
        raise RuntimeError(msg) from e


def _validar_fuentes(video_path: str, transcription_path: str) -> tuple[Path, Path]:
    """Valida el video y la existencia de la transcripción."""
    vp = _validate_video_source(video_path)
    tp = Path(transcription_path)
    if not tp.exists():
        raise FileNotFoundError(f"Transcripcion no encontrada: {transcription_path}")
    return vp, tp


def _notificar_progreso_35(progress_callback: Any | None, log: Any) -> None:
    """Notifica 35% tras Whisper (ignora fallos del callback)."""
    if progress_callback is not None:
        try:
            progress_callback(35)
        except Exception as cb_e:
            log.warning(f"progress_callback 35% fallo: {cb_e}")


def run_clip_engine(
    video_path: str,
    transcription_path: str,
    progress_callback: Any | None = None,
    *,
    allow_runpod: bool = True,
) -> dict[str, Any]:
    _log = logging.getLogger(__name__)
    vp, tp = _validar_fuentes(video_path, transcription_path)

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
    _notificar_progreso_35(progress_callback, _log)
    _log.info("Transcripción Whisper completada. Avanzando a 35% e iniciando Claude.")

    return _seleccionar_con_claude(native_segments, vp, tp, _log)


def _parse_transcript_native(text: str) -> list[dict]:
    """Parser de transcripción nativo.

    Delega en ``parse_transcript_text_to_segments`` de
    ``backend_fastapi/app/services/transcript_utils`` para compartir lógica.
    """
    from ..services.transcript_utils import parse_transcript_text_to_segments as _shared

    return _shared(text)
