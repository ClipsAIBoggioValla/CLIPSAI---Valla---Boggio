from __future__ import annotations

from backend_fastapi.app.services import hook_service as hs


def test_format_transcript_basic():
    out = hs._format_transcript([{"start": 0, "end": 2, "text": "hola mundo"}, {"start": 3, "end": 5, "text": "chau"}])
    assert isinstance(out, str)
    assert len(out) > 0


def test_build_hook_prompt():
    p = hs._build_hook_prompt("hola mundo", duration_hint=10.0)
    assert isinstance(p, str)


def test_parse_json_strict_valid():
    out = hs._parse_json_strict('{"a": 1}')
    assert out.get("a") == 1


def test_mock_hooks_basic():
    hooks = hs._mock_hooks([{"start": 0, "end": 2, "text": "hola"}])
    assert isinstance(hooks, list)
    assert len(hooks) >= 0


def test_detect_hooks_mock():
    hooks = hs.detect_hooks([{"start": 0, "end": 2, "text": "hola"}], mock=True)
    assert isinstance(hooks, list)


def test_detect_hooks_from_transcript_file(tmp_path):
    p = tmp_path / "t.ass"
    p.write_text("[Script]\n", encoding="utf-8")
    hooks = hs.detect_hooks_from_transcript_file(str(p), mock=True)
    assert isinstance(hooks, list)
