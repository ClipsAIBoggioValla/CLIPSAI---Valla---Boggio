from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from backend.handler import process_video_job
from backend_fastapi.app.services.runpod_service import RunPodError, process_video_via_runpod


class RunPodHandlerTests(unittest.TestCase):
    def test_handler_downloads_video_and_returns_json_metadata(self) -> None:
        engine = types.ModuleType("backend_fastapi.app.services.engine")
        engine.run_clip_engine = Mock(
            return_value={
                "engine": "native_claude",
                "clips": [
                    {"inicio": "00:00:10", "fin": "00:00:35", "score": 8, "titulo": "Momento clave"}
                ],
                "transcription_segments": [{"text": "transcript"}],
            }
        )

        def fake_download(_url, destination, _max_bytes):
            destination.write_bytes(b"video")

        with (
            patch.dict(sys.modules, {"backend_fastapi.app.services.engine": engine}),
            patch("backend.handler._download_input", side_effect=fake_download),
        ):
            result = process_video_job(
                {"input": {"video_url": "https://media.example/video.mp4", "video_id": "video-123"}}
            )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["video_id"], "video-123")
        self.assertEqual(result["clip_count"], 1)
        self.assertEqual(result["clips"][0]["titulo"], "Momento clave")
        self.assertEqual(result["transcription_segments_count"], 1)
        engine.run_clip_engine.assert_called_once()

    def test_handler_requires_video_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "video_url"):
            process_video_job({"input": {}})


class RunPodClientTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"RUNPOD_API_KEY": "test-key", "RUNPOD_ENDPOINT_ID": "endpoint-123"},
        clear=False,
    )
    @patch("backend_fastapi.app.services.runpod_service.requests.post")
    def test_client_calls_runsync_with_bearer_and_video_url(self, post: Mock) -> None:
        response = Mock()
        response.json.return_value = {
            "id": "job-123",
            "status": "COMPLETED",
            "output": {"status": "COMPLETED", "clip_count": 1},
        }
        response.status_code = 200
        post.return_value = response

        result = process_video_via_runpod(
            "https://media.example/video.mp4", transcription_text="00:00:00 - Hola"
        )

        self.assertEqual(result, {"status": "COMPLETED", "clip_count": 1})
        args, kwargs = post.call_args
        self.assertTrue(args[0].endswith("/endpoint-123/runsync"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["json"]["input"]["video_url"], "https://media.example/video.mp4")

    @patch.dict(os.environ, {}, clear=True)
    def test_client_requires_api_key(self) -> None:
        with self.assertRaisesRegex(RunPodError, "RUNPOD_API_KEY"):
            process_video_via_runpod("https://media.example/video.mp4")


if __name__ == "__main__":
    unittest.main()
