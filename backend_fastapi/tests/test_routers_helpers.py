from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend_fastapi.app.routers.jobs import (
    _meets_score_threshold,
    _parse_time_to_seconds,
    _parse_transcript_text_to_segments,
    _fallback_result,
    _extractmeaningful_title,
    _segments_to_fallback_title,
    _set_progress,
)
from backend_fastapi.app.routers.export import (
    _resolve_transcript,
    _build_csv,
    _build_json_payload,
    _export_response,
    _handle_export,
)
from backend_fastapi.app.routers.users import _to_user_response, _apply_update


@pytest.fixture
def mock_db():
    return MagicMock()


def _mk_clip(**kw):
    base = dict(
        id=uuid.uuid4(),
        video_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        title="T",
        start_time=0.0,
        end_time=5.0,
        score=8,
        tags=None,
        storage_path=None,
        file_path=None,
        stream_url=None,
        duration=None,
        has_ass=False,
        has_hook=False,
        status="COMPLETED",
        published_platform=None,
        social_post_id=None,
        social_post_url=None,
        published_at=None,
        publication_status=None,
        social_network=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_meets_score_threshold() -> None:
    assert _meets_score_threshold(None) is True
    assert _meets_score_threshold(0.59) is False
    assert _meets_score_threshold(0.6) is True
    assert _meets_score_threshold(6.0) is True
    assert _meets_score_threshold(5.9) is False
    assert _meets_score_threshold(8) is True
    assert _meets_score_threshold(60) is True
    assert _meets_score_threshold(59) is False
    assert _meets_score_threshold("abc") is True


def test_parse_time_to_seconds() -> None:
    assert _parse_time_to_seconds(None) == 0.0
    assert _parse_time_to_seconds("") == 0.0
    assert _parse_time_to_seconds(12.5) == 12.5
    assert _parse_time_to_seconds(3) == 3.0
    assert _parse_time_to_seconds("0:30") == 30.0
    assert _parse_time_to_seconds("1:02:03") == 3723.0
    assert _parse_time_to_seconds("bad") == 0.0


def test_parse_transcript_text_to_segments() -> None:
    segs = _parse_transcript_text_to_segments("0:00 - Hola mundo\n0:30 - Segundo segmento")
    assert isinstance(segs, list)
    assert len(segs) > 0


def test_fallback_result_raises() -> None:
    with pytest.raises(RuntimeError):
        _fallback_result(None)


def test_extractmeaningful_title() -> None:
    t = _extractmeaningful_title("y entonces nos vemos mañana que fue bueno")
    assert isinstance(t, str) and len(t) > 0
    assert _extractmeaningful_title("") == "Clip destacado"
    assert _extractmeaningful_title(None) == "Clip destacado"


def test_segments_to_fallback_title() -> None:
    segs = [{"start": 0.0, "end": 5.0, "text": "Hola que tal"}]
    t = _segments_to_fallback_title(segs, 0.0, 10.0)
    assert isinstance(t, str) and len(t) > 0
    t2 = _segments_to_fallback_title([], 0.0, 10.0)
    assert t2 == "Clip destacado"


def test_set_progress_ok_and_err(mock_db) -> None:
    job = SimpleNamespace(id=uuid.uuid4(), progress=0)
    _set_progress(mock_db, job, 50)
    assert job.progress == 50
    job2 = SimpleNamespace(id=uuid.uuid4(), progress=0)
    _set_progress(mock_db, job2, 999)
    assert job2.progress == 100


def test_resolve_transcript() -> None:
    clip = _mk_clip(transcript="hola mundo")
    assert _resolve_transcript(clip, None) == "hola mundo"
    assert _resolve_transcript(clip, "fallback") == "hola mundo"
    clip2 = _mk_clip(transcript=None, tags={"transcript": "abc"})
    assert _resolve_transcript(clip2, None) == "abc"
    assert _resolve_transcript(_mk_clip(), "vt") == "vt"


def test_build_csv() -> None:
    c1 = _mk_clip(id=uuid.uuid4(), title="T1", score=8.0)
    c2 = _mk_clip(id=uuid.uuid4(), title="T2", score=None, tags={"transcript": "txt2"})
    csv_out = _build_csv([(c1, "trans1"), (c2, None)])
    assert "ID" in csv_out
    assert "trans1" in csv_out
    assert "T1" in csv_out


def test_build_json_payload() -> None:
    clip = _mk_clip(id=uuid.uuid4(), score=7.5, title="T")
    payload = _build_json_payload([(clip, "trans")])
    assert payload["total_clips"] == 1
    assert payload["clips"][0]["transcript"] == "trans"
    assert payload["avg_score"] == 7.5
    payload2 = _build_json_payload([(clip, "trans")], job_id=uuid.uuid4())
    assert "job_id" in payload2


def test_export_response() -> None:
    r = _export_response("hi", "text/csv", "f.csv")
    assert r.body == b"hi"
    assert r.media_type == "text/csv"


def test_handle_export_csv() -> None:
    clip = _mk_clip()
    r = _handle_export([(clip, "t")], "csv")
    assert r.media_type.startswith("text/csv")


def test_handle_export_json() -> None:
    clip = _mk_clip(score=8)
    r = _handle_export([(clip, "t")], "json")
    assert "application/json" in r.media_type


def test_to_user_response() -> None:
    u = SimpleNamespace(id=uuid.uuid4(), email="a@b.com", full_name="Nombre", avatar_url=None, theme_preference="dark", created_at=datetime.now(timezone.utc))
    resp = _to_user_response(u)
    assert str(resp.id) == str(u.id)
    assert resp.email == "a@b.com"
    assert resp.full_name == "Nombre"


def test_apply_update_no_payload() -> None:
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        _apply_update(SimpleNamespace(id=uuid.uuid4()), {}, None)
