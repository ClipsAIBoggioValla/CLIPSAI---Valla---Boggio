from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class WordToken(BaseModel):
    word: str = Field(..., min_length=1, description="Palabra original respetando mayúsculas y signos si aplica")
    start: float = Field(..., ge=0, description="Segundos desde inicio del video")
    end: float = Field(..., ge=0, description="Segundos desde inicio, debe ser >= start")

    @field_validator("end")
    @classmethod
    def validate_end_ge_start(cls, v: float, info) -> float:
        start = info.data.get("start")
        if start is not None and v < start:
            raise ValueError("end debe ser >= start")
        return v

    model_config = {"extra": "forbid"}


class TranscriptData(BaseModel):
    video_id: str = Field(..., min_length=1, description="UUID del video en plataforma")
    language: str = Field(default="es", description="BCP-47, ej es, es-AR")
    words: List[WordToken] = Field(..., min_length=1, description="Tokens ordenados por start")
    raw_text: Optional[str] = Field(default=None, description="Transcripción plana opcional para compatibilidad legacy")
    duration_seconds: Optional[float] = Field(default=None, ge=0)

    model_config = {"extra": "forbid"}


class Platform(str, Enum):
    tiktok = "tiktok"
    instagram = "instagram"
    youtube = "youtube"
    youtube_shorts = "youtube_shorts"
    instagram_reels = "instagram_reels"


class ViralReport(BaseModel):
    hook_strength: int = Field(..., ge=0, le=100)
    emotional_trigger: str = Field(..., description="Ej: revelación, controversia, nostalgia")
    trend_alignment: int = Field(..., ge=0, le=100)
    clarity: int = Field(..., ge=0, le=100)
    viral_reason: str = Field(..., min_length=5)
    suggested_hashtags: List[str] = Field(default_factory=list)
    call_to_action: Optional[str] = None

    model_config = {"extra": "allow"}


class ViralClipCandidate(BaseModel):
    clip_id: str = Field(..., min_length=1, description="ID determinista o UUID del candidato")
    start_time: float = Field(..., ge=0)
    end_time: float = Field(..., ge=0)
    score: int = Field(default=0, ge=0, le=100, description="Score viral 0-100 normalizado")
    headline: str = Field(..., min_length=3, max_length=120)
    viral_report: Dict[str, Any] = Field(
        ..., description="hook_strength, emotional_trigger, trend_alignment, clarity, viral_reason, suggested_hashtags, call_to_action"
    )

    @field_validator("end_time")
    @classmethod
    def validate_end_ge_start(cls, v: float, info) -> float:
        start = info.data.get("start_time")
        if start is not None and v <= start:
            raise ValueError("end_time debe ser > start_time")
        return v

    @field_validator("viral_report")
    @classmethod
    def validate_report_keys(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        required = {"hook_strength", "emotional_trigger", "trend_alignment", "clarity", "viral_reason"}
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"viral_report faltan claves: {sorted(missing)}")
        return v

    model_config = {"extra": "forbid"}


class CaptionStyle(str, Enum):
    karaoke_yellow = "karaoke_yellow"
    neon_green = "neon_green"
    minimal_white = "minimal_white"


class RenderConfig(BaseModel):
    caption_style: str = Field(
        default="karaoke_yellow",
        description="'karaoke_yellow', 'neon_green', 'minimal_white'",
    )
    enable_auto_crop: bool = True
    watermark_path: Optional[str] = Field(default=None, description="Ruta absoluta o s3://")
    outro_path: Optional[str] = Field(default=None, description="Ruta absoluta o s3://")
    resolution: str = Field(default="1080x1920", pattern=r"^\d+x\d+$")
    fps: int = Field(default=30, ge=24, le=60)
    loudnorm_enabled: bool = True

    @field_validator("caption_style")
    @classmethod
    def validate_style(cls, v: str) -> str:
        allowed = {"karaoke_yellow", "neon_green", "minimal_white"}
        if v not in allowed:
            raise ValueError(f"caption_style debe ser uno de {allowed}")
        return v

    model_config = {"extra": "forbid"}


class ScheduledPost(BaseModel):
    clip_id: str = Field(..., min_length=1)
    platforms: List[str] = Field(..., min_length=1, description="['tiktok', 'instagram', 'youtube']")
    scheduled_at: str = Field(..., description="ISO8601 UTC, ej 2026-05-13T15:00:00Z")
    caption: str = Field(..., min_length=1, max_length=2200)
    hashtags: Optional[List[str]] = None
    render_config: Optional[RenderConfig] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, v: List[str]) -> List[str]:
        allowed = {"tiktok", "instagram", "youtube", "youtube_shorts", "instagram_reels"}
        for p in v:
            if p not in allowed:
                raise ValueError(f"platform no soportada: {p}. Permitidas: {sorted(allowed)}")
        return v

    @field_validator("scheduled_at")
    @classmethod
    def validate_iso(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception as e:
            raise ValueError(f"scheduled_at debe ser ISO8601: {e}")
        return v

    model_config = {"extra": "forbid"}


class AudioFeatures(BaseModel):
    video_id: str
    duration_seconds: float = Field(..., ge=0)
    rms_curve: Optional[List[float]] = None
    events: List[Dict[str, Any]] = Field(default_factory=list, description="Eventos detectados por audio_analyzer")
    viral_moments: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class AutopilotJobStatus(str, Enum):
    pending = "pending"
    transcribing = "transcribing"
    analyzing_audio = "analyzing_audio"
    scoring = "scoring"
    rendering = "rendering"
    ready = "ready"
    publishing = "publishing"
    completed = "completed"
    failed = "failed"


class AutopilotJob(BaseModel):
    job_id: str
    video_id: str
    status: AutopilotJobStatus = AutopilotJobStatus.pending
    progress: int = Field(default=0, ge=0, le=100)
    transcript: Optional[TranscriptData] = None
    audio_features: Optional[AudioFeatures] = None
    candidates: List[ViralClipCandidate] = Field(default_factory=list)
    error: Optional[str] = None

    model_config = {"extra": "allow"}
