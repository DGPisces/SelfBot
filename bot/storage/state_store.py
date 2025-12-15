import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional


class RuntimeState:
    def __init__(self):
        self.enabled: bool = True
        self.manual_styles: Dict[str, str] = {}
        self.updated_at: float = time.time()

    def to_dict(self) -> Dict:
        return {
            "enabled": self.enabled,
            "manual_styles": self.manual_styles,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "RuntimeState":
        inst = cls()
        inst.enabled = data.get("enabled", True)
        inst.manual_styles = data.get("manual_styles", {})
        inst.updated_at = data.get("updated_at", time.time())
        return inst


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = asyncio.Lock()
        self.state = RuntimeState()

    async def load(self) -> RuntimeState:
        if not self.path.exists():
            return self.state
        async with self.lock:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = RuntimeState.from_dict(data)
            return self.state

    async def save(self) -> None:
        async with self.lock:
            self.state.updated_at = time.time()
            self.path.write_text(
                json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    async def set_enabled(self, enabled: bool) -> RuntimeState:
        self.state.enabled = enabled
        await self.save()
        return self.state

    async def set_manual_style(self, scope_key: str, style_id: Optional[str]) -> None:
        if style_id:
            self.state.manual_styles[scope_key] = style_id
        else:
            self.state.manual_styles.pop(scope_key, None)
        await self.save()

    def resolve_manual_style(self, scope_keys: list[str]) -> Optional[str]:
        for key in scope_keys:
            if key in self.state.manual_styles:
                return self.state.manual_styles[key]
        return None
