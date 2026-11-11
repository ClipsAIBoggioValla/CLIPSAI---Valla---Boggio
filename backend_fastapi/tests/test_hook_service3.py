from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.hook_service import detect_hooks, detect_hooks_from_transcript_file


def test_detect_hooks_non_mock_mocked_llm() -> None:
    segs = [{"start": 0, "end": 30, "text": "hola"}]
    raw = '{"clips": [{"title": "T", "start_time": 0, "end_time": 30, "viral_score": 80, "hook": {"text": "h", "start_time": 0, "end_time": 4, "duration": 4}}]}'
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}, clear=False), patch(
        "backend_fastapi.app.services.hook_service._call_llm", return_value=raw
    ):
        out = detect_hooks(segs, duration_hint=30.0, mock=False)
    assert isinstance(out, list)


def test_detect_hooks_from_transcript_file_mock(tmp_path: Path) -> None:
    p = tmp_path / "t.txt"
    p.write_text("0:00 - Hola", encoding="utf-8")
    raw = '{"clips": [{"title": "T", "start_time": 0, "end_time": 30, "viral_score": 80, "hook": {"text": "h", "start_time": 0, "end_time": 4, "duration": 4}}]}'
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}, clear=False), patch(
        "backend_fastapi.app.services.hook_service._call_llm", return_value=raw
    ):
        out = detect_hooks_from_transcript_file(p, mock=False)
    assert isinstance(out, list)
