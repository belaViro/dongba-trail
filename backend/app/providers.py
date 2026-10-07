from typing import Protocol

from backend.app.glyph_refs import GlyphReference
from backend.app.schemas import Character, ProviderResult


class ProviderUnavailable(Exception):
    pass


class RecognitionProvider(Protocol):
    name: str
    configured: bool

    async def recognize(
        self,
        image: bytes,
        media_type: str,
        characters: tuple[Character, ...],
        references: tuple[GlyphReference, ...] = (),
    ) -> ProviderResult: ...


class UnconfiguredProvider:
    name = "unconfigured"
    configured = False

    async def recognize(
        self,
        image: bytes,
        media_type: str,
        characters: tuple[Character, ...],
        references: tuple[GlyphReference, ...] = (),
    ) -> ProviderResult:
        raise ProviderUnavailable("Recognition provider is not configured")
