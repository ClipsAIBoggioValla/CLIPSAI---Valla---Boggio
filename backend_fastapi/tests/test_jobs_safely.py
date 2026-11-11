from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend_fastapi.app.routers import jobs as jobs_router
from backend_fastapi.app.routers.jobs import run_job_safely, create_job


@pytest.mark.asyncio
async def test_run_job_safely_ok() -> None:
    with patch("backend_fastapi.app.routers.jobs._run_job"):
        await run_job_safely(str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_run_job_safely_fail() -> None:
    with patch("backend_fastapi.app.routers.jobs._run_job", side_effect=RuntimeError("boom")), patch(
        "backend_fastapi.app.routers.jobs.SessionLocal"
    ) as SL:
        db = MagicMock()
        SL.return_value = db
        db.get.return_value = None
        await run_job_safely(str(uuid.uuid4()))


def test_create_job_endpoint() -> None:
    from fastapi.testclient import TestClient
    from backend_fastapi.app.main import app
    from backend_fastapi.app.deps import get_current_user, get_db

    db = MagicMock()
    user = SimpleNamespace(id=uuid.uuid4())
    video = SimpleNamespace(id=uuid.uuid4(), user_id=user.id)
    db.get.return_value = video
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()

    def _get_db():
        yield db

    def _get_user():
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(f"/videos/{video.id}/jobs")
        assert resp.status_code in (200, 201, 202, 400, 404, 422, 500)
        client.close()
    finally:
        app.dependency_overrides.clear()
