from typing import Protocol

from backend.app.schemas import Character, ProviderResult


class ProviderUnavailable(Exception):
    pass


class RecognitionProvider(Protocol):
    name: str
    configured: bool

    async def recognize(
        self, image: bytes, media_type: str, characters: tuple[Character, ...]
    ) -> ProviderResult: ...


class UnconfiguredProvider:
    name = "unconfigured"
    configured = False

    async def recognize(
        self, image: bytes, media_type: str, characters: tuple[Character, ...]
    ) -> ProviderResult:
        raise ProviderUnavailable("Recognition provider is not configured")
