import time
from dataclasses import dataclass
from typing import Dict, List, Literal

from bot.config import ContextConfig


Role = Literal["system", "user", "assistant"]


@dataclass
class MessageRecord:
    role: Role
    content: str
    ts: float


class ConversationStore:
    def __init__(self, config: ContextConfig):
        self.config = config
        self.contexts: Dict[str, List[MessageRecord]] = {}

    def _cleanup(self, scope_id: str) -> None:
        now = time.time()
        expiry_seconds = self.config.expiry_minutes * 60
        records = self.contexts.get(scope_id, [])
        self.contexts[scope_id] = [
            r for r in records if now - r.ts <= expiry_seconds
        ][-self.config.max_messages :]
        if not self.contexts[scope_id]:
            self.contexts.pop(scope_id, None)

    def add(self, scope_id: str, role: Role, content: str) -> None:
        records = self.contexts.setdefault(scope_id, [])
        records.append(MessageRecord(role=role, content=content, ts=time.time()))
        self._cleanup(scope_id)

    def get(self, scope_id: str) -> List[MessageRecord]:
        self._cleanup(scope_id)
        return list(self.contexts.get(scope_id, []))

    def history_for_llm(self, scope_id: str) -> List[dict]:
        return [
            {"role": record.role, "content": record.content}
            for record in self.get(scope_id)
        ]
