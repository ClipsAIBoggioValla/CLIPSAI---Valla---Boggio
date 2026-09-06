from __future__ import annotations

import uuid
from pathlib import Path

from backend.core.security.ssrf_guard import validate_url


ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_BYTES = 500 * 1024 * 1024


async def ingest_upload(file_path: str, original_filename: str, upload_dir: str = "storage/uploads") -> str:
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_VIDEO:
        raise ValueError(f"Extensión no soportada: {ext}")
    p = Path(file_path)
    if p.stat().st_size > MAX_BYTES:
        raise ValueError("Video excede 500MB")
    video_id = str(uuid.uuid4())
    dest = Path(upload_dir) / f"{video_id}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    p.replace(dest)
    return video_id


async def ingest_ytdlp(url: str) -> str:
    validate_url(url)
    try:
        import yt_dlp  # type: ignore
    except ImportError:
        raise RuntimeError("yt-dlp no instalado. pip install yt-dlp")
    video_id = str(uuid.uuid4())
    out = Path(f"storage/uploads/{video_id}.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ydl_opts = {"outtmpl": str(out), "format": "mp4/best"}
    import asyncio

    def _dl() -> None:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
            ydl.download([url])

    await asyncio.to_thread(_dl)
    return video_id
