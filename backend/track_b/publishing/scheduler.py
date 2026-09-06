from __future__ import annotations

from backend.core.interfaces import IPublisher
from backend.core.schemas import ScheduledPost


class MockPublisher(IPublisher):
    """Stub Track B — publica a TikTok/IG/YouTube via webhook mock. Reemplazable sin tocar Track A."""

    async def publish(self, clip_path: str, post: ScheduledPost) -> dict:
        return {"clip_id": post.clip_id, "platforms": post.platforms, "url": f"https://mock.publish/{post.clip_id}", "status": "published"}

    async def schedule(self, post: ScheduledPost) -> str:
        return f"scheduled:{post.clip_id}:{post.scheduled_at}"
