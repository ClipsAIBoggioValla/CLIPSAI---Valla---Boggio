from __future__ import annotations

import uuid

from backend_fastapi.app.models import Usuario, Video, Job, Clip


def test_create_user(db_session):
    u = Usuario(id=uuid.uuid4(), email="a@b.com", hashed_password="h", full_name="N")
    db_session.add(u)
    db_session.commit()
    assert db_session.get(Usuario, u.id) is not None


def test_create_video_job_clip(db_session):
    u = Usuario(id=uuid.uuid4(), email="a@b.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    v = Video(user_id=u.id, filename="v.mp4", filepath="/tmp/v.mp4")
    db_session.add(v)
    db_session.commit()
    j = Job(video_id=v.id, status="pending", progress=0)
    db_session.add(j)
    db_session.commit()
    c = Clip(job_id=j.id, start_time=0.0, end_time=5.0, status="ready")
    db_session.add(c)
    db_session.commit()
    assert db_session.get(Clip, c.id) is not None
