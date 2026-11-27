"""Descarga segura y acotada de videos desde URLs públicas mediante yt-dlp."""

from __future__ import annotations

import ipaddress
import re
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yt_dlp


class InvalidVideoUrl(ValueError):
    """La URL no es HTTP(S) o apunta a un host no público."""


class DownloadTooLarge(Exception):
    """La descarga supera el límite de tamaño configurado."""


class VideoDownloadFailed(Exception):
    """yt-dlp no pudo producir un archivo de video válido."""

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason.lower()


@dataclass(frozen=True)
class DownloadedVideo:
    filepath: Path
    filename: str
    duration_seconds: float | None


_DNS_NAME = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
    r"(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*\Z",
    re.IGNORECASE,
)
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".test", ".invalid", ".example")
_BLOCKED_HOSTS = {"localhost", "local", "internal", "test", "invalid", "example", "metadata.google.internal"}
_VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm", ".flv", ".mpeg", ".mpg", ".3gp"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidVideoUrl(message)


def _parse_url(raw_url: str):
    value = raw_url.strip()
    _require(bool(value), "La URL del video no puede estar vacía")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise InvalidVideoUrl("La URL del video no es válida") from exc
    return parsed, port


def _validate_scheme(scheme: str) -> None:
    _require(scheme.lower() in {"http", "https"}, "La URL debe usar http o https")


def _validate_port(scheme: str, port: int | None) -> None:
    expected_port = 443 if scheme.lower() == "https" else 80
    _require(port in {None, expected_port}, "La URL debe usar el puerto HTTP/HTTPS estándar")


def _validate_resolved_host(hostname: str, port: int) -> None:
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise InvalidVideoUrl("El host de la URL no se puede resolver") from exc
    addresses = {ipaddress.ip_address(record[4][0]) for record in records}
    _require(bool(addresses) and all(address.is_global for address in addresses), "El host debe ser público")


def _validate_public_host(hostname: str, port: int) -> None:
    try:
        host = hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise InvalidVideoUrl("La URL debe incluir un host válido") from exc
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        _require(bool(_DNS_NAME.fullmatch(host)), "La URL debe incluir un host válido")
        _require(host not in _BLOCKED_HOSTS, "No se permiten hosts locales")
        _require(not host.endswith(_BLOCKED_SUFFIXES), "No se permiten hosts locales")
        _validate_resolved_host(host, port)
        return
    _require(address.is_global, "No se permiten direcciones IP privadas o reservadas")


def validate_video_url(raw_url: str) -> str:
    parsed, port = _parse_url(raw_url)
    _validate_scheme(parsed.scheme)
    _require(bool(parsed.hostname), "La URL debe incluir un host válido")
    _require(parsed.username is None and parsed.password is None, "La URL no puede incluir credenciales")
    _validate_port(parsed.scheme, port)
    _validate_public_host(parsed.hostname or "", port or (443 if parsed.scheme == "https" else 80))
    return parsed.geturl()


def _progress_hook(max_file_size: int, exceeded: list[bool]):
    def check_progress(progress: dict) -> None:
        downloaded = progress.get("downloaded_bytes") or 0
        if downloaded > max_file_size:
            exceeded[0] = True
            raise yt_dlp.utils.DownloadError("El archivo supera el tamaño máximo permitido")

    return check_progress


def _download_options(output_template: Path, max_file_size: int, progress_hook) -> dict:
    return {
        "format": "best[ext=mp4]/best",
        "outtmpl": str(output_template),
        "noplaylist": True,
        "max_filesize": max_file_size,
        "merge_output_format": "mp4",
        "socket_timeout": 20,
        "retries": 1,
        "fragment_retries": 1,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
    }


def _extract_info(url: str, options: dict, exceeded: list[bool]) -> dict:
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
    except Exception as exc:
        if exceeded[0]:
            raise DownloadTooLarge("El video supera el tamaño máximo permitido") from exc
        raise VideoDownloadFailed("yt-dlp no pudo descargar el video", str(exc)) from exc
    if not isinstance(info, dict):
        raise VideoDownloadFailed("yt-dlp no devolvió metadatos del video")
    return info


def _is_owned_video_file(candidate: Path, upload_dir: Path, prefix: str) -> bool:
    return (
        candidate.name.startswith(prefix)
        and candidate.suffix.lower() in _VIDEO_SUFFIXES
        and candidate.parent.resolve() == upload_dir.resolve()
        and candidate.is_file()
    )


def _locate_download(info: dict, upload_dir: Path, prefix: str) -> Path:
    reported_path = info.get("filepath")
    if reported_path:
        candidate = Path(reported_path)
        if _is_owned_video_file(candidate, upload_dir, prefix):
            return candidate
    candidates = [
        path for path in upload_dir.glob(f"{prefix}.*") if _is_owned_video_file(path, upload_dir, prefix)
    ]
    if not candidates:
        raise VideoDownloadFailed("yt-dlp no generó un archivo de video")
    return max(candidates, key=lambda path: path.stat().st_size)


def _cleanup_download(upload_dir: Path, prefix: str) -> None:
    for path in upload_dir.glob(f"{prefix}.*"):
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


def _safe_filename(title: object, prefix: str, suffix: str) -> str:
    cleaned = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', " ", str(title or "video"))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")[:100] or "video"
    return f"{cleaned}-{prefix[:8]}{suffix.lower()}"


def _duration_seconds(info: dict) -> float | None:
    value = info.get("duration")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _result_from_download(info: dict, upload_dir: Path, prefix: str, max_file_size: int) -> DownloadedVideo:
    filepath = _locate_download(info, upload_dir, prefix)
    file_size = filepath.stat().st_size
    if file_size <= 0:
        raise VideoDownloadFailed("yt-dlp generó un archivo vacío")
    if file_size > max_file_size:
        raise DownloadTooLarge("El video supera el tamaño máximo permitido")
    return DownloadedVideo(
        filepath=filepath,
        filename=_safe_filename(info.get("title"), prefix, filepath.suffix),
        duration_seconds=_duration_seconds(info),
    )


def download_video_from_url(raw_url: str, upload_dir: Path, max_file_size: int) -> DownloadedVideo:
    """Valida y descarga un único video, limpiando cualquier archivo parcial ante fallo."""
    url = validate_video_url(raw_url)
    prefix = uuid.uuid4().hex
    exceeded = [False]
    output_template = upload_dir / f"{prefix}.%(ext)s"
    options = _download_options(output_template, max_file_size, _progress_hook(max_file_size, exceeded))
    try:
        info = _extract_info(url, options, exceeded)
        return _result_from_download(info, upload_dir, prefix, max_file_size)
    except (DownloadTooLarge, VideoDownloadFailed):
        _cleanup_download(upload_dir, prefix)
        raise
    except Exception as exc:
        _cleanup_download(upload_dir, prefix)
        raise VideoDownloadFailed("No se pudo completar la descarga del video") from exc
