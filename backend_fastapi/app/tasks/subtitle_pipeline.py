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
        clip.status = "PROCESSING"
        if hasattr(clip, "error_log"):
            try:
                setattr(clip, "error_log", None)
            except Exception:
                pass
        db.commit()

        video_path = _resolve_video_path(clip, db)
        if video_path is None or not Path(video_path).is_file():
            raise FileNotFoundError(f"Video fuente no encontrado para clip {cid}")

        from ..services.ass_generator import write_ass_file
        from ..services.ffmpeg_service import burn_subtitles
        from ..services.whisper_service import extract_audio_wav, transcribe_wav

        tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_wav.close()
        wav_path = tmp_wav.name
        tmp_wav_created = True

        tmp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False)
        tmp_ass.close()
        ass_path = tmp_ass.name
        tmp_ass_created = True

        extract_audio_wav(video_path, wav_path)

        segments = transcribe_wav(wav_path, language="es")

        if not segments:
            raise RuntimeError("Transcripcion vacia: no se generaron segmentos")

        clipped: list[dict] = []
        for seg in segments:
            s = float(seg["start"])
            e = float(seg["end"])
            if e <= s:
                continue
            if e < clip.start_time or s > clip.end_time:
                continue
            cs = max(s, float(clip.start_time))
            ce = min(e, float(clip.end_time))
            if ce > cs:
                clipped.append({"start": cs - float(clip.start_time), "end": ce - float(clip.start_time), "text": str(seg["text"])})
        target_segments = clipped if clipped else [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in segments]

        write_ass_file(target_segments, ass_path, title=clip.title or str(clip.id))

        suffix = Path(video_path).suffix or ".mp4"
        out_name = f"{clip.id}_subtitled{suffix}"
        storage_dir = Path(video_path).parent
        if not storage_dir.is_dir():
            storage_dir = Path.cwd() / "storage" / "clips"
            storage_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(storage_dir / out_name)

        if Path(output_path).resolve() == Path(video_path).resolve():
            output_path = str(storage_dir / f"{clip.id}_subtitled_burned{suffix}")

        burn_subtitles(video_path, ass_path, output_path)

        refreshed = _get_clip_or_none(db, cid)
        if refreshed is None:
            return
        _update_clip_status(db, refreshed, "COMPLETED", output_path=output_path)
        db.commit()

    except Exception as exc:
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
    finally:
        for p, created in ((wav_path, tmp_wav_created), (ass_path, tmp_ass_created)):
            if p and created:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
        try:
            db.close()
        except Exception:
            pass
