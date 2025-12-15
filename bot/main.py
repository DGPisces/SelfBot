import asyncio
import logging
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from bot.asr.providers import build_asr_provider
from bot.config import AppConfig, load_yaml_config
from bot.core.context import ConversationStore
from bot.core.dedup import DedupConfig, Deduplicator
from bot.core.rate_limiter import RateLimiter
from bot.core.style_router import StyleRouter
from bot.discord.client import SelfBot
from bot.llm.ollama_client import OllamaClient
from bot.storage.audit import AuditLog
from bot.storage.conversations import ConversationLogger
from bot.storage.event_buffer import EventBuffer
from bot.storage.state_store import StateStore
from bot.web.admin_app import create_admin_app


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def run():
    load_dotenv()
    config_path = Path(os.getenv("CONFIG_PATH", "configs/config.yaml"))
    config: AppConfig = load_yaml_config(config_path)
    setup_logging(config.app.logging_level)

    bot_token = os.getenv(config.discord.token_env)
    if not bot_token:
        raise RuntimeError(f"未找到环境变量 {config.discord.token_env}，请先设置。")

    data_dir = Path(config.app.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    state_store = StateStore(data_dir / "runtime_state.json")
    existing = await state_store.load()
    if not state_store.path.exists():
        existing.enabled = config.behavior.enabled_by_default
        await state_store.save()

    conversation_store = ConversationStore(config.behavior.context)
    deduplicator = Deduplicator(
        DedupConfig(
            window_seconds=config.behavior.duplicate_window_seconds,
            similarity=config.behavior.duplicate_similarity,
        )
    )
    rate_limiter = RateLimiter(config.behavior.rate_limit)
    style_router = StyleRouter(config.router, config.style_map())
    llm_client = OllamaClient(config.ollama)
    asr_provider = build_asr_provider(config.asr)
    event_buffer = EventBuffer()
    audit_log = AuditLog(data_dir / "audit.log")
    conv_logger = ConversationLogger(
        log_path=data_dir / "conversations.log",
        export_dir=data_dir / "exports",
    )

    bot = SelfBot(
        config=config,
        state_store=state_store,
        conversation_store=conversation_store,
        deduplicator=deduplicator,
        rate_limiter=rate_limiter,
        style_router=style_router,
        llm_client=llm_client,
        asr_provider=asr_provider,
        event_buffer=event_buffer,
        audit_log=audit_log,
        conv_logger=conv_logger,
    )

    admin_app = create_admin_app(
        config=config,
        state_store=state_store,
        event_buffer=event_buffer,
        audit_log=audit_log,
        conv_logger=conv_logger,
        config_path=config_path,
        style_router=style_router,
    )

    server = uvicorn.Server(
        uvicorn.Config(
            app=admin_app,
            host=config.admin.host,
            port=config.admin.port,
            log_level="info",
        )
    )

    async def start_admin():
        await server.serve()

    async def start_bot():
        await bot.start(bot_token)

    try:
        await asyncio.gather(start_admin(), start_bot())
    except asyncio.CancelledError:
        pass
    finally:
        await llm_client.aclose()
        if hasattr(asr_provider, "aclose"):
            await asr_provider.aclose()  # type: ignore
        await bot.close()


if __name__ == "__main__":
    asyncio.run(run())
