from __future__ import annotations

import pytest
from unittest.mock import patch

from backend_fastapi.app.services import hook_service as hs


def test_detect_hooks_no_provider():
    with pytest.raises(RuntimeError) as ei:
        hs.detect_hooks([{"start": 0, "end": 2, "text": "hola"}], mock=False)
    assert "Error en API de Claude" in str(ei.value)


def test_detect_hooks_anthropic_error_propagates():
    def boom(prompt):
        raise RuntimeError("Error en la API de Claude: timeout")

    with patch.object(hs, "_get_provider", lambda: "anthropic"), patch.object(hs, "_call_llm", boom), patch.object(
        hs, "_build_hook_prompt", return_value="p"
    ), patch.object(hs, "_format_transcript", return_value="t"):
        with pytest.raises(RuntimeError) as ei:
            hs.detect_hooks([{"start": 0, "end": 2, "text": "hola"}], mock=False)
    assert "Error en la API de Claude" in str(ei.value)


def test_detect_hooks_empty_transcript(monkeypatch):
    monkeypatch.setattr(hs, "_get_provider", lambda: "anthropic")
    with patch.object(hs, "_call_llm", return_value='{"clips": []}'), patch.object(
        hs, "_build_hook_prompt", return_value="p"
    ), patch.object(hs, "_format_transcript", return_value=""):
        with pytest.raises(RuntimeError) as ei:
            hs.detect_hooks([{"start": 0, "end": 2, "text": "hola"}], mock=False)
    assert "Error en API de Claude" in str(ei.value)
