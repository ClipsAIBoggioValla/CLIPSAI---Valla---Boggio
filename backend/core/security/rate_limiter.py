from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict


class RateLimitExceeded(Exception):
    pass


class QuotaExceeded(Exception):
    pass


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        q = self._hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= self.max_requests:
            raise RateLimitExceeded(f"Rate limit {self.max_requests}/{self.window}s for {key}")
        q.append(now)


class MinutesQuota:
    def __init__(self, max_minutes_per_day: int = 120) -> None:
        self.max_minutes = max_minutes_per_day
        self._usage: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._day: Dict[str, str] = {}

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d")

    def consume(self, user_id: str, minutes: float) -> None:
        today = self._today()
        if self._day.get(user_id) != today:
            self._usage[user_id] = defaultdict(float)
            self._day[user_id] = today
        used = self._usage[user_id][today]
        if used + minutes > self.max_minutes:
            raise QuotaExceeded(f"Quota {self.max_minutes} min/day exceeded for {user_id} (used {used:.1f})")
        self._usage[user_id][today] = used + minutes

    def remaining(self, user_id: str) -> float:
        today = self._today()
        if self._day.get(user_id) != today:
            return float(self.max_minutes)
        return max(0.0, self.max_minutes - self._usage[user_id][today])


rate_limiter = RateLimiter()
minutes_quota = MinutesQuota()
