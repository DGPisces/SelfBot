import asyncio
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.asr.base import ASRProvider
from bot.config import AppConfig
from bot.core.context import ConversationStore
from bot.core.dedup import Deduplicator
from bot.core.rate_limiter import RateLimiter
from bot.core.style_router import StyleRouter
from bot.llm.ollama_client import OllamaClient
from bot.policy.access import AccessPolicy
from bot.storage.audit import AuditLog
from bot.storage.conversations import ConversationLogger
from bot.storage.event_buffer import EventBuffer
from bot.storage.state_store import StateStore

logger = logging.getLogger(__name__)


AUDIO_EXTS = {"wav", "mp3", "m4a", "aac", "flac", "ogg"}
IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}


class SelfBot(commands.Bot):
    def __init__(
        self,
        config: AppConfig,
        state_store: StateStore,
        conversation_store: ConversationStore,
        deduplicator: Deduplicator,
        rate_limiter: RateLimiter,
        style_router: StyleRouter,
        llm_client: OllamaClient,
        asr_provider: ASRProvider,
        event_buffer: EventBuffer,
        audit_log: AuditLog,
        conv_logger: ConversationLogger,
    ):
        intents = discord.Intents.default()
        intents.message_content = config.discord.intents.message_content
        intents.messages = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.state_store = state_store
        self.conversation_store = conversation_store
        self.deduplicator = deduplicator
        self.rate_limiter = rate_limiter
        self.style_router = style_router
        self.llm_client = llm_client
        self.asr_provider = asr_provider
        self.event_buffer = event_buffer
        self.audit_log = audit_log
        self.conv_logger = conv_logger
        self.access_policy = AccessPolicy(config.discord, config.behavior)
        self.cooldown_notified: set[int] = set()

        self.tree.add_command(self._cmd_status())
        self.tree.add_command(self._cmd_toggle())
        self.tree.add_command(self._cmd_style())

    async def setup_hook(self) -> None:
        if self.config.discord.slash_command_guilds:
            for gid in self.config.discord.slash_command_guilds:
                await self.tree.sync(guild=discord.Object(id=gid))
        else:
            await self.tree.sync()
        logger.info("Slash commands synced")

    def _cmd_status(self) -> app_commands.Command:
        @app_commands.command(name="selfbot_status", description="查看SelfBot状态")
        async def status_cmd(interaction: discord.Interaction):
            state = await self.state_store.load()
            await interaction.response.send_message(
                f"SelfBot 当前 {'开启' if state.enabled else '关闭'}，手动风格覆盖：{state.manual_styles or '无'}",
                ephemeral=True,
            )

        return status_cmd

    def _cmd_toggle(self) -> app_commands.Command:
        @app_commands.command(name="selfbot_toggle", description="开启或关闭SelfBot")
        @app_commands.choices(
            action=[
                app_commands.Choice(name="开启", value="on"),
                app_commands.Choice(name="关闭", value="off"),
            ]
        )
        async def toggle_cmd(
            interaction: discord.Interaction, action: app_commands.Choice[str]
        ):
            enable = action.value == "on"
            await self.state_store.set_enabled(enable)
            await interaction.response.send_message(
                f"SelfBot 已{'开启' if enable else '关闭'}", ephemeral=True
            )

        return toggle_cmd

    def _cmd_style(self) -> app_commands.Command:
        choices = [
            app_commands.Choice(name=style.name, value=style.id)
            for style in self.config.styles
        ]
        choices.append(app_commands.Choice(name="自动", value="auto"))

        @app_commands.command(name="selfbot_style", description="设置当前频道/服务器的风格")
        @app_commands.describe(scope="guild / channel", style_id="选择风格或自动")
        @app_commands.choices(
            scope=[
                app_commands.Choice(name="channel", value="channel"),
                app_commands.Choice(name="guild", value="guild"),
            ],
            style_id=choices,
        )
        async def style_cmd(
            interaction: discord.Interaction,
            scope: app_commands.Choice[str],
            style_id: app_commands.Choice[str],
        ):
            target_key = ""
            if scope.value == "guild":
                if not interaction.guild:
                    await interaction.response.send_message(
                        "只能在服务器内设置。", ephemeral=True
                    )
                    return
                target_key = f"guild:{interaction.guild.id}"
            else:
                target_key = f"channel:{interaction.channel_id}"
            manual_style = None if style_id.value == "auto" else style_id.value
            await self.state_store.set_manual_style(target_key, manual_style)
            await interaction.response.send_message(
                f"{scope.name} 风格已设置为 {style_id.name}", ephemeral=True
            )

        return style_cmd

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "")

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return
        allowed, reason = self.access_policy.check(message)
        if not allowed:
            self.event_buffer.add(
                {
                    "type": "blocked",
                    "reason": reason,
                    "channel": message.channel.id,
                    "user": message.author.id,
                }
            )
            return

        state = await self.state_store.load()
        if not state.enabled:
            return

        content = (message.content or "").strip()
        if not content and message.attachments:
            content = ""

        if self.deduplicator.is_duplicate(message.channel.id, content or ""):
            logger.info("跳过重复消息 channel=%s", message.channel.id)
            return

        if not self.rate_limiter.allow(message.channel.id):
            if (
                self.config.behavior.rate_limit.notify_when_limited
                and message.channel.id not in self.cooldown_notified
            ):
                await message.channel.send(
                    self.config.behavior.rate_limit.cooldown_prompt,
                    reference=message,
                    mention_author=False,
                )
                self.cooldown_notified.add(message.channel.id)
            return
        self.cooldown_notified.discard(message.channel.id)

        scope_id = self.access_policy.scope_id(message, self.config.behavior.context.scope)

        has_image = any(
            (a.content_type or "").startswith("image") or a.filename.lower().split(".")[-1] in IMAGE_EXTS
            for a in message.attachments
        )
        has_audio = any(
            (a.content_type or "").startswith("audio") or a.filename.lower().split(".")[-1] in AUDIO_EXTS
            for a in message.attachments
        )

        asr_text: Optional[str] = None
        if has_audio:
            await self._send_typing(message)
            try:
                audio = message.attachments[0]
                audio_bytes = await audio.read()
                asr_text = await self.asr_provider.transcribe(audio_bytes, audio.filename)
            except Exception as exc:  # pragma: no cover
                logger.exception("ASR失败: %s", exc)
                await message.channel.send("语音解析出了点问题，麻烦用文字再说一次～", reference=message)
                self.event_buffer.add(
                    {
                        "type": "asr_error",
                        "detail": str(exc),
                        "user": message.author.id,
                    }
                )
                return
            if asr_text is None:
                await message.channel.send("语音解析失败了，能否改用文字？", reference=message)
                return
            content = (content + "\n语音转写：" + asr_text).strip()

        if has_image and not content:
            await message.channel.send("我暂不支持直接看图，麻烦用文字描述一下吧～", reference=message)
            return

        if not content and not has_audio:
            return

        extra_hint = ""
        if has_image:
            extra_hint = "\n（提示：图片内容无法读取）"

        manual_style = self.state_store.resolve_manual_style(
            [
                f"channel:{message.channel.id}",
                f"guild:{message.guild.id}" if message.guild else "",
                f"user:{message.author.id}",
            ]
        )
        decision = self.style_router.decide(content, manual_style)
        style = self.config.style_map().get(decision.style_id)
        if not style:
            style = self.config.style_map()[self.config.router.fallback_style]

        await self._send_typing(message)
        await asyncio.sleep(
            random.uniform(
                self.config.behavior.min_reply_delay,
                self.config.behavior.max_reply_delay,
            )
        )

        history = self.conversation_store.history_for_llm(scope_id)
        try:
            reply = await self.llm_client.generate(
                user_content=content + extra_hint, history=history, style=style
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("LLM生成失败: %s", exc)
            await message.channel.send("我这边出错了，稍后再聊可以吗？", reference=message)
            self.event_buffer.add(
                {
                    "type": "llm_error",
                    "detail": str(exc),
                    "user": message.author.id,
                }
            )
            return

        self.conversation_store.add(scope_id, "user", content)
        self.conversation_store.add(scope_id, "assistant", reply)

        await message.channel.send(reply, reference=message, mention_author=False)

        self.event_buffer.add(
            {
                "type": "reply",
                "style": style.id,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "user": message.author.id,
                "channel": message.channel.id,
            }
        )
        self.audit_log.add(
            "reply",
            {
                "style": style.id,
                "reason": decision.reason,
                "user": message.author.id,
                "channel": message.channel.id,
            },
        )
        self.conv_logger.record(
            scope=scope_id,
            user_id=message.author.id,
            content=content,
            reply=reply,
            style_id=style.id,
            router_reason=decision.reason,
        )

    async def _send_typing(self, message: discord.Message) -> None:
        if not self.config.behavior.send_typing:
            return
        try:
            async with message.channel.typing():
                await asyncio.sleep(0.2)
        except Exception:
            logger.debug("发送typing失败", exc_info=True)
