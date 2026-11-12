from __future__ import annotations

import tempfile
import traceback
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Clip


def _get_clip_or_none(db: Session, clip_id: uuid.UUID) -> Clip | None:
    return db.get(Clip, clip_id)


def _resolve_video_path(clip: Clip, db: Session) -> str | None:
    for attr in ("storage_path", "file_path"):
        v = getattr(clip, attr, None)
        if v and Path(str(v)).is_file():
            return str(v)
    if clip.video_id is not None:
        try:
            from ..models import Video

            video = db.get(Video, clip.video_id)
            if video is not None:
                for attr in ("filepath", "file_path"):
                    v = getattr(video, attr, None)
                    if v and Path(str(v)).is_file():
                        return str(v)
        except Exception:
            pass
    if clip.job_id is not None:
        try:
            from ..models import Job, Video

            job = db.get(Job, clip.job_id)
            if job is not None:
                video = db.get(Video, job.video_id)
                if video is not None:
                    for attr in ("filepath", "file_path"):
                        v = getattr(video, attr, None)
                        if v and Path(str(v)).is_file():
                            return str(v)
        except Exception:
            pass
    return None


def _update_clip_status(
    db: Session,
    clip: Clip,
    status: str,
    error_log: str | None = None,
    output_path: str | None = None,
) -> None:
    clip.status = status
    has_error_log = hasattr(clip, "error_log")
    if error_log is not None:
        if has_error_log:
            try:
                setattr(clip, "error_log", error_log[:8000])
            except Exception:
                pass
        else:
            tags = clip.tags if isinstance(clip.tags, dict) else {}
            if not isinstance(tags, dict):
                tags = {"_raw_tags": clip.tags} if clip.tags is not None else {}
            tags["error_log"] = error_log[:4000]
            tags["_subtitle_error"] = error_log[:2000]
            clip.tags = tags
    elif status == "COMPLETED" and has_error_log:
        try:
            setattr(clip, "error_log", None)
        except Exception:
            pass
    if output_path is not None:
        try:
            clip.storage_path = output_path
        except Exception:
            pass


def _marcar_clip_procesando(db: Session, clip: Any) -> None:
    """PROCESSING + limpia error_log previo."""
    clip.status = "PROCESSING"
    if hasattr(clip, "error_log"):
        try:
            setattr(clip, "error_log", None)
        except Exception:
            pass
    db.commit()


def _transcribir_clip(video_path: str) -> tuple[list[dict], str | None]:
    """Transcripción: RunPod directo si está configurado, si no Whisper local con WAV.

    Devuelve (segmentos, wav_path) — wav_path solo si se creó un WAV temporal.
    """
    from ..services.runpod_service import is_runpod_configured
    from ..services.whisper_service import extract_audio_wav, transcribe_video, transcribe_wav

    if is_runpod_configured():
        return transcribe_video(video_path, language="es"), None

    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_wav.close()
    extract_audio_wav(video_path, tmp_wav.name)
    return transcribe_wav(tmp_wav.name, language="es"), tmp_wav.name


def _recortar_segmentos(segments: list[dict], clip: Any) -> list[dict]:
    """Recorta los segmentos a la ventana del clip y los shiftea a 0."""
    inicio = float(clip.start_time)
    fin = float(clip.end_time)
    clipped: list[dict] = []
    for seg in segments:
        s = float(seg["start"])
        e = float(seg["end"])
        if e <= s:
            continue
        if e < inicio or s > fin:
            continue
        cs = max(s, inicio)
        ce = min(e, fin)
        if ce > cs:
            clipped.append({"start": cs - inicio, "end": ce - inicio, "text": str(seg["text"])})
    if clipped:
        return clipped
    # Sin recortes dentro de la ventana: usar todos los segmentos tal cual
    return [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in segments]


def _resolver_salida(video_path: str, clip: Any) -> str:
    """Ruta de salida del clip subtitulado (evita sobrescribir el original)."""
    suffix = Path(video_path).suffix or ".mp4"
    out_name = f"{clip.id}_subtitled{suffix}"
    storage_dir = Path(video_path).parent
    if not storage_dir.is_dir():
        storage_dir = Path.cwd() / "storage" / "clips"
        storage_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(storage_dir / out_name)
    if Path(output_path).resolve() == Path(video_path).resolve():
        output_path = str(storage_dir / f"{clip.id}_subtitled_burned{suffix}")
    return output_path


def _marcar_fallo(db: Session, cid: uuid.UUID, exc: Exception) -> None:
    """Rollback + marca el clip FAILED con el traceback completo."""
    tb = traceback.format_exc()
    error_log = f"{type(exc).__name__}: {exc}\n{tb}"
    try:
        db.rollback()
    except Exception:
        pass
    try:
        failed = _get_clip_or_none(db, cid)
        if failed is not None:
            _update_clip_status(db, failed, "FAILED", error_log=error_log)
            db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _limpiar_temporales(wav_path: str | None, ass_path: str | None, tmp_wav_created: bool, tmp_ass_created: bool) -> None:
    for p, created in ((wav_path, tmp_wav_created), (ass_path, tmp_ass_created)):
        if p and created:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass


def run_subtitle_pipeline(clip_id: uuid.UUID | str) -> None:
    try:
        cid = uuid.UUID(str(clip_id))
    except Exception as exc:
        raise ValueError(f"clip_id invalido: {clip_id}") from exc

    db: Session = SessionLocal()
    wav_path: str | None = None
    ass_path: str | None = None
    tmp_wav_created = False
    tmp_ass_created = False

    try:
        clip = _get_clip_or_none(db, cid)
        if clip is None:
            return
        _marcar_clip_procesando(db, clip)

        video_path = _resolve_video_path(clip, db)
        if video_path is None or not Path(video_path).is_file():
            raise FileNotFoundError(f"Video fuente no encontrado para clip {cid}")

        from ..services.ass_generator import write_ass_file
        from ..services.ffmpeg_service import burn_subtitles
        from ..services.runpod_service import is_runpod_configured
        from ..services.whisper_service import extract_audio_wav, transcribe_video, transcribe_wav

        tmp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False)
        tmp_ass.close()
        ass_path = tmp_ass.name
        tmp_ass_created = True

        if is_runpod_configured():
            segments = transcribe_video(video_path, language="es")
        else:
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_wav.close()
            wav_path = tmp_wav.name
            tmp_wav_created = True
            extract_audio_wav(video_path, wav_path)
            segments = transcribe_wav(wav_path, language="es")

        if not segments:
            raise RuntimeError("Transcripcion vacia: no se generaron segmentos")

        target_segments = _recortar_segmentos(segments, clip)
        write_ass_file(target_segments, ass_path, title=clip.title or str(clip.id))

        output_path = _resolver_salida(video_path, clip)
        burn_subtitles(video_path, ass_path, output_path)

        refreshed = _get_clip_or_none(db, cid)
        if refreshed is None:
            return
        _update_clip_status(db, refreshed, "COMPLETED", output_path=output_path)
        db.commit()

    except Exception as exc:
        _marcar_fallo(db, cid, exc)
    finally:
        _limpiar_temporales(wav_path, ass_path, tmp_wav_created, tmp_ass_created)
