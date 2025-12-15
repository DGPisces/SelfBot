import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from bot.core.privacy import mask_sensitive_data


class ConversationLogger:
    def __init__(self, log_path: Path, export_dir: Path):
        self.log_path = log_path
        self.export_dir = export_dir
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        scope: str,
        user_id: int,
        content: str,
        reply: Optional[str],
        style_id: str,
        router_reason: str,
    ) -> None:
        entry = {
            "ts": time.time(),
            "scope": scope,
            "user": user_id,
            "content": mask_sensitive_data(content),
            "reply": mask_sensitive_data(reply or ""),
            "style": style_id,
            "reason": router_reason,
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def tail(self, limit: int = 50) -> List[Dict]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").strip().splitlines()
        result: List[Dict] = []
        for line in lines[-limit:]:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return result

    def export(self) -> Path:
        ts = int(time.time())
        export_path = self.export_dir / f"conversation_export_{ts}.json"
        entries = self.tail(5000)
        export_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return export_path
