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


def _ruta_de_atributos(obj: Any, atributos: tuple[str, ...]) -> str | None:
    """Primera ruta de archivo existente entre los atributos dados."""
    for attr in atributos:
        v = getattr(obj, attr, None)
        if v and Path(str(v)).is_file():
            return str(v)
    return None


def _ruta_desde_video(db: Session, video_id: Any) -> str | None:
    """Ruta del video por video_id directo (si existe)."""
    try:
        from ..models import Video

        video = db.get(Video, video_id)
        if video is not None:
            return _ruta_de_atributos(video, ("filepath", "file_path"))
    except Exception:
        pass
    return None


def _ruta_video_de_job(db: Session, job: Any) -> str | None:
    """Ruta del Video asociado al Job."""
    from ..models import Video

    video = db.get(Video, job.video_id)
    if video is not None:
        return _ruta_de_atributos(video, ("filepath", "file_path"))
    return None


def _ruta_desde_job(db: Session, job_id: Any) -> str | None:
    """Ruta del video a través del Job del clip."""
    try:
        from ..models import Job

        job = db.get(Job, job_id)
        if job is not None:
            return _ruta_video_de_job(db, job)
    except Exception:
        pass
    return None


def _ruta_via_ids(clip: Clip, db: Session) -> str | None:
    """Ruta del video por video_id directo o vía Job del clip."""
    for id_attr, resolver in (("video_id", _ruta_desde_video), ("job_id", _ruta_desde_job)):
        valor = getattr(clip, id_attr, None)
        if valor is None:
            continue
        ruta = resolver(db, valor)
        if ruta is not None:
            return ruta
    return None


def _resolve_video_path(clip: Clip, db: Session) -> str | None:
    """Ruta del video del clip: storage/file del clip, Video directo o vía Job."""
    ruta = _ruta_de_atributos(clip, ("storage_path", "file_path"))
    if ruta is not None:
        return ruta
    return _ruta_via_ids(clip, db)


def _tags_para_error(clip: Any) -> dict:
    """Dict de tags del clip, preservando tags crudos no dict."""
    tags = clip.tags if isinstance(clip.tags, dict) else {}
    if not isinstance(tags, dict):
        tags = {"_raw_tags": clip.tags} if clip.tags is not None else {}
    return tags


def _guardar_error_log(clip: Any, error_log: str) -> None:
    """Guarda el error en error_log o en tags si el modelo no lo soporta."""
    if hasattr(clip, "error_log"):
        try:
            setattr(clip, "error_log", error_log[:8000])
        except Exception:
            pass
        return
    tags = _tags_para_error(clip)
    tags["error_log"] = error_log[:4000]
    tags["_subtitle_error"] = error_log[:2000]
    clip.tags = tags


def _limpiar_error_completado(clip: Any, has_error_log: bool) -> None:
    """Al completar con modelo que soporta error_log, lo limpia."""
    if has_error_log:
        try:
            setattr(clip, "error_log", None)
        except Exception:
            pass


def _guardar_output_path(clip: Any, output_path: str | None) -> None:
    """Guarda la ruta de salida del clip (best-effort)."""
    if output_path is not None:
        try:
            clip.storage_path = output_path
        except Exception:
            pass


def _update_clip_status(
    db: Session,
    clip: Clip,
    status: str,
    error_log: str | None = None,
    output_path: str | None = None,
) -> None:
    """Actualiza estado, error_log y ruta de salida del clip."""
    clip.status = status
    if error_log is not None:
        _guardar_error_log(clip, error_log)
    elif status == "COMPLETED":
        _limpiar_error_completado(clip, hasattr(clip, "error_log"))
    _guardar_output_path(clip, output_path)


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


def _segmento_en_ventana(s: float, e: float, inicio: float, fin: float) -> bool:
    """True si el segmento tiene longitud y cruza la ventana del clip."""
    if e <= s:
        return False
    if e < inicio or s > fin:
        return False
    return True


def _recorte_ventana(seg: dict, inicio: float, fin: float) -> dict | None:
    """Recorte de un segmento a la ventana; None si queda vacío."""
    s = float(seg["start"])
    e = float(seg["end"])
    if not _segmento_en_ventana(s, e, inicio, fin):
        return None
    cs = max(s, inicio)
    ce = min(e, fin)
    if ce > cs:
        return {"start": cs - inicio, "end": ce - inicio, "text": str(seg["text"])}
    return None


def _normalizar_segmentos(segments: list[dict]) -> list[dict]:
    """Todos los segmentos tal cual, como dicts normalizados."""
    return [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in segments]


def _recortar_segmentos(segments: list[dict], clip: Any) -> list[dict]:
    """Recorta los segmentos a la ventana del clip y los shiftea a 0."""
    inicio = float(clip.start_time)
    fin = float(clip.end_time)
    recortes = (_recorte_ventana(seg, inicio, fin) for seg in segments)
    clipped = [recorte for recorte in recortes if recorte is not None]
    if clipped:
        return clipped
    # Sin recortes dentro de la ventana: usar todos los segmentos tal cual
    return _normalizar_segmentos(segments)


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


def _parse_clip_id(clip_id: uuid.UUID | str) -> uuid.UUID:
    """UUID del clip o ValueError descriptivo."""
    try:
        return uuid.UUID(str(clip_id))
    except Exception as exc:
        raise ValueError(f"clip_id invalido: {clip_id}") from exc


def _asegurar_video_fuente(clip: Clip, db: Session, cid: uuid.UUID) -> str:
    """Ruta del video fuente o FileNotFoundError si no existe."""
    video_path = _resolve_video_path(clip, db)
    if video_path is None or not Path(video_path).is_file():
        raise FileNotFoundError(f"Video fuente no encontrado para clip {cid}")
    return video_path


def _crear_ass_temporal() -> str:
    """Archivo .ass temporal para el render."""
    tmp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False)
    tmp_ass.close()
    return tmp_ass.name


def _transcribir_y_renderizar(video_path: str, clip: Any, ass_path: str) -> tuple[str, str | None]:
    """Transcribe, recorta, escribe el .ass y renderiza; devuelve (output_path, wav_path)."""
    from ..services.ass_generator import write_ass_file
    from ..services.ffmpeg_service import burn_subtitles

    segments, wav_path = _transcribir_clip(video_path)
    if not segments:
        raise RuntimeError("Transcripcion vacia: no se generaron segmentos")

    target_segments = _recortar_segmentos(segments, clip)
    write_ass_file(target_segments, ass_path, title=clip.title or str(clip.id))

    output_path = _resolver_salida(video_path, clip)
    burn_subtitles(video_path, ass_path, output_path)
    return output_path, wav_path


def run_subtitle_pipeline(clip_id: uuid.UUID | str) -> None:
    """Genera el video del clip con subtítulos quemados y marca su estado final."""
    cid = _parse_clip_id(clip_id)

    db: Session = SessionLocal()
    wav_path: str | None = None
    ass_path: str | None = None

    try:
        clip = _get_clip_or_none(db, cid)
        if clip is None:
            return
        _marcar_clip_procesando(db, clip)

        video_path = _asegurar_video_fuente(clip, db, cid)
        ass_path = _crear_ass_temporal()
        output_path, wav_path = _transcribir_y_renderizar(video_path, clip, ass_path)

        refreshed = _get_clip_or_none(db, cid)
        if refreshed is None:
            return
        _update_clip_status(db, refreshed, "COMPLETED", output_path=output_path)
        db.commit()

    except Exception as exc:
        _marcar_fallo(db, cid, exc)
    finally:
        _limpiar_temporales(wav_path, ass_path, wav_path is not None, ass_path is not None)
