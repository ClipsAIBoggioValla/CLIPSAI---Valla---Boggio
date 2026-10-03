from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.testclient import TestClient

from backend_fastapi.app.routers import videos
from backend_fastapi.app.services import runpod_service


@pytest.fixture
def e2e_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, dict[str, bytes]]]:
    stored_objects: dict[str, bytes] = {}

    class FakeS3Client:
        def generate_presigned_url(self, *, ClientMethod, Params, ExpiresIn):
            assert ClientMethod in {"put_object", "get_object"}
            assert Params["Bucket"] == "clipsai-e2e"
            if ClientMethod == "put_object":
                assert ExpiresIn == 900
            else:
                assert ExpiresIn == 3600
            return f"http://testserver/mock-r2/{Params['Key']}"

    app = FastAPI()
    app.include_router(videos.upload_url_router)

    @app.put("/mock-r2/{file_key:path}")
    async def upload_to_fake_r2(file_key: str, request: Request) -> Response:
        stored_objects[file_key] = await request.body()
        return Response(status_code=200)

    @app.get("/mock-r2/{file_key:path}")
    def read_from_fake_r2(file_key: str) -> Response:
        if file_key not in stored_objects:
            return Response(status_code=404)
        return Response(content=stored_objects[file_key], media_type="video/mp4")

    monkeypatch.setenv("BUCKET_NAME", "clipsai-e2e")
    monkeypatch.setattr(videos, "get_s3_client", FakeS3Client)
    client = TestClient(app)
    yield client, stored_objects
    client.close()


def test_direct_r2_upload_then_runpod_processing_returns_clip_metadata(
    e2e_client: tuple[TestClient, dict[str, bytes]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, stored_objects = e2e_client
    expected_video = b"fake mp4 content for integration test"

    upload_url_response = client.post(
        "/api/videos/upload-url",
        json={"file_name": "podcast.mp4", "file_type": "video/mp4"},
    )
    assert upload_url_response.status_code == 200
    signed_upload = upload_url_response.json()
    assert signed_upload["upload_url"].startswith("http://testserver/mock-r2/uploads/")
    assert signed_upload["file_key"].startswith("uploads/")

    put_response = client.put(
        signed_upload["upload_url"],
        content=expected_video,
        headers={"Content-Type": "video/mp4"},
    )
    assert put_response.status_code == 200
    assert stored_objects[signed_upload["file_key"]] == expected_video

    def fake_runpod(video_url: str, **_kwargs):
        # Simulate RunPod downloading the one-hour presigned GET URL from R2.
        downloaded = client.get(video_url)
        assert downloaded.status_code == 200
        assert downloaded.content == expected_video
        return {
            "status": "COMPLETED",
            "engine": "native_claude",
            "clip_count": 1,
            "clips": [
                {
                    "title": "La revelación del partido",
                    "start_time": 12.5,
                    "end_time": 42.5,
                    "score": 9,
                }
            ],
        }

    monkeypatch.setattr(runpod_service, "process_video_via_runpod", fake_runpod)
    process_response = client.post(
        "/api/videos/process",
        json={"file_key": signed_upload["file_key"]},
    )

    assert process_response.status_code == 200
    result = process_response.json()
    assert result["status"] == "COMPLETED"
    assert result["clip_count"] == 1
    assert isinstance(result["clips"], list)
    clip = result["clips"][0]
    assert isinstance(clip["title"], str)
    assert isinstance(clip["start_time"], (int, float))
    assert isinstance(clip["end_time"], (int, float))
    assert isinstance(clip["score"], (int, float))


def test_processing_accepts_direct_video_url(e2e_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _stored_objects = e2e_client
    runpod_call: dict[str, str] = {}

    def fake_runpod(video_url: str, **_kwargs):
        runpod_call["video_url"] = video_url
        return {"status": "COMPLETED", "clips": []}

    monkeypatch.setattr(runpod_service, "process_video_via_runpod", fake_runpod)
    response = client.post(
        "/api/videos/process",
        json={"video_url": "https://media.example.test/direct.mp4"},
    )

    assert response.status_code == 200
    assert runpod_call["video_url"] == "https://media.example.test/direct.mp4"


def test_runpod_failure_is_returned_as_gateway_error(e2e_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _stored_objects = e2e_client

    def fail_runpod(*_args, **_kwargs):
        raise runpod_service.RunPodError("worker falló")

    monkeypatch.setattr(runpod_service, "process_video_via_runpod", fail_runpod)
    response = client.post(
        "/api/videos/process",
        json={"video_url": "https://media.example.test/direct.mp4"},
    )

    assert response.status_code == 502
    assert "worker falló" in response.json()["detail"]
