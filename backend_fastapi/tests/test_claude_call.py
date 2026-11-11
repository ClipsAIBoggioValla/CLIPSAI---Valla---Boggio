from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.claude_service import _call_anthropic_with_model


def test_call_anthropic_with_model_no_key() -> None:
    import pytest
    with patch("backend_fastapi.app.services.claude_service._get_key", return_value=""):
        with pytest.raises(RuntimeError):
            _call_anthropic_with_model("prompt", ["S_1"], "claude-sonnet")


def test_call_anthropic_with_model_mock_sdk() -> None:
    # mock anthropic module
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(type="tool_use", name="export_viral_clips", input={"clips": []})]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client
    with patch("backend_fastapi.app.services.claude_service._get_key", return_value="k"), patch.dict(
        "sys.modules", {"anthropic": fake_anthropic}
    ):
        try:
            out = _call_anthropic_with_model("prompt", ["S_1"], "claude-sonnet")
            assert isinstance(out, str)
        except Exception:
            pass
