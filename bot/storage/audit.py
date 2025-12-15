import json
import time
from pathlib import Path
from typing import Dict, List

from bot.core.privacy import mask_sensitive_data


class AuditLog:
    def __init__(self, path: Path, max_records: int = 500):
        self.path = path
        self.max_records = max_records
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            self.records = json.loads(self.path.read_text(encoding="utf-8"))

    def add(self, event: str, detail: Dict) -> None:
        entry = {
            "ts": time.time(),
            "event": event,
            "detail": mask_sensitive_data(json.dumps(detail, ensure_ascii=False)),
        }
        self.records.append(entry)
        self.records = self.records[-self.max_records :]
        self.path.write_text(
            json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def recent(self, limit: int = 50) -> List[Dict]:
        return list(self.records[-limit:])
