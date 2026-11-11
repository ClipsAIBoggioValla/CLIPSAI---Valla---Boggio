from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.runpod_service import process_video_via_runpod, _decode_response, _raise_for_job_failure


def test_decode_response_ok() -> None:
    r = MagicMock()
    r.json.return_value = {"status": "COMPLETED"}
    r.status_code = 200
    r.text = "{}"
    out = _decode_response(r)
    assert out == {"status": "COMPLETED"}


def test_decode_response_bad() -> None:
    import pytest
    r = MagicMock()
    r.json.side_effect = ValueError("bad")
    r.status_code = 500
    r.text = "err"
    with pytest.raises(Exception):
        _decode_response(r)


def test_raise_for_job_failure_failed() -> None:
    import pytest
    with pytest.raises(Exception):
        _raise_for_job_failure({"status": "FAILED", "error": "boom"})


def test_raise_for_job_failure_ok() -> None:
    _raise_for_job_failure({"status": "COMPLETED"})


def test_process_video_via_runpod_completed() -> None:
    settings = ("k", "e", 10, 100, 1.0, "https://api.runpod.ai/v2")
    with patch("backend_fastapi.app.services.runpod_service._settings", return_value=settings), patch(
        "backend_fastapi.app.services.runpod_service.requests.post"
    ) as m:
        m.return_value = MagicMock(status_code=200, json=lambda: {"status": "COMPLETED", "output": {"clips": []}, "id": "j1"})
        m.return_value.raise_for_status = lambda: None
        out = process_video_via_runpod("http://v.mp4", video_id="v1")
    assert isinstance(out, (dict, type(None)))


def test_process_video_via_runpod_validation() -> None:
    import pytest
    with pytest.raises(ValueError):
        process_video_via_runpod("")
    with pytest.raises(ValueError):
        process_video_via_runpod("http://v.mp4", transcription_url="u", transcription_text="t")


def test_process_video_via_runpod_polling() -> None:
    settings = ("k", "e", 10, 100, 0.01, "https://api.runpod.ai/v2")
    with patch("backend_fastapi.app.services.runpod_service._settings", return_value=settings), patch(
        "backend_fastapi.app.services.runpod_service.requests.post"
    ) as mp, patch("backend_fastapi.app.services.runpod_service.requests.get") as mg, patch(
        "backend_fastapi.app.services.runpod_service.time.sleep"
    ):
        mp.return_value = MagicMock(status_code=200, json=lambda: {"status": "IN_PROGRESS", "id": "j1"}, raise_for_status=lambda: None)
        mg.return_value = MagicMock(status_code=200, json=lambda: {"status": "COMPLETED", "output": {"clips": []}}, raise_for_status=lambda: None)
        out = process_video_via_runpod("http://v.mp4")
    assert isinstance(out, (dict, type(None)))
