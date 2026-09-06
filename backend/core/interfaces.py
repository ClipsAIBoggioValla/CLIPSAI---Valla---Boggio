from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, List

from .schemas import (
    AudioFeatures,
    AutopilotJob,
    RenderConfig,
    ScheduledPost,
    TranscriptData,
    ViralClipCandidate,
)


class ITranscriber(ABC):
    @abstractmethod
    async def transcribe(self, video_path: str, language: str = "es") -> TranscriptData:
        ...


class IAudioAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, video_path: str, video_id: str) -> AudioFeatures:
        ...


class IIngestionService(ABC):
    @abstractmethod
    async def ingest(self, file_path: str, original_filename: str, transcript_path: str | None = None) -> str:
        """Guarda video crudo y retorna video_id. Track A owner."""
        ...


class IViralityEngine(ABC):
    @abstractmethod
    async def score(
        self, transcript: TranscriptData, audio: AudioFeatures, max_candidates: int = 10
    ) -> List[ViralClipCandidate]:
        ...

    @abstractmethod
    async def generate_report(self, candidate: ViralClipCandidate) -> dict:
        ...


class IRenderer(ABC):
    @abstractmethod
    async def render(
        self,
        video_path: str,
        candidate: ViralClipCandidate,
        transcript: TranscriptData,
        config: RenderConfig,
        output_path: str,
    ) -> str:
        """Renderiza clip vertical 1080x1920 con captions kinetic + auto-crop + brand kit. Retorna output_path."""
        ...


class IPublisher(ABC):
    @abstractmethod
    async def publish(self, clip_path: str, post: ScheduledPost) -> dict:
        ...

    @abstractmethod
    async def schedule(self, post: ScheduledPost) -> str:
        ...


class IJobOrchestrator(ABC):
    @abstractmethod
    async def create_job(self, video_id: str) -> AutopilotJob:
        ...

    @abstractmethod
    async def stream_progress(self, job_id: str) -> AsyncIterator[AutopilotJob]:
        """SSE stream de progreso para UI Autopilot."""
        ...

    @abstractmethod
    async def get_job(self, job_id: str) -> AutopilotJob:
        ...
