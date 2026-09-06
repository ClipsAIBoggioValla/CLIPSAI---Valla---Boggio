from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List

from backend.core.schemas import ScheduledPost


class PublisherInterface(ABC):
    @abstractmethod
    async def publish(self, clip_path: str, post: ScheduledPost) -> Dict[str, str]:
        ...

    @abstractmethod
    async def schedule(self, post: ScheduledPost) -> str:
        ...


class MockPublisher(PublisherInterface):
    async def publish(self, clip_path: str, post: ScheduledPost) -> Dict[str, str]:
        return {
            "clip_id": post.clip_id,
            "platforms": ",".join(post.platforms),
            "url": f"https://mock.publish/{post.clip_id}",
            "status": "published",
            "clip_path": clip_path,
        }

    async def schedule(self, post: ScheduledPost) -> str:
        return f"scheduled:{post.clip_id}:{post.scheduled_at}"


class SocialScheduler:
    def __init__(self, publisher: PublisherInterface | None = None) -> None:
        self.publisher = publisher or MockPublisher()
        self._scheduled: List[ScheduledPost] = []

    async def schedule_post(self, post: ScheduledPost) -> ScheduledPost:
        self._scheduled.append(post)
        await self.publisher.schedule(post)
        return post

    async def publish_now(self, clip_path: str, post: ScheduledPost) -> Dict[str, str]:
        return await self.publisher.publish(clip_path, post)

    def list_scheduled(self) -> List[ScheduledPost]:
        return list(self._scheduled)

    def get_by_clip(self, clip_id: str) -> List[ScheduledPost]:
        return [p for p in self._scheduled if p.clip_id == clip_id]
