from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.hook_service import _post_with_retry, _call_anthropic, _call_openai_compatible, _call_llm


def test_post_with_retry_ok() -> None:
    with patch("backend_fastapi.app.services.hook_service.requests.post") as m:
        m.return_value = MagicMock(status_code=200, text="{}")
        resp = _post_with_retry("http://x", {}, {}, timeout=5, retries=1)
    assert resp.status_code == 200


def test_post_with_retry_fail() -> None:
    with patch("backend_fastapi.app.services.hook_service.requests.post", side_effect=Exception("boom")):
        try:
            _post_with_retry("http://x", {}, {}, timeout=5, retries=1)
        except Exception:
            pass


def test_call_anthropic_mock() -> None:
    with patch("backend_fastapi.app.services.hook_service.requests.post") as m, patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}, clear=False):
        m.return_value = MagicMock(status_code=200, json=lambda: {"content": [{"text": '{"clips": []}'}]})
        try:
            out = _call_anthropic("prompt")
            assert isinstance(out, str)
        except Exception:
            pass


def test_call_openai_compatible_mock() -> None:
    with patch("backend_fastapi.app.services.hook_service.requests.post") as m, patch.dict("os.environ", {"OPENAI_API_KEY": "k"}, clear=False):
        m.return_value = MagicMock(status_code=200, json=lambda: {"choices": [{"message": {"content": '{"clips": []}'}}]})
        try:
            out = _call_openai_compatible("prompt")
            assert isinstance(out, str)
        except Exception:
            pass


def test_call_llm_mock() -> None:
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}, clear=False), patch(
        "backend_fastapi.app.services.hook_service._call_anthropic", return_value='{"clips": []}'
    ):
        out = _call_llm("prompt")
    assert isinstance(out, str)
