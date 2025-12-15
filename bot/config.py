import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, validator


class DiscordListConfig(BaseModel):
    guilds: List[int] = Field(default_factory=list)
    channels: List[int] = Field(default_factory=list)
    users: List[int] = Field(default_factory=list)


class DiscordIntentsConfig(BaseModel):
    message_content: bool = True


class DiscordConfig(BaseModel):
    token_env: str
    application_id: str | None = None
    intents: DiscordIntentsConfig = DiscordIntentsConfig()
    allow_dm: bool = True
    whitelist: DiscordListConfig = DiscordListConfig()
    blacklist: DiscordListConfig = DiscordListConfig()
    slash_command_guilds: List[int] = Field(default_factory=list)


class RateLimitConfig(BaseModel):
    window_seconds: int = 30
    max_messages: int = 6
    cooldown_prompt: str = "我这边处理有点多，稍后再回复你哦～"
    notify_when_limited: bool = True


class ContextConfig(BaseModel):
    scope: str = "channel"
    max_messages: int = 12
    expiry_minutes: int = 120

    @validator("scope")
    def validate_scope(cls, v: str) -> str:
        allowed = {"channel", "user", "thread"}
        if v not in allowed:
            raise ValueError(f"context.scope 必须是 {allowed}")
        return v


class BehaviorConfig(BaseModel):
    enabled_by_default: bool = True
    respond_to_bots: bool = False
    mention_only: bool = False
    min_reply_delay: float = 0.8
    max_reply_delay: float = 2.4
    send_typing: bool = True
    emoji_density: float = 0.3
    duplicate_window_seconds: int = 120
    duplicate_similarity: float = 0.92
    rate_limit: RateLimitConfig = RateLimitConfig()
    context: ContextConfig = ContextConfig()


class StyleConfig(BaseModel):
    id: str
    name: str
    model: str
    system_prompt: str
    temperature: float = 0.6
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    emoji_density: float = 0.3
    max_tokens: Optional[int] = None


class RouterConfig(BaseModel):
    default_style: str
    fallback_style: str
    confidence_threshold: float = 0.35


class OllamaConfig(BaseModel):
    base_url: str
    timeout_seconds: int = 60


class ASRHTTPConfig(BaseModel):
    endpoint: str
    timeout_seconds: int = 30


class ASRConfig(BaseModel):
    provider: str = "dummy"
    http: ASRHTTPConfig | None = None


class AdminConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    token_env: str = "ADMIN_TOKEN"
    allow_cors: bool = False


class AppMeta(BaseModel):
    name: str = "SelfBot"
    locale: str = "zh"
    logging_level: str = "INFO"
    data_dir: str = "data"


class AppConfig(BaseModel):
    app: AppMeta = AppMeta()
    discord: DiscordConfig
    behavior: BehaviorConfig = BehaviorConfig()
    router: RouterConfig
    styles: List[StyleConfig]
    ollama: OllamaConfig
    asr: ASRConfig = ASRConfig()
    admin: AdminConfig = AdminConfig()

    def style_map(self) -> Dict[str, StyleConfig]:
        return {style.id: style for style in self.styles}


def load_yaml_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    config = AppConfig.parse_obj(data)

    base_url_override = os.getenv("OLLAMA_BASE_URL")
    if base_url_override:
        config.ollama.base_url = base_url_override
    log_level_override = os.getenv("LOG_LEVEL")
    if log_level_override:
        config.app.logging_level = log_level_override
    return config


def save_yaml_config(config: AppConfig, path: str | Path) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config.dict(), f, allow_unicode=True, sort_keys=False)
