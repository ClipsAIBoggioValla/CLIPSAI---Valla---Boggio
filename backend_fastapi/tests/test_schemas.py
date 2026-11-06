from __future__ import annotations

import uuid
from datetime import datetime

from backend_fastapi.app.schemas.clip import ClipBase, ClipUpdate, PublishClipRequest
from backend_fastapi.app.schemas.job import *
from backend_fastapi.app.schemas.metrics import *
from backend_fastapi.app.schemas.stats import *
from backend_fastapi.app.schemas.token import *
from backend_fastapi.app.schemas.usuario import *
from backend_fastapi.app.schemas.video import *


def test_clip_base():
    c = ClipBase(title="t", tags=["a"])
    assert c.title == "t"
    u = ClipUpdate()
    assert u.title is None


def test_publish_clip_request():
    r = PublishClipRequest(platform="tiktok", caption="hi")
    assert r.platform == "tiktok"
    r2 = PublishClipRequest(platform="webhook", webhook_override_url="http://x")
    assert r2.webhook_override_url == "http://x"


def test_imports_ok():
    assert True
