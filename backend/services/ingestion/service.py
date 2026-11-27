from __future__ import annotations

import uuid
import os
from pathlib import Path
from urllib.parse import urlsplit

from backend.core.security.ssrf_guard import validate_url


ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_BYTES = 500 * 1024 * 1024
_ALLOWED_DOMAINS = ("youtube.com", "youtu.be", "twitch.tv")


def _source_host_allowed(url: str) -> bool:
    """Permite dominios soportados y solo el host público de R2 configurado."""
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    r2_url = os.getenv("R2_PUBLIC_URL", "").strip()
    r2_host = urlsplit(r2_url if "://" in r2_url else f"https://{r2_url}").hostname if r2_url else ""
    domains = (*_ALLOWED_DOMAINS, r2_host or "")
    return any(host == domain or host.endswith(f".{domain}") for domain in domains if domain)


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


async def ingest_ytdlp(url: str, upload_dir: str = "storage/uploads") -> str:
    validate_url(url)
    if not _source_host_allowed(url):
        raise ValueError("Dominio no permitido para ingesta por URL")
    try:
        import yt_dlp  # type: ignore
    except ImportError:
        raise RuntimeError("yt-dlp no instalado. pip install yt-dlp")
    video_id = str(uuid.uuid4())
    out = Path(upload_dir) / f"{video_id}.%(ext)s"
    out.parent.mkdir(parents=True, exist_ok=True)
    ydl_opts = {"outtmpl": str(out), "format": "best[ext=mp4]/best", "merge_output_format": "mp4", "noplaylist": True}
    import asyncio

    def _dl() -> None:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
            ydl.download([url])

    await asyncio.to_thread(_dl)
    return video_id
