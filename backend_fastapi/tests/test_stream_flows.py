from __future__ import annotations

import uuid

from backend_fastapi.app.models import Usuario, Video, Job, Clip
from backend_fastapi.app.routers.stream import _effective_status, _event, _get_owner_video
from backend_fastapi.app.routers import stream as stream_router


def _mk_clip(db_session, user_id, status="PUBLISHED", pub_status=None, video_id=None, job_id=None):
    v = Video(user_id=user_id, filename="v.mp4", filepath="/tmp/v.mp4")
    db_session.add(v)
    db_session.commit()
    j = Job(video_id=v.id, status="completed", progress=100)
    db_session.add(j)
    db_session.commit()
    c = Clip(job_id=j.id, video_id=video_id or v.id, start_time=0.0, end_time=5.0, status=status, storage_path="/tmp/c.mp4", tags={})
    if pub_status:
        c.publication_status = pub_status
    db_session.add(c)
    db_session.commit()
    return c


def test_effective_status_variants(db_session):
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()

    c1 = _mk_clip(db_session, u.id, status="PUBLISHED")
    assert _effective_status(c1) == "PUBLISHED"

    c2 = _mk_clip(db_session, u.id, status="ready", pub_status="PUBLISHING")
    assert _effective_status(c2) == "PUBLISHING"

    c3 = _mk_clip(db_session, u.id, status="ready", pub_status="FAILED")
    assert _effective_status(c3) == "FAILED"

    c4 = _mk_clip(db_session, u.id, status="ready")
    assert _effective_status(c4) == "DRAFT"


def test_event_format():
    s = _event("data", {"a": 1})
    assert s.startswith("event: data")
    assert "data: " in s
    assert s.endswith("\n\n")


def test_get_owner_video_via_job(db_session):
    u = Usuario(id=uuid.uuid4(), email=f"u{uuid.uuid4().hex[:6]}@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    v = Video(user_id=u.id, filename="v.mp4", filepath="/tmp/v.mp4")
    db_session.add(v)
    db_session.commit()
    j = Job(video_id=v.id, status="completed", progress=100)
    db_session.add(j)
    db_session.commit()
    c = Clip(job_id=j.id, video_id=None, start_time=0.0, end_time=5.0, status="ready", storage_path="/tmp/c.mp4", tags={})
    db_session.add(c)
    db_session.commit()
    owner = stream_router._get_owner_video(db_session, c)
    assert owner is not None
    assert owner.id == v.id


def test_get_owner_video_none(db_session):
    import uuid as _u
    c = Clip(job_id=_u.uuid4(), video_id=None, start_time=0.0, end_time=5.0, status="ready", storage_path="/tmp/c.mp4", tags={})
    db_session.add(c)
    db_session.commit()
    assert stream_router._get_owner_video(db_session, c) is None
