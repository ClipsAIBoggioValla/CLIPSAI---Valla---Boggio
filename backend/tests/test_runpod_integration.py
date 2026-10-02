from __future__ import annotations

import asyncio
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from backend.handler import process_video_job
from backend_fastapi.app.routers.videos import (
    ProcessVideoRequest,
    UploadUrlRequest,
    generate_upload_url,
    process_video,
)
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


class PresignedUploadUrlTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_ENDPOINT_URL": "https://s3.example.test",
            "AWS_REGION": "auto",
            "BUCKET_NAME": "clipsai-test",
        },
        clear=False,
    )
    def test_returns_presigned_put_url_and_unique_key(self) -> None:
        s3_client = Mock()
        s3_client.generate_presigned_url.return_value = "https://s3.example.test/upload"
        boto3_module = types.ModuleType("boto3")
        boto3_module.client = Mock(return_value=s3_client)
        config_module = types.ModuleType("botocore.config")
        config_module.Config = Mock(return_value="s3v4-config")
        botocore_module = types.ModuleType("botocore")
        botocore_module.config = config_module

        with patch.dict(
            sys.modules,
            {"boto3": boto3_module, "botocore": botocore_module, "botocore.config": config_module},
        ):
            result = asyncio.run(
                generate_upload_url(UploadUrlRequest(file_name="video.mp4", file_type="video/mp4"))
            )

        self.assertEqual(result["upload_url"], "https://s3.example.test/upload")
        self.assertRegex(result["file_key"], r"^uploads/[0-9a-f-]{36}\.mp4$")
        self.assertEqual(s3_client.generate_presigned_url.call_args.kwargs["ExpiresIn"], 900)


class RunPodOrchestrationTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_ENDPOINT_URL": "https://s3.example.test",
            "BUCKET_NAME": "clipsai-test",
        },
        clear=False,
    )
    @patch("backend_fastapi.app.services.runpod_service.process_video_via_runpod")
    def test_file_key_is_presigned_for_read_then_submitted_to_runpod(self, runpod_call: Mock) -> None:
        s3_client = Mock()
        s3_client.generate_presigned_url.return_value = "https://s3.example.test/presigned-read"
        boto3_module = types.ModuleType("boto3")
        boto3_module.client = Mock(return_value=s3_client)
        config_module = types.ModuleType("botocore.config")
        config_module.Config = Mock(return_value="s3v4-config")
        botocore_module = types.ModuleType("botocore")
        botocore_module.config = config_module
        runpod_call.return_value = {"status": "COMPLETED", "clips": [{"title": "Test clip"}]}

        with patch.dict(
            sys.modules,
            {"boto3": boto3_module, "botocore": botocore_module, "botocore.config": config_module},
        ):
            result = process_video(ProcessVideoRequest(file_key="uploads/video.mp4"))

        self.assertEqual(result["clips"][0]["title"], "Test clip")
        self.assertEqual(s3_client.generate_presigned_url.call_args.kwargs["ClientMethod"], "get_object")
        self.assertEqual(s3_client.generate_presigned_url.call_args.kwargs["ExpiresIn"], 3600)
        runpod_call.assert_called_once_with(
            "https://s3.example.test/presigned-read",
            transcription_url=None,
            transcription_text=None,
            video_id=None,
        )

    @patch("backend_fastapi.app.services.runpod_service.process_video_via_runpod")
    def test_direct_video_url_skips_s3_presigning(self, runpod_call: Mock) -> None:
        runpod_call.return_value = {"status": "COMPLETED", "clips": []}

        result = process_video(ProcessVideoRequest(video_url="https://media.example/video.mp4"))

        self.assertEqual(result["status"], "COMPLETED")
        runpod_call.assert_called_once_with(
            "https://media.example/video.mp4",
            transcription_url=None,
            transcription_text=None,
            video_id=None,
        )

    def test_process_request_requires_exactly_one_video_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactamente uno"):
            ProcessVideoRequest()
        with self.assertRaisesRegex(ValueError, "exactamente uno"):
            ProcessVideoRequest(file_key="uploads/video.mp4", video_url="https://media.example/video.mp4")


if __name__ == "__main__":
    unittest.main()
