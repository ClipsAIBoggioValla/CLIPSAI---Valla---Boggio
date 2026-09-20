"""Router de Jobs — creacion en background y consulta de estado (Issue 4 + Issue 29 ASS/Hook)."""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from ..database import SessionLocal
from ..deps import CurrentUser, DbSession
from ..models import Job, JobStatus, Video
from ..schemas import JobResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])

ENABLE_ASS_HOOK = os.getenv("ENABLE_ASS_HOOK", "true").lower() not in ("0", "false", "no")

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
    # Local dev: <repo_root>/storage/clips
    repo_root = Path(__file__).resolve().parents[3]
    p = repo_root / "storage" / "clips"
    p.mkdir(parents=True, exist_ok=True)
    return p

STORAGE_CLIPS_DIR = _resolve_storage_dir()


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
    # 1) Whisper directo sobre video (más preciso, requiere ffmpeg + faster-whisper)
    try:
        from ..services.whisper_service import transcribe_video

        segs = transcribe_video(video.filepath, language="es")
        if segs:
            logger.info("[jobs] whisper segmentos=%s para video=%s", len(segs), video.id)
            return [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in segs]
    except Exception as e:
        logger.warning("[jobs] whisper no disponible (%s), fallback a transcripción", e)

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
    if not segments:
        return []
    try:
        from ..services.hook_service import detect_hooks

        duration = None
        try:
            if video.duration_seconds:
                duration = float(video.duration_seconds)
            elif segments:
                duration = float(segments[-1].get("end", 0))
        except Exception:
            duration = None
        hooks = detect_hooks(segments, duration_hint=duration, mock=False)
        logger.info("[jobs] hooks detectados=%s", len(hooks))
        return hooks  # list[HookClip] TypedDict
    except Exception as e:
        logger.warning("[jobs] detect_hooks fallo: %s", e)
        return []


def _select_hook_for_clip(clip_start: float, clip_end: float, hooks: list[dict], segments: list[dict]) -> tuple[float, float, dict | None] | None:
    """Busca hook contenido en [clip_start, clip_end]. Retorna (hook_start, hook_end, hook_meta) o None. Fallback sintético centrado."""
    clip_dur = clip_end - clip_start
    # Hook solo si clip 15-90s (ffmpeg permite 15-60 pero flexibilizamos a 90)
    if not (15.0 <= clip_dur <= 90.0):
        return None

    # 1) Buscar hook LLM contenido
    best = None
    for h in hooks:
        try:
            # h es HookClip: {start_time, end_time, hook:{start_time,end_time,duration}}
            hk = h.get("hook") or {}
            hs = float(hk.get("start_time", hk.get("start", 0)))
            he = float(hk.get("end_time", hk.get("end", 0)))
            if hs <= 0 and he <= 0:
                continue
            if clip_start <= hs < he <= clip_end and 3.0 <= (he - hs) <= 6.0:
                # Preferir mayor viral_score
                score = int(h.get("viral_score", 0))
                if best is None or score > best[2].get("viral_score", 0):
                    best = (hs, he, h)
        except Exception:
            continue
    if best:
        return best

    # 2) Fallback sintético: ventana central 5s alineada a segmento si posible
    hook_dur = 5.0
    if clip_dur < hook_dur + 2:
        return None
    center = (clip_start + clip_end) / 2
    hs = center - hook_dur / 2
    he = hs + hook_dur
    # Alinear a segmento más cercano para que hook_text coincida con frase real
    if segments:
        try:
            # Busca segmento cuyo start esté ~2s de hs
            closest = min(segments, key=lambda s: abs(float(s.get("start", 0)) - hs))
            cs = float(closest.get("start", hs))
            # Ajusta hs para que empiece en cs si cae dentro del clip
            if clip_start <= cs <= clip_end - hook_dur:
                hs = cs
                he = hs + hook_dur
                if he > clip_end:
                    he = clip_end
                    hs = he - hook_dur
        except Exception:
            pass
    # Clamp
    if hs < clip_start:
        hs = clip_start
        he = hs + hook_dur
    if he > clip_end:
        he = clip_end
        hs = he - hook_dur
    if he - hs < 3.0 or hs < clip_start or he > clip_end:
        return None
    return (round(hs, 2), round(he, 2), None)


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
    """Renderiza clip: cut/concat + ASS burn. Retorna (final_path, meta). Degrada gracefully."""
    meta: dict = {"hook_applied": False, "ass_applied": False, "render": "fallback"}
    src = Path(video_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video fuente no encontrado: {src}")

    # Directorio final persistente
    out_dir = STORAGE_CLIPS_DIR / str(job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    final_name = f"{job_id}_{clip_index:02d}.mp4"
    final_path = out_dir / final_name

    # Si ffmpeg no disponible, fallback a cut simple sin ASS/hook
    has_ffmpeg = True
    try:
        from ..services.ffmpeg_service import _check_ffmpeg

        _check_ffmpeg()
    except Exception as e:
        logger.warning("[jobs] ffmpeg no disponible, clip sin render: %s", e)
        has_ffmpeg = False

    if not has_ffmpeg:
        # Intenta al menos cut sin ASS
        try:
            from ..services.ffmpeg_service import cut_segment

            cut_segment(src, clip_start, clip_end, final_path)
            meta["render"] = "cut_no_ffmpeg_check"
            return str(final_path), meta
        except Exception:
            raise

    # Preparar ASS
    ass_path_obj: Path | None = None
    use_ass = bool(segments)
    if use_ass:
        try:
            tmp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False)
            tmp_ass.close()
            ass_path_obj = Path(tmp_ass.name)
            if hook_sel:
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

    # Render FFmpeg
    try:
        if hook_sel and ass_path_obj and ass_path_obj.is_file():
            # Hook + ASS: build hook concat temp luego burn
            hs, he, _ = hook_sel
            tmp_concat = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            tmp_concat.close()
            tmp_concat_path = Path(tmp_concat.name)
            try:
                from ..services.ffmpeg_service import build_hook_clip, burn_subtitles

                build_hook_clip(src, clip_start, clip_end, hs, he, tmp_concat_path)
                burn_subtitles(tmp_concat_path, ass_path_obj, final_path)
                meta["hook_applied"] = True
                meta["render"] = "hook+ass"
                logger.info("[jobs] render hook+ass ok -> %s", final_path)
                return str(final_path), meta
            finally:
                try:
                    tmp_concat_path.unlink(missing_ok=True)
                except Exception:
                    pass
        elif hook_sel:
            # Hook sin ASS
            hs, he, _ = hook_sel
            from ..services.ffmpeg_service import build_hook_clip

            build_hook_clip(src, clip_start, clip_end, hs, he, final_path)
            meta["hook_applied"] = True
            meta["render"] = "hook"
            logger.info("[jobs] render hook ok -> %s", final_path)
            return str(final_path), meta
        elif ass_path_obj and ass_path_obj.is_file():
            # ASS sin hook: cut luego burn
            tmp_cut = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            tmp_cut.close()
            tmp_cut_path = Path(tmp_cut.name)
            try:
                from ..services.ffmpeg_service import burn_subtitles, cut_segment

                cut_segment(src, clip_start, clip_end, tmp_cut_path)
                burn_subtitles(tmp_cut_path, ass_path_obj, final_path)
                meta["render"] = "ass"
                logger.info("[jobs] render ass ok -> %s", final_path)
                return str(final_path), meta
            finally:
                try:
                    tmp_cut_path.unlink(missing_ok=True)
                except Exception:
                    pass
        else:
            # Solo cut
            from ..services.ffmpeg_service import cut_segment

            cut_segment(src, clip_start, clip_end, final_path)
            meta["render"] = "cut"
            logger.info("[jobs] render cut ok -> %s", final_path)
            return str(final_path), meta
    finally:
        if ass_path_obj:
            try:
                ass_path_obj.unlink(missing_ok=True)
            except Exception:
                pass
    # Fallback si todo falla
    raise RuntimeError("Render falló en todas las ramas")


def _fallback_result(video: Video | None) -> dict:
    preview = ""
    if video is not None:
        try:
            if video.transcript:
                preview = str(video.transcript)[:120]
            elif video.transcription_filepath:
                import pathlib

                p = pathlib.Path(str(video.transcription_filepath))
                if p.is_file():
                    preview = p.read_text(encoding="utf-8", errors="ignore")[:120]
        except Exception:
            preview = ""
    return {
        "clips": [
            {"inicio": "00:00:10", "fin": "00:00:45", "titulo": "Clip destacado 1 (fallback)", "score": 7.5, "transcript_preview": preview},
            {"inicio": "00:01:00", "fin": "00:01:35", "titulo": "Clip destacado 2 (fallback)", "score": 7.0},
        ],
        "engine": "fallback",
        "fallback": True,
        "reason": "LLM no disponible, clip fallback automático",
    }


def _run_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job: Job | None = db.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.PROCESSING.value
        db.commit()

        video: Video | None = db.get(Video, job.video_id)
        if video is None:
            raise RuntimeError("Video asociado no encontrado")

        from ..services.engine import run_clip_engine

        try:
            result = run_clip_engine(video.filepath, video.transcription_filepath or "")
        except Exception:
            logger.exception("run_clip_engine fallo job=%s, aplicando fallback para no dejar FAILED", job_id)
            result = _fallback_result(video)
            result["fallback_error"] = "LLM fallo, fallback aplicado"

        clips_payload = []
        if isinstance(result, dict):
            clips_payload = result.get("clips") or result.get("result") or result.get("clips_generated") or []
        elif isinstance(result, list):
            clips_payload = result

        if not clips_payload:
            logger.warning("run_clip_engine devolvio 0 clips job=%s, usando fallback", job_id)
            result = _fallback_result(video)
            clips_payload = result.get("clips", [])

        # --- Issue #29: preparar segmentos y hooks para ASS + teaser ---
        segments: list[dict] = []
        hooks: list[dict] = []
        if ENABLE_ASS_HOOK:
            try:
                segments = _load_transcription_segments(video)
                if segments:
                    hooks = _detect_hooks_for_segments(segments, video)
                logger.info("[jobs] pipeline ASS/Hook enabled: segments=%s hooks=%s", len(segments), len(hooks))
            except Exception as e:
                logger.warning("[jobs] ASS/Hook prep fallo, continuará sin render: %s", e)
                segments = []
                hooks = []

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
                    hook_sel = _select_hook_for_clip(float(start), float(end), hooks, segments)
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
            # Si ENABLE y video existe como archivo, intenta render; si no, usa storage original o vacío
            video_exists = False
            try:
                video_exists = Path(video.filepath).is_file()
            except Exception:
                video_exists = False

            if ENABLE_ASS_HOOK and video_exists:
                try:
                    final_path, render_meta = _render_clip_with_ass_and_hook(
                        video.filepath, float(start), float(end), segments, hook_sel, job.id, idx, str(title)[:255] if title else None
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
                            base_tags["hook"]["title"] = hmeta.get("title")
                            base_tags["hook"]["viral_score"] = hmeta.get("viral_score")
                        base_tags["hook"]["source"] = "llm" if hmeta else "synthetic"
                    if render_meta.get("ass_applied"):
                        base_tags["ass"] = {"applied": True, "segments": len(segments)}
                    base_tags["_render"] = r
                    # Permitir que el engine archive su path temporal no persista
                    logger.info("[jobs] clip %s render %s -> %s", idx, r, final_storage)
                except Exception as e:
                    logger.warning("[jobs] render fallo clip %s (%s), fallback storage original: %s", idx, e, storage, exc_info=True)
                    render_stats["fallback"] += 1
                    base_tags["_render_error"] = str(e)[:500]
                    base_tags["_render"] = "failed_fallback"
                    final_storage = storage  # mantiene original (vacío o tmp efímero)
                    # Si storage apunta a /tmp y no existe, quedará vacío y clips.py servirá sample_test
            else:
                # Sin render (disabled o video no en disco)
                if not ENABLE_ASS_HOOK:
                    base_tags["_render"] = "disabled"
                elif not video_exists:
                    base_tags["_render"] = "no_source"
                # Mantener storage original si existe, sino vacío
                final_storage = storage

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

        # Guardar stats de render en result_metadata para observabilidad
        try:
            result["_render_stats"] = render_stats
            result["_ass_hook_enabled"] = ENABLE_ASS_HOOK
            if segments:
                result["_segments_count"] = len(segments)
            if hooks:
                result["_hooks_count"] = len(hooks)
        except Exception:
            pass

        refreshed: Job | None = db.get(Job, job_id)
        if refreshed is None:
            return
        refreshed.result_metadata = result
        refreshed.status = JobStatus.COMPLETED.value
        refreshed.error_message = None
        for c in clips_to_create:
            db.add(c)
        db.commit()
        if result.get("fallback"):
            logger.warning("Job %s completado via fallback (%s clips)", job_id, len(clips_to_create))
        else:
            logger.info("Job %s completado (%s clips)", job_id, len(clips_to_create))
    except Exception as exc:
        logger.exception("Fallo irrecuperable job=%s", job_id)
        try:
            video_fallback: Video | None = None
            try:
                j = db.get(Job, job_id)
                if j is not None:
                    video_fallback = db.get(Video, j.video_id)
            except Exception:
                pass
            fallback = _fallback_result(video_fallback)
            fallback["fatal_error"] = str(exc)[:1000]
            failed: Job | None = db.get(Job, job_id)
            if failed is not None:
                from ..models import Clip as ClipModel

                failed.result_metadata = fallback
                failed.status = JobStatus.COMPLETED.value
                failed.error_message = None
                for item in fallback.get("clips", []):
                    if not isinstance(item, dict):
                        continue
                    title = item.get("titulo", "Clip fallback")
                    start = _parse_time_to_seconds(item.get("inicio", 10))
                    end = _parse_time_to_seconds(item.get("fin", 45))
                    db.add(
                        ClipModel(
                            video_id=video_fallback.id if video_fallback else failed.video_id,
                            job_id=failed.id,
                            title=str(title)[:255],
                            start_time=float(start),
                            end_time=float(end),
                            score=float(item.get("score", 7.0)),
                            tags=None,
                            storage_path="",
                            status="ready",
                        )
                    )
                db.commit()
                logger.warning("Job %s recuperado via fallback tras error fatal", job_id)
                return
        except Exception:
            logger.exception("Fallo al aplicar fallback fatal job=%s", job_id)
        try:
            failed2: Job | None = db.get(Job, job_id)
            if failed2 is not None:
                failed2.status = JobStatus.FAILED.value
                failed2.error_message = str(exc)[:2000]
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


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
    )
    db.add(job)
    db.commit()
    db.refresh(job)

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
