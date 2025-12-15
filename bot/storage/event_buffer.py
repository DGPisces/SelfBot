from collections import deque
from typing import Deque, Dict, List


class EventBuffer:
    def __init__(self, maxlen: int = 200):
        self.buffer: Deque[Dict] = deque(maxlen=maxlen)

    def add(self, event: Dict) -> None:
        self.buffer.append(event)

    def recent(self, limit: int = 50) -> List[Dict]:
        if limit <= 0:
            return []
        return list(self.buffer)[-limit:]
