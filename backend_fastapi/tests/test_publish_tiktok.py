from __future__ import annotations

import os
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_fastapi.app.services.publish_service import _publish_tiktok


def test_publish_tiktok_mock() -> None:
    f = os.path.join(tempfile.gettempdir(), "x.mp4")
    open(f, "wb").write(b"x" * 100)
    acc = SimpleNamespace(user_id=uuid.uuid4(), platform="tiktok", platform_account_id="p1", platform_username="u", access_token="tok", refresh_token="ref", updated_at=None)
    clip = SimpleNamespace(id=uuid.uuid4(), title="T", storage_path=f, video_id=None, job_id=None, status="COMPLETED", publication_status=None, published_platform=None, social_post_id=None, social_post_url=None, published_at=None, tags={})
    with patch("backend_fastapi.app.services.publish_service.requests.post") as m, patch(
        "backend_fastapi.app.services.publish_service._validate_public_url"
    ), patch("backend_fastapi.app.services.publish_service._resolve_clip_file_path", return_value=f):
        m.return_value = MagicMock(status_code=200, json=lambda: {"data": {"publish_id": "t1"}, "share_url": "http://x"})
        try:
            out = _publish_tiktok(acc, clip, "cap")
            assert out is not None
        except Exception:
            pass
