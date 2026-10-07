"""Reference glyph loading for image-based recognition (AI-01, D-066).

The Ark vision model cannot map a photo to a dictionary ID from Chinese names
alone. This module turns reviewed dictionary entries into compact reference
glyph images that are sent alongside the photo. It never invents content and
never exposes user photos to other visitors.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from backend.app.schemas import Character

logger = logging.getLogger(__name__)

# Kept small so many references fit in one request and latency stays bounded.
REFERENCE_SIDE = 128
MAX_REFERENCES = 200

_cache: dict[tuple[str, int, int], bytes] = {}
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class GlyphReference:
    character_id: str
    cn_name: str
    image: bytes


def _asset_name(url: str) -> str | None:
    prefix = "/api/v1/media/"
    if not url.startswith(prefix):
        return None
    name = url.removeprefix(prefix)
    if not name.endswith(".png") or "/" in name or "\\" in name:
        return None
    return name


def _normalize(raw: bytes) -> bytes:
    with Image.open(BytesIO(raw)) as opened:
        clean = ImageOps.exif_transpose(opened).convert("L")
        clean = ImageOps.autocontrast(clean)
        canvas = Image.new("L", (REFERENCE_SIDE, REFERENCE_SIDE), 255)
        thumb = clean.copy()
        thumb.thumbnail((REFERENCE_SIDE, REFERENCE_SIDE), Image.Resampling.LANCZOS)
        offset = ((REFERENCE_SIDE - thumb.width) // 2, (REFERENCE_SIDE - thumb.height) // 2)
        canvas.paste(thumb, offset)
        output = BytesIO()
        canvas.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


def _cached(path: Path, character_id: str) -> bytes | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (character_id, stat.st_mtime_ns, stat.st_size)
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        normalized = _normalize(path.read_bytes())
    except Exception as exc:  # A single bad asset must not break recognition.
        logger.warning(
            "glyph_reference_unreadable character_id=%s error_type=%s",
            character_id,
            type(exc).__name__,
        )
        return None
    with _cache_lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[key] = normalized
    return normalized


def load_references(
    characters: Sequence[Character],
    media_directory: Path,
    limit: int = MAX_REFERENCES,
) -> list[GlyphReference]:
    """Return reviewed reference glyphs, skipping entries without a usable image."""
    references: list[GlyphReference] = []
    for character in characters:
        if len(references) >= limit:
            break
        name = _asset_name(character.image_url)
        if not name:
            continue
        normalized = _cached(media_directory / name, character.character_id)
        if normalized is None:
            continue
        references.append(
            GlyphReference(
                character_id=character.character_id,
                cn_name=character.cn_name,
                image=normalized,
            )
        )
    return references
