"""Router de Jobs — creacion en background y consulta de estado (Issue 4 + Issue 29 ASS/Hook)."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import sys
import tempfile
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from ..database import SessionLocal
from ..deps import CurrentUser, DbSession
from ..models import Job, JobStatus, Video
from ..schemas import JobResponse

# Logging inmediato (Unbuffered Output) — flush automático a sys.stdout
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
if not logging.getLogger().handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setLevel(logging.INFO)
    _formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    _handler.setFormatter(_formatter)
    logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
# Asegurar flush en cada emit
try:
    for _h in logging.getLogger().handlers:
        _orig_emit = _h.emit
        def _emit_with_flush(record, _h=_h, _orig=_orig_emit):
            _orig(record)
            try:
                _h.flush()
                sys.stdout.flush()
            except Exception:
                pass
        _h.emit = _emit_with_flush  # type: ignore
except Exception:
    pass

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])

# Modo 100% real — ASS/Hook siempre activo, sin flag de simulación (auditoría 2026-09-21)
ENABLE_ASS_HOOK = True

def _resolve_storage_dir() -> Path:
    env_dir = os.getenv("STORAGE_CLIPS_DIR", "").strip()
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    # Docker: /.dockerenv existe
    if Path("/.dockerenv").exists():
        p = Path("/app/storage/clips")
        p.mkdir(parents=True, exist_ok=True)
        return p
    # Local dev: <repo_root>/storage/clips — resolución segura sin parents[3] fijo
    cur = Path(__file__).resolve()
    repo_root = None
    for _p in cur.parents:
        try:
            # Priorizar backend_fastapi/.env para no confundir con el propio módulo
            if (_p / "backend_fastapi").is_dir():
                repo_root = _p
                break
            if (_p / ".env").exists():
                repo_root = _p
                break
            if _p != cur.parent and (_p / "engine.py").exists():
                repo_root = _p
                break
        except Exception:
            continue
    if repo_root is None:
        repo_root = cur.parents[min(3, len(cur.parents) - 1)]
    p = repo_root / "storage" / "clips"
    p.mkdir(parents=True, exist_ok=True)
    return p

STORAGE_CLIPS_DIR = _resolve_storage_dir()


def _set_progress(db, job: Job, value: int) -> None:
    """Actualiza progress 0-100 y hace commit para que polling/SSE lo vea."""
    try:
        v = int(value)
        v = max(0, min(100, v))
        job.progress = v
        db.commit()
        # refresh para asegurar lectura consistente
        try:
            db.refresh(job)
        except Exception:
            pass
        logger.info("[jobs] progress job=%s -> %s%%", job.id, v)
    except Exception as e:
        logger.warning("[jobs] no se pudo actualizar progress job=%s a %s%%: %s", getattr(job, "id", "?"), value, e)
        try:
            db.rollback()
        except Exception:
            pass


def _meets_score_threshold(score: object, threshold: float = 6.0) -> bool:
    """Umbral medio-alto: ≥6.0/10, ≥60/100, ≥0.6/1."""
    if score is None:
        return True  # sin score, preservar
    try:
        v = float(str(score).strip())
        if v <= 1.0:
            return v >= 0.6
        if v <= 10:
            return v >= threshold
        return v >= 60
    except Exception:
        return True


def _parse_time_to_seconds(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return 0.0
    try:
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
        return float(s)
    except Exception:
        return 0.0


def _parse_transcript_text_to_segments(text: str) -> list[dict]:
    """Fallback parser: convierte texto plano o líneas con timestamps a segmentos sintéticos."""
    segs: list[dict] = []
    if not text or not text.strip():
        return segs
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    # Detecta formato "HH:MM:SS - texto" o "MM:SS - texto" o "[start - end] texto"
    re_ts = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*(.+)$")
    re_bracket = re.compile(r"^\[\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*\]\s*(.+)$")
    cursor = 0.0
    for line in lines:
        m = re_bracket.match(line)
        if m:
            try:
                s = float(m.group(1)); e = float(m.group(2)); t = m.group(3).strip()
                if e > s and t:
                    segs.append({"start": s, "end": e, "text": t})
                    cursor = e
                continue
            except Exception:
                pass
        m = re_ts.match(line)
        if m:
            ts_str = m.group(1); t = m.group(2).strip()
            # Convierte ts a segundos
            try:
                parts = ts_str.split(":")
                if len(parts) == 3:
                    s = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    s = int(parts[0]) * 60 + float(parts[1])
                else:
                    s = float(parts[0])
                e = s + 3.0
                if t:
                    segs.append({"start": s, "end": e, "text": t})
                    cursor = e
                continue
            except Exception:
                pass
        # Línea sin timestamp: asigna ventana sintética 3s
        segs.append({"start": cursor, "end": cursor + 3.0, "text": line})
        cursor += 3.0
    return segs


def _load_transcription_segments(video: Video) -> list[dict]:
    """Intenta obtener segmentos con timestamps para ASS/Hook. Prioridad: whisper > archivo transcripción > transcript TEXT."""
    # Validación previa: verificar que el archivo de video existe antes de Whisper/FFmpeg
    try:
        video_path = str(video.filepath or "").strip()
        if not video_path or not Path(video_path).is_file():
            logger.warning("[jobs] video.filepath no existe en disco: %s — se omite Whisper", video_path)
            raise FileNotFoundError(f"Video no encontrado en disco: {video_path}")
    except FileNotFoundError:
        # Propagar como warning, continuar con transcripción de texto
        logger.warning("[jobs] sin video físico, usando solo transcripción de texto para video=%s", video.id)
    # 1) Whisper directo sobre video (más preciso, requiere ffmpeg + faster-whisper)
    try:
        # Verificar existencia física antes de invocar Whisper
        if video.filepath and Path(str(video.filepath)).is_file() and os.path.exists(str(video.filepath)):
            from ..services.whisper_service import transcribe_video

            segs = transcribe_video(video.filepath, language="es")
            if segs and len(segs) > 0:
                logger.info("[jobs] whisper segmentos=%s para video=%s", len(segs), video.id)
                return [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in segs]
            elif segs is not None and len(segs) == 0:
                logger.warning("[jobs] whisper devolvió 0 segmentos para video=%s — fallback a transcripción", video.id)
        else:
            logger.warning("[jobs] video.filepath no accesible, saltando Whisper para video=%s", video.id)
    except Exception as e:
        logger.warning("[jobs] whisper no disponible (%s), fallback a transcripción — %s", e, traceback.format_exc()[:500])

    # 2) Archivo de transcripción asociado
    try:
        p = None
        if video.transcription_filepath:
            p = Path(str(video.transcription_filepath))
            if p.is_file():
                txt = p.read_text(encoding="utf-8", errors="ignore")
                segs = _parse_transcript_text_to_segments(txt)
                if segs:
                    logger.info("[jobs] segmentos desde transcription_filepath=%s (%s segs)", p, len(segs))
                    return segs
    except Exception as e:
        logger.warning("[jobs] parse transcription_filepath fallo: %s", e)

    # 3) Campo transcript en BD
    try:
        if video.transcript and video.transcript.strip():
            segs = _parse_transcript_text_to_segments(video.transcript)
            if segs:
                logger.info("[jobs] segmentos desde Video.transcript (%s segs)", len(segs))
                return segs
    except Exception as e:
        logger.warning("[jobs] parse transcript TEXT fallo: %s", e)

    logger.warning("[jobs] sin segmentos para video=%s", video.id)
    return []


def _detect_hooks_for_segments(segments: list[dict], video: Video) -> list[dict]:
    """Llama a hook_service.detect_hooks y normaliza salida. Retorna lista de HookClip dicts."""
    # Control de arrays/segmentos vacíos: validar antes de acceder a índices
    if not segments:
        logger.warning("[jobs] _detect_hooks_for_segments: segments vacío — no se generan hooks")
        return []
    if len(segments) == 0:
        logger.warning("[jobs] _detect_hooks_for_segments: len(segments)==0 — omitiendo hook detection")
        return []
    try:
        from ..services.hook_service import detect_hooks

        duration = None
        try:
            if video.duration_seconds:
                duration = float(video.duration_seconds)
            elif segments and len(segments) > 0:
                # Acceso seguro con validación de índice
                last = segments[-1] if len(segments) > 0 else None
                if last is not None:
                    duration = float(last.get("end", 0))
        except Exception:
            duration = None
            logger.warning("[jobs] error calculando duration para hooks — %s", traceback.format_exc()[:300])
        hooks = detect_hooks(segments, duration_hint=duration, mock=False)
        logger.info("[jobs] hooks detectados=%s (segmentos=%s)", len(hooks), len(segments))
        return hooks  # list[HookClip] TypedDict
    except Exception as e:
        logger.warning("[jobs] detect_hooks fallo: %s\n%s", e, traceback.format_exc()[:800])
        return []


def _select_hook_for_clip(
    clip_start: float,
    clip_end: float,
    hook_selection: dict | None,
) -> tuple[float, float, dict] | None:
    """Valida el teaser de Claude o selecciona los primeros 3s sin reordenarlos."""
    try:
        clip_start = float(clip_start)
        clip_end = float(clip_end)
        if clip_start < 0 or clip_end <= clip_start:
            raise ValueError(f"Rango de clip inválido [{clip_start},{clip_end}]")
    except (TypeError, ValueError) as exc:
        logger.warning("[jobs] hook: rango de clip inválido: %s", exc)
        return None

    clip_duration = clip_end - clip_start
    if clip_duration < 3.0:
        logger.warning("[jobs] clip demasiado corto para hook in-clip: %.3fs", clip_duration)
        return None

    direct_end = min(clip_start + 3.0, clip_end)
    if isinstance(hook_selection, dict) and hook_selection.get("mode") == "in_clip":
        return (
            clip_start,
            direct_end,
            {
                **hook_selection,
                "start_time": round(clip_start, 3),
                "end_time": round(direct_end, 3),
            },
        )

    if isinstance(hook_selection, dict) and hook_selection.get("mode") == "teaser":
        try:
            hook_start = float(hook_selection["start_time"])
            hook_end = float(hook_selection["end_time"])
            duration = hook_end - hook_start
            score = int(hook_selection.get("curiosity_score", 0))
            standalone = hook_selection.get("makes_sense_standalone") is True
            if 2.5 < duration < 5.5 and score >= 8 and standalone:
                return hook_start, hook_end, hook_selection
            logger.warning(
                "[jobs] teaser rechazado: duration=%.3fs curiosity=%s standalone=%s; se usa apertura in-clip",
                duration,
                score,
                standalone,
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("[jobs] teaser Claude inválido (%s); se usa apertura in-clip", exc)

    # No se extrae ni se concatena otra ventana: el video ya abre con su hook directo.
    return (
        clip_start,
        direct_end,
        {
            "mode": "in_clip",
            "source": "in_clip_fallback",
            "curiosity_score": None,
            "makes_sense_standalone": False,
        },
    )


def _render_clip_with_ass_and_hook(
    video_path: str,
    clip_start: float,
    clip_end: float,
    segments: list[dict],
    hook_sel: tuple[float, float, dict | None] | None,
    job_id: uuid.UUID,
    clip_index: int,
    clip_title: str | None,
) -> tuple[str, dict]:
    """Construye cada clip en orden: recorte → crop 9:16 → subtítulos ASS."""
    # Validación de argumentos FFmpeg antes de ejecutar: evitar código de salida 4 por args inválidos
    try:
        clip_start = float(clip_start)
        clip_end = float(clip_end)
        if not (clip_end > clip_start):
            raise ValueError(f"clip_end ({clip_end}) debe ser > clip_start ({clip_start})")
        if clip_start < 0 or clip_end < 0:
            raise ValueError(f"Tiempos negativos no permitidos: start={clip_start}, end={clip_end}")
        duration = clip_end - clip_start
        if not (2.0 <= duration <= 90.0):
            raise ValueError(f"Duración {duration:.1f}s fuera de rango permitido 2-90s (start={clip_start}, end={clip_end})")
        if hook_sel is not None:
            hs, he, _ = hook_sel
            hs = float(hs); he = float(he)
            hook_meta = hook_sel[2] if isinstance(hook_sel[2], dict) else {}
            hook_mode = str(hook_meta.get("mode", "teaser"))
            if not (2.5 < (he - hs) < 5.5):
                raise ValueError(f"Hook duración {(he-hs):.3f}s debe estar estrictamente entre 2.5 y 5.5s")
            if hook_mode == "in_clip" and not (clip_start <= hs < he <= clip_end):
                raise ValueError(f"Hook in-clip [{hs},{he}] fuera del cuerpo [{clip_start},{clip_end}]")
    except ValueError as ve:
        logger.error("[jobs] _render_clip_with_ass_and_hook args inválidos clip_%s: %s — %s", clip_index, ve, traceback.format_exc()[:500])
        raise
    meta: dict = {"hook_applied": False, "ass_applied": False, "render": "fallback"}
    src = Path(video_path)
    # Verificación de ruta física del video antes de FFmpeg
    if not video_path or not str(video_path).strip():
        raise FileNotFoundError("Ruta de video vacía — verificar video.filepath")
    if not os.path.exists(str(video_path)):
        raise FileNotFoundError(f"Video fuente no encontrado en disco: {video_path} (os.path.exists=False)")
    if not src.is_file():
        raise FileNotFoundError(f"Video fuente no encontrado: {src} (Path.is_file=False)")
    # Verificar tamaño >0 para evitar FFmpeg con archivo corrupto
    try:
        if src.stat().st_size == 0:
            raise RuntimeError(f"Video fuente vacío (0 bytes): {src}")
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.warning("[jobs] advertencia al verificar tamaño video: %s", e)

    # Directorio final persistente
    out_dir = STORAGE_CLIPS_DIR / str(job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    final_name = f"{job_id}_{clip_index:02d}.mp4"
    final_path = out_dir / final_name

    # Preparar ASS
    ass_path_obj: Path | None = None
    use_ass = bool(segments)
    hook_meta = hook_sel[2] if hook_sel and isinstance(hook_sel[2], dict) else {}
    hook_mode = str(hook_meta.get("mode", "teaser"))
    if use_ass:
        try:
            tmp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False)
            tmp_ass.close()
            ass_path_obj = Path(tmp_ass.name)
            if hook_sel and hook_mode == "teaser":
                hs, he, _ = hook_sel
                from ..services.ass_generator import generate_hooked_ass

                # Convertir segments a SubtitleSegment type
                segs_for_ass = [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in segments]
                generate_hooked_ass(segs_for_ass, clip_start, clip_end, hs, he, ass_path_obj, title=clip_title or "clipsai")
                logger.info("[jobs] ASS hooked generado %s (hook %.1f-%.1f)", ass_path_obj, hs, he)
            else:
                # Filtrar segmentos dentro del clip y shiftear a 0
                clipped: list[dict] = []
                for s in segments:
                    try:
                        st = float(s.get("start", 0)); en = float(s.get("end", 0)); txt = str(s.get("text", "")).strip()
                        if not txt or en <= st:
                            continue
                        if en < clip_start or st > clip_end:
                            continue
                        cs = max(st, clip_start); ce = min(en, clip_end)
                        if ce > cs:
                            clipped.append({"start": cs - clip_start, "end": ce - clip_start, "text": txt})
                    except Exception:
                        continue
                if not clipped:
                    # Sin segmentos en ventana: usa todos shifteados proporcionalmente
                    clipped = [{"start": 0, "end": min(3.0, clip_end - clip_start), "text": "CLIPSAI"}]
                from ..services.ass_generator import write_ass_file

                write_ass_file(clipped, ass_path_obj, title=clip_title or "clipsai")
                logger.info("[jobs] ASS simple generado %s (%s segs)", ass_path_obj, len(clipped))
            meta["ass_applied"] = True
        except Exception as e:
            logger.warning("[jobs] ASS generación fallo, continuará sin ASS: %s", e)
            ass_path_obj = None
            meta["ass_applied"] = False

    # Construir el clip intermedio; todos los caminos pasan obligatoriamente por crop 9:16.
    try:
        from ..services.editor import reframe_video
        from ..services.ffmpeg_service import build_hook_clip, burn_subtitles, cut_segment

        with tempfile.TemporaryDirectory(prefix=f"clipsai_render_{clip_index}_") as temp_dir:
            temp_root = Path(temp_dir)
            trimmed_path = temp_root / "trimmed.mp4"
            reframed_path = temp_root / "reframed_9x16.mp4"

            # a) Recortar por timestamps (o componer primero el teaser y el clip).
            if hook_sel and hook_mode == "teaser":
                hs, he, _ = hook_sel
                build_hook_clip(src, clip_start, clip_end, hs, he, trimmed_path)
            else:
                cut_segment(src, clip_start, clip_end, trimmed_path)

            # b) Reencuadrar explícitamente a 9:16. Un error aborta el render, nunca usa 16:9.
            reframe_video(trimmed_path, reframed_path, aspect_ratio="9:16")
            meta["aspect_ratio"] = "9:16"

            # c) Quemar ASS únicamente sobre el archivo que ya fue reencuadrado.
            if ass_path_obj and ass_path_obj.is_file():
                burn_subtitles(reframed_path, ass_path_obj, final_path)
                meta["ass_applied"] = True
            else:
                shutil.move(str(reframed_path), str(final_path))

            meta["hook_applied"] = bool(hook_sel)
            if hook_sel:
                meta["hook_mode"] = hook_mode
            if meta["ass_applied"]:
                meta["render"] = "hook+ass" if hook_sel else "ass"
            else:
                meta["render"] = "hook" if hook_sel else "cut"
            logger.info(
                "[jobs] render %s 9:16 ok -> %s",
                meta["render"],
                final_path,
            )
            return str(final_path), meta
    finally:
        if ass_path_obj:
            try:
                ass_path_obj.unlink(missing_ok=True)
            except Exception:
                pass
    # Fallback si todo falla
    raise RuntimeError("Render falló en todas las ramas")


def _extractmeaningful_title(text: str, max_words: int = 8) -> str:
    """Fallback título dinámico: primeras 5-8 palabras con significado (filtra muletillas)."""
    if not text:
        return "Clip destacado"
    # Stopwords rioplatenses + genéricas
    stop = {"y","o","pero","entonces","eh","ah","bueno","o","sea","este","esta","eso","a","de","la","el","en","que","con","por","para","un","una","al","del","se","me","te","le","lo","si","no","ya","como","muy","más","mas"}
    words = re.sub(r"[^\wáéíóúñÁÉÍÓÚ\s]", " ", text).split()
    # Filtrar stopwords al inicio pero mantener al menos 5 palabras totales
    meaningful = [w for w in words if w.lower() not in stop]
    # Si filtra demasiado, usar palabras originales
    pool = meaningful if len(meaningful) >= 5 else words
    # Tomar 5-8 palabras
    take = min(max_words, max(5, len(pool)))
    # Priorizar hasta 7 palabras si el texto es largo
    if len(pool) > 8:
        take = 7
    title_words = pool[:take]
    title = " ".join(title_words).strip()
    # Capitalizar primera letra
    if title:
        title = title[0].upper() + title[1:]
    # Limitar 60 chars
    if len(title) > 60:
        title = title[:57].rsplit(" ", 1)[0] + "..."
    return title or "Clip destacado"


def _segments_to_fallback_title(segments: list[dict], start: float, end: float) -> str:
    """Busca texto de segmentos dentro de [start,end] y extrae título."""
    texts: list[str] = []
    for s in segments:
        try:
            st = float(s.get("start", 0)); en = float(s.get("end", 0)); txt = str(s.get("text","")).strip()
            if not txt or en < start or st > end:
                continue
            texts.append(txt)
        except Exception:
            continue
    combined = " ".join(texts)[:500] if texts else ""
    return _extractmeaningful_title(combined) if combined else "Clip destacado"


# Auditoría 2026-09-21: _fallback_result deshabilitado — modo 100% real
# Ya no se generan clips sintéticos. Si el engine real falla, el job debe pasar a FAILED
# para que el frontend muestre error real (no estado simulado exitoso).
def _fallback_result(video: Video | None) -> dict:  # type: ignore[no-redef]
    raise RuntimeError("Modo fallback deshabilitado — se requiere procesamiento real (Whisper + FFmpeg + LLM). Verificar video/transcripción y claves LLM.")


def _run_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        # Wrapper global — inicio con log inmediato y flush
        logger.info(f"[JOB {job_id}] Inicio de procesamiento de job.")
        try:
            sys.stdout.flush()
        except Exception:
            pass
        job: Job | None = db.get(Job, job_id)
        if job is None:
            logger.warning("[jobs] _run_job: job %s no encontrado", job_id)
            return
        job.status = JobStatus.PROCESSING.value
        job.progress = 10
        db.commit()
        # Persistencia inmediata ya con commit + flush
        try:
            sys.stdout.flush()
        except Exception:
            pass
        logger.info("[jobs] _run_job iniciado job=%s progress=10%%", job_id)

        video: Video | None = db.get(Video, job.video_id)
        if video is None:
            raise RuntimeError("Video asociado no encontrado")

        # Validaciones previas exhaustivas antes de llamar al engine/Whisper/FFmpeg
        # 1) Verificar filepath del video en disco
        video_path_str = str(video.filepath or "").strip()
        if not video_path_str:
            raise FileNotFoundError("video.filepath está vacío en BD — no se puede procesar")
        if not os.path.exists(video_path_str):
            raise FileNotFoundError(f"Archivo de video no existe en disco: {video_path_str}")
        if not Path(video_path_str).is_file():
            raise FileNotFoundError(f"Video no es archivo regular: {video_path_str}")
        try:
            if Path(video_path_str).stat().st_size == 0:
                raise RuntimeError(f"Video vacío (0 bytes): {video_path_str}")
        except FileNotFoundError:
            raise
        # 2) Verificar transcripción (puede ser filepath o texto en BD)
        transcription_path_str = str(video.transcription_filepath or "").strip()
        has_transcript_text = bool(video.transcript and video.transcript.strip())
        if not transcription_path_str and not has_transcript_text:
            logger.warning("[jobs] video %s sin transcription_filepath ni transcript — intentando Whisper como fallback", video.id)
        elif transcription_path_str and not os.path.exists(transcription_path_str):
            logger.warning("[jobs] transcription_filepath no existe: %s — se usará transcript en BD si existe (len=%s)", transcription_path_str, len(video.transcript or ""))
            if not has_transcript_text:
                raise FileNotFoundError(f"Transcripción no encontrada ni en disco ni en BD: {transcription_path_str}")
            transcription_path_str = ""  # forzar uso de transcript en BD vía fallback interno

        # 3. Diagnóstico Claro de la Transcripción — logs explícitos y persistencia inmediata de progreso
        transcript_data = has_transcript_text
        transcription_filepath = transcription_path_str
        if transcript_data or transcription_filepath:
            logger.info(f"[JOB {job_id}] Transcripción provista por el usuario. Omitiendo Whisper y avanzando a 35%.")
            try:
                cur_diag = db.get(Job, job_id)
                if cur_diag is not None:
                    _set_progress(db, cur_diag, 35)
                    # Actualizar referencia job para siguientes _set_progress
                    job = cur_diag
            except Exception as _diag_e:
                logger.warning(f"[JOB {job_id}] No se pudo persistir progress 35% tras diagnóstico transcripción: {_diag_e}")
        else:
            logger.warning(f"[JOB {job_id}] No se detectó transcripción previa. Ejecutando Whisper como fallback.")
            try:
                cur_diag2 = db.get(Job, job_id)
                if cur_diag2 is not None:
                    _set_progress(db, cur_diag2, 10)
                    job = cur_diag2
            except Exception as _diag_e2:
                logger.warning(f"[JOB {job_id}] No se pudo persistir progress 10% tras diagnóstico transcripción: {_diag_e2}")

        from ..services.engine import run_clip_engine

        # Modo 100% real — sin fallback sintético. Si el engine falla, el job pasa a FAILED con traceback completo.
        logger.info("[jobs] invocando run_clip_engine video=%s transcripcion=%s job=%s", video_path_str, transcription_path_str or "<transcript BD>", job_id)
        # Log de configuración Claude (verificación .env) — verifica API Key leyendo de entorno
        try:
            _claude_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            if not _claude_key:
                # Reintentar via Settings
                try:
                    from ..config import get_settings
                    _claude_key = (get_settings().anthropic_api_key or "").strip()
                except Exception:
                    _claude_key = ""
            if _claude_key:
                logger.info("[jobs] ANTHROPIC_API_KEY presente (prefijo %s...), modelo=%s — se usará Claude para selección semántica", _claude_key[:10], os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))
            else:
                logger.warning("[jobs] ANTHROPIC_API_KEY no configurada — se usará heurística nativa (revisar backend_fastapi/app/config.py y docker-compose.yml)")
        except Exception:
            pass

        # Callback inmediato post-Whisper: actualiza progress=35 ANTES de Claude con commit y log explícito
        def _on_whisper_done(pct: int = 35) -> None:
            try:
                cur = db.get(Job, job_id)
                if cur is not None:
                    _set_progress(db, cur, pct)
                else:
                    _set_progress(db, job, pct)
            except Exception as e:
                logger.warning(f"[jobs] No se pudo actualizar progress a {pct}% para job {job_id}: {e}")
            logger.info(f"[jobs] Job {job_id}: Transcripción Whisper completada. Avanzando a 35% e iniciando Claude.")

        # Resiliencia y timeouts en llamada a Claude (60-90s) — envolver con try/except explícito
        try:
            result = run_clip_engine(video_path_str, transcription_path_str or "", progress_callback=_on_whisper_done)
        except Exception as e:
            err_str = str(e)
            # Verificar si es error de Claude / timeout / API key
            is_claude_err = "Claude" in err_str or "ANTHROPIC" in err_str or "anthropic" in err_str.lower() or "timeout" in err_str.lower() or "Timeout" in err_str
            if is_claude_err:
                logger.error(f"[jobs] Job {job_id}: Error en Claude: {err_str}")
                # Actualizar job a failed con mensaje exacto requerido
                try:
                    fail_job = db.get(Job, job_id)
                    if fail_job is not None:
                        fail_job.status = JobStatus.FAILED.value
                        fail_job.error_message = f"Error en Claude: {err_str}"
                        # Intentar guardar también en result_metadata para observabilidad
                        try:
                            fail_job.result_metadata = {"error": f"Error en Claude: {err_str}", "error_type": type(e).__name__, "engine": "claude_failed"}
                        except Exception:
                            pass
                        db.commit()
                        logger.info(f"[jobs] Job {job_id} marcado como failed por error de Claude (timeout/API key)")
                except Exception as db_e:
                    logger.error(f"[jobs] No se pudo marcar job {job_id} como failed tras error Claude: {db_e}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
            # Re-lanzar para que el handler global también lo capture y haga traceback completo
            raise
        # Log de confirmación cuando Claude responde exitosamente (usa resultado de Claude en lugar de heurística)
        try:
            _engine_type = str(result.get("engine", "")).lower() if isinstance(result, dict) else ""
            if _engine_type in ("native_claude", "real") and result.get("clips"):
                # Verificar si algún clip tiene criterio claude_semantico
                _has_claude = any("claude" in str(c.get("criterio_principal", "")).lower() or "claude" in str(c.get("engine", "")).lower() for c in result.get("clips", []) if isinstance(c, dict))
                if _has_claude or _engine_type == "native_claude":
                    logger.info("Análisis de virabilidad completado exitosamente vía Claude API (job %s, %s clips semánticos)", job_id, len(result.get("clips", [])))
                elif _engine_type == "native" and os.getenv("ANTHROPIC_API_KEY", "").strip():
                    logger.info("Análisis de virabilidad completado exitosamente vía Claude API (job %s, engine=%s)", job_id, _engine_type)
        except Exception:
            pass

        clips_payload = []
        cached_transcription_segments: list[dict] = []
        if isinstance(result, dict):
            clips_payload = result.get("clips") or result.get("result") or result.get("clips_generated") or []
            raw_segments = result.pop("transcription_segments", None)
            if isinstance(raw_segments, list):
                for raw_segment in raw_segments:
                    if not isinstance(raw_segment, dict):
                        continue
                    try:
                        start_time = float(raw_segment["start"])
                        end_time = float(raw_segment["end"])
                        text = str(raw_segment.get("text", "")).strip()
                        if text and end_time > start_time:
                            cached_transcription_segments.append(
                                {"start": start_time, "end": end_time, "text": text}
                            )
                    except (KeyError, TypeError, ValueError):
                        continue
        elif isinstance(result, list):
            clips_payload = result

        if not clips_payload:
            # Control de arrays vacíos: mensaje descriptivo en lugar de error críptico o "4"
            # Esto evita que el frontend reciba solo "4" y permite diagnóstico real
            segs_dbg = len(segments) if 'segments' in locals() else "N/A (antes de ASS/Hook)"
            raise RuntimeError(
                f"El engine real no devolvió clips (0 clips). "
                f"Posibles causas: transcripción vacía o sin segmentos detectables, "
                f"Whisper no generó segmentos (verificar audio/idioma), "
                f"LLM sin respuesta o filtrado por score. "
                f"Debug: clips_payload vacío, job={job_id}, video={video.id}, segments_detectados={segs_dbg}. "
                f"Revisar logs whisper/LLM y verificar que el video tenga audio nítido y transcripción válida."
            )

        # Filtrado por score medio-alto sin límite máximo (prompt: eliminar [:6]/max_clips)
        # Preservar start/end de Whisper; solo descartar por score < umbral
        _initial = len(clips_payload)
        _filtered = [c for c in clips_payload if _meets_score_threshold(c.get("score"))]
        if len(_filtered) < _initial:
            logger.info("[jobs] filtrado por score ≥6.0/60: %s → %s clips (descartados %s por score bajo)", _initial, len(_filtered), _initial - len(_filtered))
        clips_payload = _filtered
        # Sin truncamiento [:6] / max_clips — se devuelven TODOS los válidos (3, 8, 15)

        # --- Issue #29: preparar segmentos y hooks para ASS + teaser — flujo obligatorio Claude sin fallback heurístico
        segments: list[dict] = []
        if ENABLE_ASS_HOOK:
            # Reusar segmentos de la pasada Whisper del engine; el WAV temporal ya se limpió.
            # Si el engine no los entregó, extraer/transcribir de nuevo con los timeouts adecuados.
            segments = cached_transcription_segments or _load_transcription_segments(video)
            if not segments:
                raise RuntimeError("Error en API de Claude: no se detectaron segmentos de transcripción para ASS/Hook — verificar Whisper/transcripción")
            if cached_transcription_segments:
                logger.info("[jobs] reutilizando %s segmentos Whisper en memoria para ASS/Hook", len(segments))
            logger.info("[jobs] pipeline ASS/Hook enabled: segments=%s; hook candidates provistos por Claude engine", len(segments))
            # 65% Finalización análisis hooks (Claude)
            try:
                _set_progress(db, job, 65)
            except Exception:
                pass

        from ..models import Clip

        clips_to_create = []
        render_stats = {"total": len(clips_payload), "hook+ass": 0, "ass": 0, "hook": 0, "cut": 0, "fallback": 0}
        for idx, item in enumerate(clips_payload):
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("titulo") or item.get("titulo_sugerido") or item.get("name") or "Clip"
            start_raw = item.get("start_time", item.get("inicio", item.get("start", 0)))
            end_raw = item.get("end_time", item.get("fin", item.get("end", 10)))
            start = _parse_time_to_seconds(start_raw)
            end = _parse_time_to_seconds(end_raw)
            if end <= start:
                end = start + 30.0
            # Clamp ffmpeg limits: 2-90s, si fuera de rango, ajusta a 30s fallback
            if not (2.0 <= (end - start) <= 90.0):
                logger.warning("[jobs] clip %s duracion %.1f fuera de rango, clamp a 30s", idx, end - start)
                end = start + 30.0
            score = item.get("score")
            try:
                score_val = float(score) if score is not None else None
            except Exception:
                score_val = None
            tags = item.get("tags")
            if tags is not None and not isinstance(tags, list):
                tags = [str(tags)]
            # Base tags dict para guardar metadata hook/ass
            base_tags: dict = {}
            if isinstance(tags, list) and tags:
                base_tags["_raw_tags"] = tags
            # Selección hook para este clip
            hook_sel = None
            if ENABLE_ASS_HOOK and segments:
                try:
                    hook_sel = _select_hook_for_clip(
                        float(start), float(end), item.get("hook_selection")
                    )
                except Exception as e:
                    logger.warning("[jobs] hook select fallo clip %s: %s", idx, e)
                    hook_sel = None

            # Render FFmpeg + ASS
            storage = item.get("storage_path") or item.get("file_path") or item.get("path") or ""
            if not isinstance(storage, str):
                storage = str(storage) if storage is not None else ""
            storage = storage.strip()
            render_meta: dict = {}
            final_storage = storage
            # Corte y renderizado físico SIEMPRE — eliminar Modo Simulado (prompt: ejecutar FFmpeg con start/end Whisper)
            video_exists = False
            try:
                video_exists = Path(video.filepath).is_file()
            except Exception:
                video_exists = False

            if video_exists:
                try:
                    # Pasar segments/hook solo si ASS/Hook habilitado, pero siempre renderizar físico
                    segs_for_render = segments if ENABLE_ASS_HOOK else []
                    hook_for_render = hook_sel if ENABLE_ASS_HOOK else None
                    final_path, render_meta = _render_clip_with_ass_and_hook(
                        video.filepath, float(start), float(end), segs_for_render, hook_for_render, job.id, idx, str(title)[:255] if title else None
                    )
                    final_storage = final_path
                    # Actualizar stats
                    r = render_meta.get("render", "fallback")
                    if r == "hook+ass":
                        render_stats["hook+ass"] += 1
                    elif r == "ass":
                        render_stats["ass"] += 1
                    elif r == "hook":
                        render_stats["hook"] += 1
                    elif r in ("cut", "cut_no_ffmpeg_check"):
                        render_stats["cut"] += 1
                    else:
                        render_stats["fallback"] += 1
                    # Enriquecer tags con hook/ass
                    if render_meta.get("hook_applied"):
                        hs, he, hmeta = hook_sel if hook_sel else (None, None, None)
                        base_tags["hook"] = {"start": hs, "end": he, "applied": True}
                        if hmeta:
                            base_tags["hook"]["title"] = hmeta.get("text", "")[:120]
                            base_tags["hook"]["curiosity_score"] = hmeta.get("curiosity_score")
                            base_tags["hook"]["standalone"] = hmeta.get("makes_sense_standalone", False)
                            base_tags["hook"]["mode"] = hmeta.get("mode", "teaser")
                        base_tags["hook"]["source"] = hmeta.get("source", "in_clip_fallback") if hmeta else "in_clip_fallback"
                    if render_meta.get("ass_applied"):
                        base_tags["ass"] = {"applied": True, "segments": len(segments)}
                    base_tags["_render"] = r
                    # Permitir que el engine archive su path temporal no persista
                    logger.info("[jobs] clip %s render %s -> %s", idx, r, final_storage)
                    # Actualizar progreso incrementalmente durante renderizado (65% -> 90%)
                    try:
                        total = len(clips_payload) or 1
                        prog = 65 + int(25 * (idx + 1) / total)
                        prog = min(90, prog)
                        # Necesitamos refrescar job desde db para actualizar progress
                        _cur = db.get(Job, job_id)
                        if _cur is not None:
                            _set_progress(db, _cur, prog)
                            # re-asignar job para siguientes iteraciones
                            job = _cur
                    except Exception:
                        pass
                except Exception as e:
                    tb = traceback.format_exc()
                    logger.warning("[jobs] render fallo clip %s (%s), fallback storage original: %s\n%s", idx, e, storage, tb)
                    render_stats["fallback"] += 1
                    # Mensaje descriptivo completo en lugar de solo str(e) que podía ser "4"
                    err_detail = f"{type(e).__name__}: {e}\n{tb[:1500]}"
                    base_tags["_render_error"] = err_detail[:800]
                    base_tags["_render"] = "failed_fallback"
                    # Modo real: propagates error — no se deja storage vacío simulado
                    raise RuntimeError(f"Render FFmpeg falló para clip {idx} [{type(e).__name__}: {e}] — ver traceback en logs") from e
            else:
                # Video origen no existe — error real, sin fallback de prueba
                raise FileNotFoundError(f"Video origen no encontrado en disco: {video.filepath} — no se puede renderizar clip {idx}")

            # Validación física obligatoria: el archivo recortado debe existir en storage
            if not final_storage or not Path(final_storage).is_file() or Path(final_storage).stat().st_size == 0:
                raise RuntimeError(f"Clip {idx} no generó archivo .mp4 físico en storage: {final_storage}")

            # Merge tags originales + base_tags
            merged_tags: dict | list | None = None
            if base_tags:
                merged_tags = base_tags
                # Si había tags lista, preservarla bajo _raw
            else:
                merged_tags = tags

            clips_to_create.append(
                Clip(
                    video_id=video.id,
                    job_id=job.id,
                    title=str(title)[:255] if title else None,
                    start_time=float(start),
                    end_time=float(end),
                    score=score_val,
                    tags=merged_tags,
                    storage_path=final_storage or "",
                    status="ready",
                )
            )

        # 90% Recorte y renderizado completado
        try:
            _cur2 = db.get(Job, job_id)
            if _cur2 is not None:
                _set_progress(db, _cur2, 90)
        except Exception:
            pass

        # Guardar stats de render en result_metadata para observabilidad
        try:
            result["_render_stats"] = render_stats
            result["_ass_hook_enabled"] = ENABLE_ASS_HOOK
            if segments:
                result["_segments_count"] = len(segments)
            rendered_hook_count = render_stats["hook"] + render_stats["hook+ass"]
            if rendered_hook_count:
                result["_hooks_count"] = rendered_hook_count
        except Exception:
            pass

        refreshed: Job | None = db.get(Job, job_id)
        if refreshed is None:
            return
        # Validación final: todos los clips deben tener storage_path físico real
        for c in clips_to_create:
            if not c.storage_path or not Path(c.storage_path).is_file():
                raise RuntimeError(f"Clip '{c.title}' no generó archivo físico: {c.storage_path}")

        refreshed.result_metadata = result
        refreshed.status = JobStatus.COMPLETED.value
        refreshed.progress = 100
        refreshed.error_message = None
        for c in clips_to_create:
            db.add(c)
        db.commit()
        try:
            sys.stdout.flush()
        except Exception:
            pass
        logger.info("Job %s completado 100%% real (%s clips físicos: %s)", job_id, len(clips_to_create), render_stats)
    except Exception as e:
        # Decorador / Wrapper Global — captura NINGÚN processing silencioso
        error_trace = traceback.format_exc()
        logger.error(f"[JOB {job_id}] ERROR CRÍTICO EN PIPELINE:\n{error_trace}")
        try:
            sys.stdout.flush()
        except Exception:
            pass
        # Guardar en Base de Datos de inmediato — spec: status failed con Details
        try:
            _spec_fail = db.get(Job, job_id)
            if _spec_fail is not None:
                _spec_fail.status = JobStatus.FAILED.value
                _spec_fail.error_message = f"{str(e)} | Details: {error_trace[-300:]}"
                try:
                    _spec_fail.result_metadata = {"error": f"{str(e)} | Details: {error_trace[-300:]}", "error_type": type(e).__name__, "traceback": error_trace[:3000], "engine": "real", "failed": True}
                except Exception:
                    pass
                db.commit()
                try:
                    sys.stdout.flush()
                except Exception:
                    pass
                logger.info(f"[JOB {job_id}] Guardado en BD estado failed tras error crítico")
        except Exception as _spec_db_e:
            logger.error(f"[JOB {job_id}] No se pudo guardar error crítico en BD: {_spec_db_e}")
            try:
                db.rollback()
            except Exception:
                pass
        # FIX legado: Capturar e imprimir Traceback completo en lugar de solo str(e) que almacenó "4"
        exc = e
        tb_full = error_trace
        logger.exception("Fallo irrecuperable job=%s — modo 100%% real sin fallback\nTraceback:\n%s", job_id, tb_full)
        # Mensaje descriptivo humano + tipo de excepción + traceback abreviado (no solo "4")
        # Si str(exc) es vacío o un solo carácter como "4", usar tb para diagnóstico
        raw_msg = str(exc).strip()
        if not raw_msg or len(raw_msg) <= 4 or raw_msg == "4":
            # Caso Error 4: str(e) era "4" por excepción mal formateada o código FFmpeg — expandir a descriptivo
            descriptive = (
                f"{type(exc).__name__}: {raw_msg or 'error sin mensaje'} — "
                f"Fallo en pipeline de Job {job_id}. "
                f"Posibles causas: segments vacío (Whisper sin audio), "
                f"filepath no existe, o FFmpeg args inválidos. "
                f"Traceback:\n{tb_full[:1500]}"
            )
        else:
            descriptive = f"{type(exc).__name__}: {raw_msg}\n{tb_full[:1200]}"
        # También detectar causas comunes para mensajes más útiles
        if "segments" in tb_full and ("IndexError" in tb_full or "list index out of range" in tb_full):
            descriptive = (
                "No se detectaron segmentos de audio suficientes en el video — "
                f"Whisper devolvió lista vacía o muy corta. Job {job_id}: {type(exc).__name__}: {raw_msg}\n{tb_full[:1200]}"
            )
        elif "FileNotFoundError" in tb_full or "No such file" in tb_full:
            descriptive = descriptive  # ya es descriptivo con path
        # Guardar en BD con mensaje descriptivo (no solo "4") — preservar spec si ya guardado
        try:
            failed2: Job | None = db.get(Job, job_id)
            if failed2 is not None:
                # Si ya tiene el formato spec con Details:, no sobrescribir error_message principal
                if failed2.error_message and "Details:" in failed2.error_message and "| Details:" in failed2.error_message:
                    # Ya guardado por spec, solo asegurar result_metadata detallado
                    try:
                        if not failed2.result_metadata or "descriptive" not in str(failed2.result_metadata):
                            failed2.result_metadata = {
                                "error": descriptive[:2000],
                                "error_type": type(exc).__name__,
                                "traceback": tb_full[:3000],
                                "engine": "real",
                                "failed": True,
                                "spec_error": f"{str(exc)} | Details: {error_trace[-300:]}",
                            }
                            db.commit()
                    except Exception:
                        pass
                    logger.info("[jobs] job %s ya marcado FAILED por spec, se preserva mensaje spec", job_id)
                else:
                    failed2.status = JobStatus.FAILED.value
                    failed2.error_message = descriptive[:2000]
                try:
                    failed2.result_metadata = {
                        "error": descriptive[:2000],
                        "error_type": type(exc).__name__,
                        "traceback": tb_full[:3000],
                        "engine": "real",
                        "failed": True,
                    }
                except Exception:
                    # Fallback mínimo si result_metadata falla
                    try:
                        failed2.result_metadata = {"error": descriptive[:2000], "engine": "real", "failed": True}
                    except Exception:
                        pass
                db.commit()
                logger.info("[jobs] job %s marcado FAILED con mensaje descriptivo (%s chars)", job_id, len(descriptive))
        except Exception as db_exc:
            logger.exception("[jobs] error al marcar FAILED job=%s: %s", job_id, db_exc)
            try:
                db.rollback()
            except Exception:
                pass
    finally:
        db.close()


# Wrapper Global para BackgroundTasks — spec exacta (async)
async def run_job_safely(job_id: str) -> None:
    """Wrapper async con try...except global para BackgroundTasks (spec)."""
    try:
        logger.info(f"[JOB {job_id}] Inicio de procesamiento de job.")
        try:
            sys.stdout.flush()
        except Exception:
            pass
        # Delegar a pipeline síncrono existente (convierte str a UUID si necesario)
        try:
            jid = uuid.UUID(str(job_id)) if isinstance(job_id, str) else job_id  # type: ignore
        except Exception:
            jid = job_id  # type: ignore
        _run_job(jid)  # type: ignore
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"[JOB {job_id}] ERROR CRÍTICO EN PIPELINE:\n{error_trace}")
        try:
            sys.stdout.flush()
        except Exception:
            pass
        # Guardar en BD de inmediato — sync version de update_job_status_in_db
        try:
            db2 = SessionLocal()
            try:
                fj = db2.get(Job, jid if 'jid' in locals() else job_id)  # type: ignore
                if fj is not None:
                    fj.status = JobStatus.FAILED.value
                    fj.error_message = f"{str(e)} | Details: {error_trace[-300:]}"
                    try:
                        fj.result_metadata = {"error": f"{str(e)} | Details: {error_trace[-300:]}", "traceback": error_trace[:3000], "engine": "real", "failed": True}
                    except Exception:
                        pass
                    db2.commit()
                    try:
                        sys.stdout.flush()
                    except Exception:
                        pass
            finally:
                db2.close()
        except Exception as _db_e:
            logger.error(f"[JOB {job_id}] No se pudo guardar error en BD desde wrapper: {_db_e}")


# Wrapper Global para BackgroundTasks — spec exacta con asyncio.to_thread para desbloquear event loop
async def run_job_safely(job_id: str) -> None:
    """Wrapper async con try...except global para BackgroundTasks (spec) + desbloqueo event loop."""
    try:
        logger.info(f"[JOB {job_id}] Inicio de procesamiento de job.")
        try:
            sys.stdout.flush()
        except Exception:
            pass
        # Desbloquear Event Loop: pipeline síncrono pesado (Whisper/PyTorch/FFmpeg) en hilo secundario
        try:
            jid = uuid.UUID(str(job_id)) if isinstance(job_id, str) else job_id  # type: ignore
        except Exception:
            jid = job_id  # type: ignore
        await asyncio.to_thread(_run_job, jid)  # type: ignore
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"[JOB {job_id}] ERROR CRÍTICO EN PIPELINE:\n{error_trace}")
        try:
            sys.stdout.flush()
        except Exception:
            pass
        # Guardar en BD de inmediato — sync version de update_job_status_in_db
        try:
            from ..database import SessionLocal as _SessionLocal2
            from ..models import Job as _Job2, JobStatus as _JobStatus2

            db2 = _SessionLocal2()
            try:
                fj = db2.get(_Job2, jid if 'jid' in locals() else job_id)  # type: ignore
                if fj is not None:
                    fj.status = _JobStatus2.FAILED.value
                    fj.error_message = f"{str(e)} | Details: {error_trace[-300:]}"
                    try:
                        fj.result_metadata = {"error": f"{str(e)} | Details: {error_trace[-300:]}", "error_type": type(e).__name__, "traceback": error_trace[:3000], "engine": "real", "failed": True}
                    except Exception:
                        pass
                    db2.commit()
                    try:
                        sys.stdout.flush()
                    except Exception:
                        pass
            finally:
                db2.close()
        except Exception as _db_e:
            logger.error(f"[JOB {job_id}] No se pudo guardar error en BD desde wrapper: {_db_e}")


@router.post(
    "/videos/{video_id}/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear Job de procesamiento para un video",
)
def create_job(
    video_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> Job:
    video: Video | None = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video no encontrado")
    if video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para este video")

    job = Job(
        video_id=video.id,
        status=JobStatus.PENDING.value,
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Usar wrapper global async con captura de errores y logging unbuffered
    try:
        background_tasks.add_task(run_job_safely, str(job.id))  # type: ignore
    except Exception:
        # Fallback sync si BackgroundTasks no soporta async en esta versión
        background_tasks.add_task(_run_job, job.id)

    return job


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="Consultar estado de un Job",
)
def get_job(
    job_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Job:
    job: Job | None = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")

    video: Video | None = db.get(Video, job.video_id)
    if video is None or video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")

    return job
