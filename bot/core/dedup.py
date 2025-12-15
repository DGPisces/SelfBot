import difflib
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Tuple


@dataclass
class DedupConfig:
    window_seconds: int = 120
    similarity: float = 0.92
    max_items: int = 50


class Deduplicator:
    def __init__(self, config: DedupConfig):
        self.config = config
        self.records: dict[int, Deque[Tuple[float, str]]] = {}

    def is_duplicate(self, channel_id: int, content: str) -> bool:
        now = time.time()
        queue = self.records.setdefault(channel_id, deque())
        while queue and now - queue[0][0] > self.config.window_seconds:
            queue.popleft()
        normalized = content.strip().lower()
        for _, prev in queue:
            ratio = difflib.SequenceMatcher(None, normalized, prev).ratio()
            if ratio >= self.config.similarity:
                return True
        queue.append((now, normalized))
        if len(queue) > self.config.max_items:
            queue.popleft()
        return False
