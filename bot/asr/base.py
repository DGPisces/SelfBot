import abc
from typing import Optional


class ASRProvider(abc.ABC):
    @abc.abstractmethod
    async def transcribe(self, audio_bytes: bytes, filename: str) -> Optional[str]:
        raise NotImplementedError
