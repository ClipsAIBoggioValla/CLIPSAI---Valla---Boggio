"""Router de Clips — CRUD + descarga + biblioteca (Issue 5 + Issue 16)."""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

from ..deps import CurrentUser, DbSession
from ..models import Clip, Video
from ..schemas import ClipListItem, ClipListResponse, ClipResponse, ClipUpdate

router = APIRouter(prefix="/clips", tags=["clips"])


def _clip_has_ass(tags: object) -> bool:
    if not isinstance(tags, dict):
        return False
    # FIX: has_ass explícito tiene prioridad (re-render)
    if "has_ass" in tags:
        return bool(tags.get("has_ass"))
    if isinstance(tags.get("ass"), dict) and tags["ass"].get("applied"):
        return True
    r = tags.get("_render")
    return r in ("ass", "hook+ass")


def _clip_has_hook(tags: object) -> bool:
    if not isinstance(tags, dict):
        return False
    if "has_hook" in tags:
        return bool(tags.get("has_hook"))
    if isinstance(tags.get("hook"), dict) and tags["hook"].get("applied"):
        return True
    r = tags.get("_render")
    return r in ("hook", "hook+ass")


def _clip_duration(start: float, end: float) -> float | None:
    try:
        return float(end) - float(start)
    except Exception:
        return None


def _clip_file_path(clip: Clip) -> str | None:
    return getattr(clip, "storage_path", None)


def _clip_stream_url(clip_id: uuid.UUID) -> str:
    return f"/clips/{clip_id}/descarga"


def _enrich_clip_response(clip: Clip) -> dict:
    return {
        "id": clip.id,
        "video_id": getattr(clip, "video_id", None),
        "job_id": clip.job_id,
        "title": clip.title,
        "start_time": clip.start_time,
        "end_time": clip.end_time,
        "score": clip.score,
        "tags": clip.tags,
        "storage_path": getattr(clip, "storage_path", None),
        "file_path": _clip_file_path(clip),
        "stream_url": _clip_stream_url(clip.id),
        "duration": _clip_duration(clip.start_time, clip.end_time),
        "has_ass": _clip_has_ass(clip.tags),
        "has_hook": _clip_has_hook(clip.tags),
        "status": clip.status,
        "published_platform": getattr(clip, "published_platform", None),
        "social_post_id": getattr(clip, "social_post_id", None),
        "social_post_url": getattr(clip, "social_post_url", None),
        "published_at": getattr(clip, "published_at", None),
        "publication_status": getattr(clip, "publication_status", None),
        "social_network": getattr(clip, "social_network", None),
        "created_at": clip.created_at,
        "updated_at": clip.updated_at,
    }


class ReRenderRequest(BaseModel):
    enable_ass: bool = True
    enable_hook: bool = True


def _run_re_render(clip_id: uuid.UUID, enable_ass: bool, enable_hook: bool) -> None:
    from ..database import SessionLocal as _SessionLocal

    db = _SessionLocal()
    try:
        clip = db.get(Clip, clip_id)
        if clip is None:
            return
        # Resolver video
        video = None
        if clip.video_id is not None:
            video = db.get(Video, clip.video_id)
        if video is None and clip.job_id is not None:
            from ..models import Job

            job = db.get(Job, clip.job_id)
            if job is not None:
                video = db.get(Video, job.video_id)
        if video is None or not Path(str(video.filepath)).is_file():
            clip.status = "FAILED"
            clip.error_log = "Video origen no encontrado para re-render"
            db.commit()
            return

        # Cargar segmentos si alguno de los flags activo
        segments: list[dict] = []
        hooks: list[dict] = []
        if enable_ass or enable_hook:
            try:
                # Reusar lógica de jobs.py sin importar circular: intentar whisper + parse
                try:
                    from ..services.whisper_service import transcribe_video

                    segs = transcribe_video(str(video.filepath), language="es")
                    if segs:
                        segments = [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in segs]
                except Exception:
                    pass
                if not segments:
                    # Fallback parse transcript
                    import re

                    txt = None
                    if video.transcript:
                        txt = video.transcript
                    elif video.transcription_filepath and Path(str(video.transcription_filepath)).is_file():
                        txt = Path(str(video.transcription_filepath)).read_text(encoding="utf-8", errors="ignore")
                    if txt:
                        # parser simple HH:MM:SS - texto
                        segs2: list[dict] = []
                        re_ts = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*(.+)$")
                        cursor = 0.0
                        for line in txt.splitlines():
                            line=line.strip()
                            if not line:
                                continue
                            m=re_ts.match(line)
                            if m:
                                ts_str=m.group(1); t=m.group(2).strip()
                                try:
                                    parts=ts_str.split(":")
                                    if len(parts)==3:
                                        s=int(parts[0])*3600+int(parts[1])*60+float(parts[2])
                                    elif len(parts)==2:
                                        s=int(parts[0])*60+float(parts[1])
                                    else:
                                        s=float(parts[0])
                                    segs2.append({"start": s, "end": s+3.0, "text": t})
                                    cursor=s+3.0
                                    continue
                                except Exception:
                                    pass
                            segs2.append({"start": cursor, "end": cursor+3.0, "text": line})
                            cursor+=3.0
                        segments = segs2
                if enable_hook and segments:
                    try:
                        from ..services.hook_service import detect_hooks

                        duration = None
                        try:
                            if video.duration_seconds:
                                duration=float(video.duration_seconds)
                            elif segments:
                                duration=float(segments[-1].get("end",0))
                        except Exception:
                            duration=None
                        hooks = detect_hooks(segments, duration_hint=duration, mock=False) or []
                    except Exception:
                        hooks=[]
            except Exception as e:
                logger.warning(f"[re-render] segmentos/hooks fallo: {e}")
                segments=[]
                hooks=[]

        # Seleccionar hook si enable_hook
        hook_sel = None
        if enable_hook and segments:
            try:
                # Buscar hook LLM contenido
                best=None
                for h in hooks:
                    try:
                        hk=h.get("hook") or {}
                        hs=float(hk.get("start_time", hk.get("start",0))); he=float(hk.get("end_time", hk.get("end",0)))
                        if clip.start_time <= hs < he <= clip.end_time and 3.0 <= (he-hs) <=6.0:
                            score=int(h.get("viral_score",0))
                            if best is None or score>best[2].get("viral_score",0):
                                best=(hs,he,h)
                    except Exception:
                        continue
                if best:
                    hook_sel=best
                else:
                    # Sintético centrado
                    clip_dur=clip.end_time - clip.start_time
                    if 15 <= clip_dur <=90:
                        hook_dur=5.0
                        center=(clip.start_time+clip.end_time)/2
                        hs=center-hook_dur/2; he=hs+hook_dur
                        if segments:
                            try:
                                closest=min(segments, key=lambda s: abs(float(s.get("start",0))-hs))
                                cs=float(closest.get("start",hs))
                                if clip.start_time <= cs <= clip.end_time-hook_dur:
                                    hs=cs; he=hs+hook_dur
                            except Exception:
                                pass
                        if hs<clip.start_time:
                            hs=clip.start_time; he=hs+hook_dur
                        if he>clip.end_time:
                            he=clip.end_time; hs=he-hook_dur
                        if he-hs>=3.0:
                            hook_sel=(round(hs,2), round(he,2), None)
            except Exception:
                hook_sel=None

        # Desactivar flags según enable
        effective_hook = hook_sel if enable_hook else None
        effective_segments: list[dict] | None = segments if enable_ass else None
        # Si enable_ass False, no pasar segmentos a render (evita ASS)
        segs_for_render = effective_segments if enable_ass else []

        from ..routers.jobs import _render_clip_with_ass_and_hook as _render  # reuse

        # Usar helper de jobs para render (import diferido para evitar ciclo)
        try:
            # _render espera segments list; si enable_ass False, pasar lista vacía
            out_path, meta = _render(
                str(video.filepath),
                float(clip.start_time),
                float(clip.end_time),
                segs_for_render or [],
                effective_hook,
                clip.job_id,
                0,
                clip.title,
            )
            clip.storage_path = out_path
            # Actualizar tags — FIX: actualizar explícitamente has_ass/has_hook = enable_* antes del commit (auditoría Parte 1)
            tags = clip.tags if isinstance(clip.tags, dict) else {}
            if not isinstance(tags, dict):
                tags={}
            # FIX explícito requerido por auditoría: has_ass/has_hook reflejan el toggle solicitado
            tags["has_ass"] = bool(enable_ass)
            tags["has_hook"] = bool(enable_hook)
            # Mantener estructura legacy "ass"/"hook" para compatibilidad con _clip_has_ass/_clip_has_hook
            if enable_hook and meta.get("hook_applied"):
                hs,he,_=effective_hook if effective_hook else (None,None,None)
                tags["hook"]={"start":hs,"end":he,"applied":True, "source": "re-render"}
                # has_hook ya True arriba
            elif not enable_hook:
                tags.pop("hook", None)
                tags["has_hook"] = False
            else:
                # enable_hook True pero hook no aplicado (ej. duración <15s)
                if meta.get("hook_applied") is False or not meta.get("hook_applied"):
                    # Mantener has_hook True (usuario lo pidió) pero marcar detalle
                    if "hook" not in tags:
                        tags["hook"]={"applied": False, "reason": "hook no aplicable o fallo FFmpeg", "requested": True}
            if enable_ass and meta.get("ass_applied"):
                tags["ass"]={"applied": True, "segments": len(segments) if segments else 0}
                tags["has_ass"] = True
            elif enable_ass and not meta.get("ass_applied"):
                # enable_ass True pero ASS falló: mantener has_ass True y registrar error
                tags["ass"]={"applied": False, "reason": "ASS fallo, fallback sin subtítulos", "requested": True}
                tags["has_ass"] = True
            elif not enable_ass:
                tags.pop("ass", None)
                tags["has_ass"] = False
            tags["_render"]=meta.get("render","re-render")
            tags["_re_render"]= {"enable_ass": enable_ass, "enable_hook": enable_hook, "at": __import__("datetime").datetime.utcnow().isoformat(), "out_path": out_path}
            clip.tags=tags
            clip.status="ready"
            clip.error_log=None
            # FIX: storage_path ya actualizado arriba; updated_at se actualiza por trigger set_updated_at(), pero forzamos toque para cache busting
            try:
                from sqlalchemy import func as _func
                clip.updated_at = _func.now()  # noqa: trigger también lo hará
            except Exception:
                pass
            db.commit()
            logger.info(f"[re-render] clip {clip_id} ok -> {out_path} meta={meta} has_ass={tags['has_ass']} has_hook={tags['has_hook']}")
        except Exception as e:
            import traceback

            clip.status="FAILED"
            clip.error_log=str(e)[:2000] + "\n" + traceback.format_exc()[:2000]
            # tags error
            tags = clip.tags if isinstance(clip.tags, dict) else {}
            if not isinstance(tags, dict):
                tags={}
            tags["_render_error"]=str(e)[:500]
            clip.tags=tags
            db.commit()
            logger.exception(f"[re-render] fallo clip {clip_id}")
    except Exception as e:
        logger.exception(f"[re-render] error inesperado {clip_id}: {e}")
    finally:
        try:
            db.close()
        except Exception:
            pass

# Auditoría 2026-09-21: pipeline real 100% — sin fallback de prueba. El worker escribe MP4 físico en /app/storage/clips.


def _get_clip_or_404(db: DbSession, clip_id: uuid.UUID) -> Clip:
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    return clip


def _assert_ownership(db: DbSession, clip: Clip, current_user) -> None:
    video = None
    if clip.video_id is not None:
        video = db.get(Video, clip.video_id)
    if video is None and clip.job_id is not None:
        from ..models import Job

        job = db.get(Job, clip.job_id)
        if job is not None:
            video = db.get(Video, job.video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip no encontrado")
    if video.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para este clip")


@router.get(
    "",
    response_model=ClipListResponse,
    summary="Listar clips del usuario (biblioteca con búsqueda, filtros y paginación)",
)
def list_clips(
    db: DbSession,
    current_user: CurrentUser,
    q: Optional[str] = Query(default=None, description="Búsqueda por título o transcripción (case-insensitive)"),
    min_score: Optional[float] = Query(default=None, ge=0, le=100, description="Score mínimo (0-100)"),
    sort_by: Literal["created_at_desc", "created_at_asc", "score_desc", "score_asc"] = Query(
        default="created_at_desc", description="Orden de resultados"
    ),
    page: int = Query(default=1, ge=1, description="Número de página"),
    limit: int = Query(default=10, ge=1, le=100, description="Tamaño de página"),
    video_id: Optional[uuid.UUID] = Query(default=None, description="Filtrar por video"),
    status: Optional[str] = Query(default=None, description="Filtrar por status"),
    job_id: Optional[uuid.UUID] = Query(default=None, description="Filtrar por job"),
) -> ClipListResponse:
    from ..models import Job

    base = (
        select(Clip, Video.transcript.label("video_transcript"))
        .join(Job, Clip.job_id == Job.id)
        .join(Video, Job.video_id == Video.id)
        .where(Video.user_id == current_user.id)
    )

    if q is not None and q.strip() != "":
        pattern = f"%{q.strip()}%"
        base = base.where(
            (Clip.title.ilike(pattern)) | (Video.transcript.ilike(pattern))
        )

    if min_score is not None:
        base = base.where(Clip.score >= min_score)

    if video_id is not None:
        base = base.where((Clip.video_id == video_id) | (Job.video_id == video_id))

    if job_id is not None:
        base = base.where(Clip.job_id == job_id)

    if status is not None:
        base = base.where(Clip.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total: int = db.scalar(count_stmt) or 0
    total_pages: int = math.ceil(total / limit) if total > 0 else 0

    if sort_by == "created_at_desc":
        base = base.order_by(Clip.created_at.desc())
    elif sort_by == "created_at_asc":
        base = base.order_by(Clip.created_at.asc())
    elif sort_by == "score_desc":
        base = base.order_by(Clip.score.desc().nulls_last(), Clip.created_at.desc())
    elif sort_by == "score_asc":
        base = base.order_by(Clip.score.asc().nulls_last(), Clip.created_at.desc())

    base = base.offset((page - 1) * limit).limit(limit)

    rows = db.execute(base).all()

    items: list[ClipListItem] = []
    for clip, video_transcript in rows:
        transcript: str | None = None
        if video_transcript:
            transcript = str(video_transcript)[:500]
        items.append(
            ClipListItem(
                id=clip.id,
                job_id=clip.job_id,
                title=clip.title,
                score=clip.score,
                start_time=clip.start_time,
                end_time=clip.end_time,
                transcript=transcript,
                status=getattr(clip, "status", None),
                published_platform=getattr(clip, "published_platform", None),
                social_post_url=getattr(clip, "social_post_url", None),
                published_at=getattr(clip, "published_at", None),
                created_at=clip.created_at,
                updated_at=getattr(clip, "updated_at", None),
                file_path=_clip_file_path(clip),
                stream_url=_clip_stream_url(clip.id),
                duration=_clip_duration(clip.start_time, clip.end_time),
                has_ass=_clip_has_ass(clip.tags),
                has_hook=_clip_has_hook(clip.tags),
                tags=clip.tags if isinstance(clip.tags, (dict, list)) else None,
            )
        )

    return ClipListResponse(items=items, total=total, page=page, limit=limit, total_pages=total_pages)


@router.get(
    "/{clip_id}",
    response_model=ClipResponse,
    summary="Obtener un clip por id",
)
def get_clip(
    clip_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)
    return _enrich_clip_response(clip)


@router.patch(
    "/{clip_id}",
    response_model=ClipResponse,
    summary="Actualizar metadata de un clip (title/tags)",
)
def update_clip(
    clip_id: uuid.UUID,
    payload: ClipUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nada para actualizar")

    if "title" in data:
        clip.title = data["title"]
    if "tags" in data:
        clip.tags = data["tags"]

    db.commit()
    db.refresh(clip)
    return _enrich_clip_response(clip)


@router.post(
    "/{clip_id}/re-render",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-renderizar clip con ASS/Hook (enable_ass, enable_hook)",
)
def re_render_clip(
    clip_id: uuid.UUID,
    payload: ReRenderRequest,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)
    if clip.status == "PROCESSING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Clip ya en procesamiento")
    clip.status = "PROCESSING"
    try:
        clip.error_log = None
    except Exception:
        pass
    db.commit()
    background_tasks.add_task(_run_re_render, clip.id, bool(payload.enable_ass), bool(payload.enable_hook))
    return {"detail": "Re-render encolado", "clip_id": str(clip.id), "status": "PROCESSING", "enable_ass": bool(payload.enable_ass), "enable_hook": bool(payload.enable_hook)}


@router.delete(
    "/{clip_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un clip",
)
def delete_clip(
    clip_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    clip = _get_clip_or_404(db, clip_id)
    _assert_ownership(db, clip, current_user)

    for attr in ("storage_path", "file_path"):
        p = getattr(clip, attr, None)
        if p:
            try:
                path = Path(str(p))
                if path.is_file():
                    path.unlink()
            except Exception:
                pass

    db.delete(clip)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{clip_id}/descarga",
    summary="Descargar archivo del clip (público - sin autenticación para Meta crawler)",
)
def download_clip(
    clip_id: uuid.UUID,
    db: DbSession,
):
    # 1. Lectura directa desde BD: consulta registro clip y obtén ruta real almacenada
    clip = _get_clip_or_404(db, clip_id)
    raw_path = None
    for attr in ("file_path", "video_path", "output_path", "storage_path", "filepath", "path"):
        v = getattr(clip, attr, None)
        if v and str(v).strip():
            raw_path = str(v).strip()
            break
    # Fallback: si clip no tiene ruta, intentar video asociado
    if not raw_path and clip.video_id is not None:
        try:
            video = db.get(Video, clip.video_id)
            if video is not None:
                for attr in ("filepath", "file_path", "video_path", "path"):
                    v = getattr(video, attr, None)
                    if v and str(v).strip():
                        raw_path = str(v).strip()
                        break
        except Exception:
            pass
    if not raw_path:
        logger.error(f"[CLIP DESCARGA] clip {clip_id} sin ruta en BD (file_path/video_path/output_path vacíos)")
        raise HTTPException(status_code=400, detail="El archivo de clip no existe o está vacío")

    # 2. Verificación de ruta — modo 100% real: solo ubicaciones válidas de storage, sin fallback de prueba
    ruta_final = raw_path
    if not os.path.isfile(ruta_final):
        # Fallback limitado y real: buscar basename solo en directorios de storage configurados
        basename = os.path.basename(ruta_final) if os.path.basename(ruta_final) else ruta_final
        candidatos_reales = [
            f"/app/storage/clips/{basename}",
            f"/app/storage/uploads/{basename}",
            f"/app/storage/{basename}",
        ]
        encontrado = None
        for cand in candidatos_reales:
            if os.path.isfile(cand) and os.path.getsize(cand) > 0:
                encontrado = cand
                logger.info(f"[CLIP DESCARGA] Fallback real encontrado en {cand} para basename {basename}")
                break
        if encontrado:
            ruta_final = encontrado
        else:
            # Modo 100% real: no existe archivo físico → error 404 real para que el frontend muestre toast
            logger.error(f"[CLIP DESCARGA] clip {clip_id} archivo no encontrado raw_path={raw_path} basename={basename} — sin fallback de prueba (modo 100%% real)")
            raise HTTPException(status_code=404, detail=f"Archivo de clip no encontrado en storage: {raw_path}. El clip debe ser reprocesado via /clips/{{id}}/re-render.")

    # Verificación final tamaño
    try:
        size = os.path.getsize(ruta_final)
        if size == 0:
            raise HTTPException(status_code=400, detail="El archivo de clip no existe o está vacío")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CLIP DESCARGA] error obteniendo tamaño {ruta_final}: {e}")
        raise HTTPException(status_code=400, detail="El archivo de clip no existe o está vacío")

    # Log requerido
    msg = f"[CLIP DESCARGA] Sirviendo archivo real: {ruta_final} (Tamaño: {size} bytes)"
    print(msg)
    logger.info(msg)

    # 3. Respuesta HTTP con media_type video/mp4
    return FileResponse(path=ruta_final, media_type="video/mp4", filename=f"{clip_id}.mp4")
