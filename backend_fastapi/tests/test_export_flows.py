from __future__ import annotations

import uuid
from types import SimpleNamespace

from backend_fastapi.app.routers import export as export_router
from backend_fastapi.app.models import Usuario, Video, Job, Clip


def test_resolve_transcript_via_clip_attr():
    c = SimpleNamespace(transcript=None, transcript_text=None, transcription=None, text=None, tags={})
    assert export_router._resolve_transcript(c, None) == ""
    c2 = SimpleNamespace(transcript=None, transcript_text=None, transcription=None, text="hola mundo", tags={})
    assert export_router._resolve_transcript(c2, None) == "hola mundo"
    c3 = SimpleNamespace(transcript=None, transcript_text=None, transcription=None, text=None, tags={"transcript": "tag texto"})
    assert export_router._resolve_transcript(c3, None) == "tag texto"


def test_build_csv_basic():
    c = SimpleNamespace(id=uuid.uuid4(), title="T1", start_time=0.0, end_time=5.0, score=8.0, transcript=None)
    out = export_router._build_csv([(c, None)])
    assert "T1" in out
    assert "hola" not in out


def test_handle_export_csv():
    resp = export_router._handle_export([], "csv")
    assert resp.media_type.startswith("text/csv")
    assert resp.body is not None


def test_handle_export_json():
    resp = export_router._handle_export([], "json")
    assert resp.media_type.startswith("application/json")
    assert b"clips" in resp.body


def test_build_json_payload_shape():
    c = SimpleNamespace(id=uuid.uuid4(), title="T1", start_time=0.0, end_time=5.0, score=8.0, transcript="hola")
    p = export_router._build_json_payload([(c, None)], job_id=None)
    assert p["total_clips"] == 1
    assert p["clips"][0]["title"] == "T1"
    assert p["avg_score"] == 8.0


def test_fetch_user_clips(db_session):
    user = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    v = Video(user_id=user.id, filename="v.mp4", filepath="/tmp/v.mp4")
    db_session.add(v)
    db_session.commit()
    j = Job(video_id=v.id, status="completed", progress=100)
    db_session.add(j)
    db_session.commit()
    c = Clip(job_id=j.id, video_id=v.id, start_time=0.0, end_time=5.0, status="ready", storage_path="/tmp/c.mp4", tags={})
    db_session.add(c)
    db_session.commit()
    clips = export_router._fetch_user_clips(db_session, user)
    assert isinstance(clips, list)
