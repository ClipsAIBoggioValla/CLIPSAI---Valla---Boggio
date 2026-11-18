from __future__ import annotations

import os
import uuid
from pathlib import Path

from backend.core.interfaces import IIngestionService


ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_TRANSCRIPT = {".txt", ".srt", ".vtt"}
MAX_BYTES = 500 * 1024 * 1024


class IngestionService(IIngestionService):
    def __init__(self, upload_dir: str = "storage/uploads") -> None:
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validar_extensiones(original_filename: str, transcript_path: str | None) -> str:
        """Valida extensiones de video y transcript; devuelve la extensión del video."""
        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_VIDEO:
            raise ValueError(f"Extensión video no soportada: {ext}")
        if transcript_path:
            t_ext = Path(transcript_path).suffix.lower()
            if t_ext not in ALLOWED_TRANSCRIPT:
                raise ValueError(f"Extensión transcript no soportada: {t_ext}")
        return ext

    def _mover_transcript(self, video_id: str, transcript_path: str | None) -> None:
        """Mueve el transcript al upload_dir si existe."""
        if transcript_path and Path(transcript_path).exists():
            t_dest = self.upload_dir / f"{video_id}_transcript{Path(transcript_path).suffix}"
            Path(transcript_path).replace(t_dest)

    async def ingest(self, file_path: str, original_filename: str, transcript_path: str | None = None) -> str:
        ext = self._validar_extensiones(original_filename, transcript_path)

        video_id = str(uuid.uuid4())
        dest = self.upload_dir / f"{video_id}{ext}"
        Path(file_path).replace(dest)

        self._mover_transcript(video_id, transcript_path)

        if dest.stat().st_size > MAX_BYTES:
            dest.unlink(missing_ok=True)
            raise ValueError("Video excede 500MB")

        return video_id
