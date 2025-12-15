from typing import Optional, Tuple

import discord

from bot.config import BehaviorConfig, DiscordConfig


class AccessPolicy:
    def __init__(self, discord_config: DiscordConfig, behavior: BehaviorConfig):
        self.discord_config = discord_config
        self.behavior = behavior

    def check(
        self, message: discord.Message
    ) -> Tuple[bool, str]:
        author = message.author
        if author.bot and not self.behavior.respond_to_bots:
            return False, "bot_message"

        guild_id = message.guild.id if message.guild else None
        channel_id = message.channel.id
        user_id = author.id

        if guild_id is None and not self.discord_config.allow_dm:
            return False, "dm_blocked"

        # blacklist first
        if guild_id and guild_id in self.discord_config.blacklist.guilds:
            return False, "guild_blacklisted"
        if channel_id in self.discord_config.blacklist.channels:
            return False, "channel_blacklisted"
        if user_id in self.discord_config.blacklist.users:
            return False, "user_blacklisted"

        # whitelist only if provided
        if self.discord_config.whitelist.guilds and guild_id:
            if guild_id not in self.discord_config.whitelist.guilds:
                return False, "guild_not_whitelisted"

        if self.discord_config.whitelist.channels and channel_id not in self.discord_config.whitelist.channels:
            return False, "channel_not_whitelisted"

        if self.discord_config.whitelist.users and user_id not in self.discord_config.whitelist.users:
            return False, "user_not_whitelisted"

        if (
            self.behavior.mention_only
            and guild_id is not None
            and message.guild
            and message.guild.me
            and message.guild.me not in message.mentions
        ):
            return False, "not_mentioned"

        return True, "allowed"

    @staticmethod
    def scope_id(message: discord.Message, scope: str) -> str:
        if scope == "user":
            return f"user:{message.author.id}"
        if scope == "thread" and message.thread:
            return f"thread:{message.thread.id}"
        return f"channel:{message.channel.id}"
