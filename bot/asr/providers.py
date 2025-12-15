import logging
from typing import Optional

import httpx

from bot.asr.base import ASRProvider
from bot.config import ASRConfig

logger = logging.getLogger(__name__)


class DummyASRProvider(ASRProvider):
    async def transcribe(self, audio_bytes: bytes, filename: str) -> Optional[str]:
        logger.warning("使用 Dummy ASR，未实际转写。文件: %s", filename)
        return "（语音内容占位，未实际转写）"


class HTTPASRProvider(ASRProvider):
    def __init__(self, endpoint: str, timeout: int = 30):
        self.endpoint = endpoint
        self.client = httpx.AsyncClient(timeout=timeout)

    async def transcribe(self, audio_bytes: bytes, filename: str) -> Optional[str]:
        files = {"file": (filename, audio_bytes)}
        resp = await self.client.post(self.endpoint, files=files)
        if resp.status_code != 200:
            logger.error("ASR HTTP错误: %s %s", resp.status_code, resp.text)
            return None
        data = resp.json()
        return data.get("text")

    async def aclose(self) -> None:
        await self.client.aclose()


def build_asr_provider(config: ASRConfig) -> ASRProvider:
    if config.provider == "http" and config.http:
        return HTTPASRProvider(
            endpoint=config.http.endpoint, timeout=config.http.timeout_seconds
        )
    return DummyASRProvider()
