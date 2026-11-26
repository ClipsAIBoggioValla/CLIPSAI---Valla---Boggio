from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, Callable

import pytest

from backend_fastapi.app.routers import videos as videos_router
from backend_fastapi.app.services import ytdlp_service
from _fixtures import build_client


def _allow_public_test_host(monkeypatch: pytest.MonkeyPatch) -> None:
    record = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    monkeypatch.setattr(ytdlp_service.socket, "getaddrinfo", lambda *_args, **_kwargs: [record])


def _mock_youtube_dl(monkeypatch: pytest.MonkeyPatch, extract_info: Callable[..., dict[str, Any]]) -> None:
    class FakeYoutubeDL:
        def __init__(self, options: dict[str, Any]) -> None:
            self.options = options

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, Any]:
            assert url == "https://www.youtube.com/watch?v=abc123"
            assert download is True
            return extract_info(self.options)

    monkeypatch.setattr(ytdlp_service.yt_dlp, "YoutubeDL", FakeYoutubeDL)


def test_from_url_201_descarga_y_persiste_video(client, db, user, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    _allow_public_test_host(monkeypatch)

    def extract(options: dict[str, Any]) -> dict[str, Any]:
        filepath = Path(options["outtmpl"].replace("%(ext)s", "mp4"))
        filepath.write_bytes(b"video bytes")
        return {"filepath": str(filepath), "title": "Mi video de prueba", "duration": 92.5}

    _mock_youtube_dl(monkeypatch, extract)
    response = client.post(
        "/api/videos/from-url",
        json={"url": "https://www.youtube.com/watch?v=abc123"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["filename"].startswith("Mi video de prueba-")
    assert db.commits == 1
    saved_video = db.added[0]
    assert saved_video.user_id == user.id
    assert saved_video.duration_seconds == 92.5
    assert Path(saved_video.filepath).read_bytes() == b"video bytes"


@pytest.mark.parametrize(
    "url",
    ["", "ftp://example.com/video.mp4", "http://127.0.0.1/video.mp4", "http://[::1]/video.mp4"],
)
def test_from_url_rechaza_url_invalida(client, url: str) -> None:
    response = client.post("/api/videos/from-url", json={"url": url})

    assert response.status_code in (400, 422)


def test_from_url_rechaza_dominio_que_resuelve_a_ip_privada(client, monkeypatch) -> None:
    record = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.12", 443))
    monkeypatch.setattr(ytdlp_service.socket, "getaddrinfo", lambda *_args, **_kwargs: [record])
    response = client.post(
        "/api/videos/from-url",
        json={"url": "https://www.youtube.com/watch?v=abc123"},
    )

    assert response.status_code == 400


def test_from_url_502_y_limpia_archivo_parcial(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    _allow_public_test_host(monkeypatch)

    def extract(options: dict[str, Any]) -> dict[str, Any]:
        partial = Path(options["outtmpl"].replace("%(ext)s", "mp4.part"))
        partial.write_bytes(b"partial")
        raise ytdlp_service.yt_dlp.utils.DownloadError("fallo de prueba")

    _mock_youtube_dl(monkeypatch, extract)
    response = client.post(
        "/api/videos/from-url",
        json={"url": "https://www.youtube.com/watch?v=abc123"},
    )

    assert response.status_code == 502
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("file_content", [None, b""])
def test_from_url_falla_si_archivo_no_existe_o_esta_vacio(client, monkeypatch, tmp_path, file_content) -> None:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    _allow_public_test_host(monkeypatch)

    def extract(options: dict[str, Any]) -> dict[str, Any]:
        filepath = Path(options["outtmpl"].replace("%(ext)s", "mp4"))
        if file_content is not None:
            filepath.write_bytes(file_content)
        return {"filepath": str(filepath), "title": "Video sin datos"}

    _mock_youtube_dl(monkeypatch, extract)
    response = client.post(
        "/api/videos/from-url",
        json={"url": "https://www.youtube.com/watch?v=abc123"},
    )

    assert response.status_code == 502
    assert list(tmp_path.iterdir()) == []


def test_from_url_rechaza_archivo_mayor_al_limite_y_lo_limpia(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(videos_router, "MAX_FILE_SIZE", 4)
    _allow_public_test_host(monkeypatch)

    def extract(options: dict[str, Any]) -> dict[str, Any]:
        filepath = Path(options["outtmpl"].replace("%(ext)s", "mp4"))
        filepath.write_bytes(b"too large")
        return {"filepath": str(filepath), "title": "Oversize"}

    _mock_youtube_dl(monkeypatch, extract)
    response = client.post(
        "/api/videos/from-url",
        json={"url": "https://www.youtube.com/watch?v=abc123"},
    )

    assert response.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_from_url_requiere_autenticacion(db) -> None:
    anonymous_client = build_client(db, use_real_auth=True)
    try:
        response = anonymous_client.post(
            "/api/videos/from-url",
            json={"url": "https://www.youtube.com/watch?v=abc123"},
        )
    finally:
        anonymous_client.close()

    assert response.status_code in (401, 403)
