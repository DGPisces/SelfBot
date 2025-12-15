import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bot.config import AppConfig, StyleConfig, save_yaml_config
from bot.core.privacy import mask_sensitive_data
from bot.core.style_router import StyleRouter
from bot.storage.audit import AuditLog
from bot.storage.conversations import ConversationLogger
from bot.storage.event_buffer import EventBuffer
from bot.storage.state_store import StateStore


def _require_admin(config: AppConfig):
    expected = os.getenv(config.admin.token_env, "")

    async def verifier(request: Request):
        token = request.headers.get("X-Admin-Token")
        if not expected or token != expected:
            raise HTTPException(status_code=401, detail="unauthorized")
        return True

    return verifier


def create_admin_app(
    config: AppConfig,
    state_store: StateStore,
    event_buffer: EventBuffer,
    audit_log: AuditLog,
    conv_logger: ConversationLogger,
    config_path: Path,
    style_router: StyleRouter,
) -> FastAPI:
    app = FastAPI(title="SelfBot Admin", docs_url=None, redoc_url=None)

    verifier = _require_admin(config)

    @app.get("/api/status")
    async def status(_: bool = Depends(verifier)):
        state = await state_store.load()
        return {
            "enabled": state.enabled,
            "manual_styles": state.manual_styles,
            "router_logs": event_buffer.recent(50),
            "styles": [s.dict() for s in config.styles],
            "behavior": config.behavior.dict(),
        }

    @app.post("/api/toggle")
    async def toggle(body: dict, _: bool = Depends(verifier)):
        enabled = bool(body.get("enabled", True))
        await state_store.set_enabled(enabled)
        audit_log.add("admin_toggle", {"enabled": enabled})
        return {"ok": True, "enabled": enabled}

    @app.post("/api/style")
    async def set_style(body: dict, _: bool = Depends(verifier)):
        scope = body.get("scope")
        style_id: Optional[str] = body.get("style_id")
        if not scope:
            raise HTTPException(400, "scope缺失")
        await state_store.set_manual_style(scope, style_id)
        audit_log.add("admin_style", {"scope": scope, "style": style_id})
        return {"ok": True}

    @app.post("/api/style/{style_id}")
    async def update_style(style_id: str, body: dict, _: bool = Depends(verifier)):
        style_map = config.style_map()
        if style_id not in style_map:
            raise HTTPException(404, "style不存在")
        existing: StyleConfig = style_map[style_id]
        updated = existing.copy(update={k: v for k, v in body.items() if k in existing.dict()})
        for i, s in enumerate(config.styles):
            if s.id == style_id:
                config.styles[i] = updated
        style_router.styles = config.style_map()
        save_yaml_config(config, config_path)
        audit_log.add("admin_style_update", {"style": style_id})
        return {"ok": True, "style": updated.dict()}

    @app.post("/api/behavior")
    async def update_behavior(body: dict, _: bool = Depends(verifier)):
        for key, value in body.items():
            if hasattr(config.behavior, key):
                setattr(config.behavior, key, value)
        save_yaml_config(config, config_path)
        audit_log.add("admin_behavior_update", body)
        return {"ok": True, "behavior": config.behavior.dict()}

    @app.post("/api/whitelist")
    async def update_lists(body: dict, _: bool = Depends(verifier)):
        for field in ["whitelist", "blacklist"]:
            if field in body:
                cfg = getattr(config.discord, field)
                updates = body[field]
                for k, v in updates.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
        save_yaml_config(config, config_path)
        audit_log.add("admin_access_update", body)
        return {"ok": True}

    @app.get("/api/logs")
    async def logs(_: bool = Depends(verifier)):
        return {"events": event_buffer.recent(100), "audit": audit_log.recent(50)}

    @app.get("/api/conversations/export")
    async def export(_: bool = Depends(verifier)):
        export_path = conv_logger.export()
        audit_log.add("admin_export", {"path": str(export_path)})
        return {"ok": True, "path": str(export_path)}

    @app.post("/api/reload")
    async def reload(_: bool = Depends(verifier)):
        # Reload is no-op for now because config object already in memory; keeping endpoint for symmetry.
        return {"ok": True}

    static_dir = Path(__file__).parent / "static"
    app.mount("/admin", StaticFiles(directory=static_dir, html=True), name="admin")

    @app.exception_handler(HTTPException)
    async def http_exc(_, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    return app
