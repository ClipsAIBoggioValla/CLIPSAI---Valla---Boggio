from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, Callable

import pytest

from backend.core.security import ssrf_guard
from backend_fastapi.app.routers import videos as videos_router
from backend_fastapi.app.routers import jobs as jobs_router
from backend_fastapi.app.services import ytdlp_service
from backend_fastapi.app.models import Clip
from _fixtures import build_client


def _allow_public_test_host(monkeypatch: pytest.MonkeyPatch) -> None:
    record = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    monkeypatch.setattr(ytdlp_service.socket, "getaddrinfo", lambda *_args, **_kwargs: [record])
    monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", lambda *_args, **_kwargs: [record])


@pytest.fixture(autouse=True)
def _mock_job_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs_router, "run_job_safely", lambda _job_id: None)


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
    assert db.commits == 2
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

    assert response.status_code in (400, 403, 422)


def test_from_url_rechaza_dominio_que_resuelve_a_ip_privada(client, monkeypatch) -> None:
    record = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.12", 443))
    monkeypatch.setattr(ytdlp_service.socket, "getaddrinfo", lambda *_args, **_kwargs: [record])
    monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", lambda *_args, **_kwargs: [record])
    response = client.post(
        "/api/videos/from-url",
        json={"url": "https://www.youtube.com/watch?v=abc123"},
    )

    assert response.status_code == 403


def test_from_url_rechaza_dominio_fuera_de_whitelist(client) -> None:
    response = client.post("/api/videos/from-url", json={"url": "https://media.example.org/video.mp4"})

    assert response.status_code == 422
    assert "Dominio no permitido" in response.json()["detail"]


@pytest.mark.parametrize(
    ("reason", "hint"),
    [
        ("Private video", "privado"),
        ("age-restricted", "restricción por edad"),
        ("not available in your country", "geobloqueado"),
        ("duration limit exceeded", "límite de duración"),
    ],
)
def test_from_url_explica_como_resolver_restricciones_de_descarga(client, monkeypatch, tmp_path, reason, hint) -> None:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    _allow_public_test_host(monkeypatch)

    def extract(_options: dict[str, Any]) -> dict[str, Any]:
        raise ytdlp_service.yt_dlp.utils.DownloadError(reason)

    _mock_youtube_dl(monkeypatch, extract)
    response = client.post("/api/videos/from-url", json={"url": "https://www.youtube.com/watch?v=abc123"})

    assert response.status_code == 422
    assert hint in response.json()["detail"]


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


def test_from_url_crea_job_y_clips_con_descarga_y_pipeline_mockeados(
    client, db, user, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    _allow_public_test_host(monkeypatch)

    def extract(options: dict[str, Any]) -> dict[str, Any]:
        filepath = Path(options["outtmpl"].replace("%(ext)s", "mp4"))
        filepath.write_bytes(b"mocked source video")
        return {"filepath": str(filepath), "title": "E2E", "duration": 45}

    _mock_youtube_dl(monkeypatch, extract)

    def fake_pipeline(job_id: str) -> None:
        job = next(item for item in db.added if type(item).__name__ == "Job")
        assert str(job.id) == job_id
        db.add(Clip(video_id=job.video_id, job_id=job.id, title="Clip E2E", start_time=2, end_time=12, score=9, status="ready"))

    monkeypatch.setattr(jobs_router, "run_job_safely", fake_pipeline)
    response = client.post("/api/videos/from-url", json={"url": "https://www.youtube.com/watch?v=abc123"})

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "pending"
    assert result["job_id"]
    assert any(type(item).__name__ == "Job" for item in db.added)
    clips = [item for item in db.added if type(item).__name__ == "Clip"]
    assert len(clips) == 1
    assert clips[0].title == "Clip E2E"
    assert str(clips[0].video_id) == result["id"]
