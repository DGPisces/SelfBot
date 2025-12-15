import time
from collections import deque
from typing import Deque

from bot.config import RateLimitConfig


class RateLimiter:
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.buckets: dict[int, Deque[float]] = {}

    def allow(self, key: int) -> bool:
        now = time.time()
        window = self.buckets.setdefault(key, deque())
        while window and now - window[0] > self.config.window_seconds:
            window.popleft()
        if len(window) >= self.config.max_messages:
            return False
        window.append(now)
        return True
