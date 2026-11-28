"""Editor ligero de clips: re-trim + re-render con ASS y RenderConfig (Issue #121).

Expone:
- POST /clips/{clip_id}/retrim          → re-corta, re-renderiza y reemplaza el clip.
- GET  /clips/{clip_id}/retrim/options  → datos para precargar el modal React.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend.core.schemas import RenderConfig

from ..deps import CurrentUser, DbSession
from ..models import Clip, Job, Video
from ..services import retrim_service
from ..services.ass_generator import CAPTION_STYLES
from ..services.ffmpeg_service import probe_duration

router = APIRouter(prefix="/clips", tags=["clips-retrim"])

MAX_RANGE_SECONDS = 86_400.0


class SubtitleCue(BaseModel):
    """Cue de subtítulo en tiempo absoluto del video fuente."""

    start: float = Field(..., ge=0, description="Inicio absoluto en segundos")
    end: float = Field(..., ge=0, description="Fin absoluto en segundos")
    text: str = Field(..., min_length=1, max_length=500)

    @model_validator(mode="after")
    def _valid_range(self) -> "SubtitleCue":
        if self.end <= self.start:
            raise ValueError("end debe ser > start")
        return self


class RetrimRequest(BaseModel):
    """Payload del editor: rango, subtítulos editados y configuración de render."""

    start_time: float = Field(..., ge=0, le=MAX_RANGE_SECONDS, description="Nuevo inicio en segundos")
    end_time: float = Field(..., ge=0, le=MAX_RANGE_SECONDS, description="Nuevo fin en segundos")
    subtitles_text: str | None = Field(default=None, max_length=retrim_service.MAX_TEXT_CHARS)
    subtitle_cues: list[SubtitleCue] | None = Field(default=None, max_length=retrim_service.MAX_SUBTITLE_CUES)
    render_config: RenderConfig | None = Field(default=None, description="Plantilla, watermark, hook y audio")
    enable_hook_teaser: bool = Field(default=True, description="Compat: hook si RenderConfig no lo define")
    sfx_mood: str = Field(default="transition", pattern=r"^(tension|impact|transition|none)$")

    def validate_range(self) -> None:
        """Compatibilidad con el contrato previo (5–90 s)."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time debe ser > start_time")
        if self.end_time - self.start_time < retrim_service.MIN_DURATION:
            raise ValueError("Duración mínima 5s")
        if self.end_time - self.start_time > retrim_service.MAX_DURATION:
            raise ValueError("Duración máxima 90s")

    def effective_config(self) -> RenderConfig:
        """RenderConfig explícito o uno construido con los campos legacy."""
        if self.render_config is not None:
            return self.render_config
        return RenderConfig(enable_hook_teaser=self.enable_hook_teaser, sfx_mood=self.sfx_mood)


class RetrimResponse(BaseModel):
    clip_id: str
    start_time: float
    end_time: float
    duration: float
    status: str = "ready"
    file_path: str | None = None
    retrim_count: int = 0
    retrim_limit: int = retrim_service.DEFAULT_MAX_RETRIMS
    caption_style: str = retrim_service.DEFAULT_CAPTION_STYLE


class RetrimOptionsResponse(BaseModel):
    clip_id: str
    start_time: float
    end_time: float
    source_duration: float | None = None
    duration: float
    subtitles: list[SubtitleCue]
    subtitles_text: str
    retrim_count: int
    retrim_limit: int
    caption_styles: list[str]
    default_caption_style: str
    has_hook: bool
    watermark_path: str | None = None


def _job_of(db: DbSession, clip: Clip) -> Job | None:
    if not clip.job_id:
        return None
    return db.get(Job, clip.job_id)


def _video_of(db: DbSession, job: Job | None) -> Video | None:
    if job is None:
        return None
    return db.get(Video, job.video_id)


def _assert_owner(video: Video | None, user_id: Any) -> None:
    if video is None:
        raise HTTPException(status_code=404, detail="Clip no encontrado")
    if video.user_id != user_id:
        raise HTTPException(status_code=404, detail="Clip no encontrado")


def _load_owned_clip(db: DbSession, clip_id: str, user_id: Any) -> tuple[Clip, Job | None, Video | None]:
    clip = db.get(Clip, retrim_service.clip_uuid(clip_id))
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip no encontrado")
    job = _job_of(db, clip)
    video = _video_of(db, job)
    _assert_owner(video, user_id)
    return clip, job, video


def _plan_from_request(body: RetrimRequest, clip: Clip, source: Any, cues: list[dict[str, Any]]) -> retrim_service.RetrimPlan:
    config = body.effective_config()
    hook = retrim_service.hook_window(clip) if config.enable_hook_teaser else None
    title = str(getattr(clip, "title", None) or "clipsai")
    return retrim_service.RetrimPlan(
        source=source,
        start=float(body.start_time),
        end=float(body.end_time),
        cues=cues,
        hook=hook,
        config=config,
        title=title,
    )


def _response(clip: Clip, plan: retrim_service.RetrimPlan, duration: float) -> RetrimResponse:
    status = str(getattr(clip, "status", None) or "ready")
    return RetrimResponse(
        clip_id=str(clip.id),
        start_time=plan.start,
        end_time=plan.end,
        duration=duration,
        status=status,
        file_path=str(getattr(clip, "storage_path", "") or ""),
        retrim_count=retrim_service.retrim_count(clip),
        retrim_limit=retrim_service.max_retrims(),
        caption_style=plan.config.caption_style,
    )


@router.post("/{clip_id}/retrim", response_model=RetrimResponse, summary="Editar rango, subtítulos y estilo de un clip")
def retrim_clip(
    clip_id: str,
    body: RetrimRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> RetrimResponse:
    clip, job, video = _load_owned_clip(db, clip_id, current_user.id)
    source = retrim_service.select_source(clip, job, video)
    duration = retrim_service.validate_window(body.start_time, body.end_time, probe_duration(source))
    cues = retrim_service.resolve_cues(body, clip, job, video)
    plan = _plan_from_request(body, clip, source, cues)

    previous = retrim_service.reserve_retrim(clip, db)
    try:
        retrim_service.execute_retrim(db, clip, plan)
    except Exception:
        retrim_service.release_retrim(clip, db, previous)
        raise
    return _response(clip, plan, duration)


def _safe_style(style: str | None) -> str:
    return style if style in CAPTION_STYLES else retrim_service.DEFAULT_CAPTION_STYLE


@router.get(
    "/{clip_id}/retrim/options",
    response_model=RetrimOptionsResponse,
    summary="Datos actuales del clip para precargar el editor",
)
def retrim_options(
    clip_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> RetrimOptionsResponse:
    clip, job, video = _load_owned_clip(db, clip_id, current_user.id)
    source = retrim_service.select_source(clip, job, video)
    start = float(clip.start_time)
    end = float(clip.end_time)
    cues = retrim_service.options_cues(clip, job, video, (start, end))
    meta = retrim_service.retrim_meta(clip)
    style = _safe_style(str(meta.get("caption_style") or ""))
    return RetrimOptionsResponse(
        clip_id=str(clip.id),
        start_time=start,
        end_time=end,
        source_duration=probe_duration(source),
        duration=end - start,
        subtitles=[SubtitleCue(**cue) for cue in cues],
        subtitles_text="\n".join(cue["text"] for cue in cues),
        retrim_count=retrim_service.retrim_count(clip),
        retrim_limit=retrim_service.max_retrims(),
        caption_styles=list(CAPTION_STYLES),
        default_caption_style=style,
        has_hook=bool(retrim_service.hook_window(clip)),
        watermark_path=meta.get("watermark_path"),
    )
