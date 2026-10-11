"""Reference glyph loading for image-based recognition (AI-01, D-066, D-071).

The Ark vision model cannot map a photo to a dictionary ID from Chinese names
alone. This module turns reviewed dictionary entries into compact reference
glyph images that are sent alongside the photo. It never invents content and
never exposes user photos to other visitors.

D-071: once the published dictionary outgrows ``MAX_REFERENCES`` the adapter
must not send an arbitrary prefix of reference glyphs. A deterministic CPU
feature shortlists the closest candidates first, so every published character
stays reachable without training a model or adding infrastructure.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath

from PIL import Image, ImageDraw, ImageFont, ImageOps

from backend.app.glyph_prototypes import load_prototype_index, rank_prototype_classes
from backend.app.schemas import Character

logger = logging.getLogger(__name__)

# Kept small so many references fit in one request and latency stays bounded.
REFERENCE_SIDE = 128
# Coarse shortlist side: tiny enough to compare every published glyph on CPU,
# large enough to keep the stroke layout usable for ranking.
FEATURE_SIDE = 16
MAX_REFERENCES = 200
# Ark charges a substantial per-image vision-token minimum. Sending the 200
# shortlisted glyphs as separate 128px images made one recognition consume an
# unexpectedly large prompt. Keep every shortlisted glyph, but pack 20 of them
# into each labelled comparison sheet before the provider request.
SHEET_COLUMNS = 4
SHEET_ROWS = 5
SHEET_TILE_WIDTH = 160
SHEET_TILE_HEIGHT = 160
REFERENCES_PER_SHEET = SHEET_COLUMNS * SHEET_ROWS

_cache: dict[tuple[str, int, int, str], bytes] = {}
_feature_cache: dict[tuple[str, int, int], bytes] = {}
_prototype_index_cache: dict[tuple[str, int, int], dict] = {}
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class GlyphReference:
    character_id: str
    cn_name: str
    image: bytes


def build_reference_sheets(
    references: Sequence[GlyphReference],
) -> list[tuple[tuple[GlyphReference, ...], bytes]]:
    """Pack reference glyphs into labelled PNG sheets without dropping any IDs."""
    sheets: list[tuple[tuple[GlyphReference, ...], bytes]] = []
    font = ImageFont.load_default(size=16)
    for start in range(0, len(references), REFERENCES_PER_SHEET):
        group = tuple(references[start : start + REFERENCES_PER_SHEET])
        rows = (len(group) + SHEET_COLUMNS - 1) // SHEET_COLUMNS
        canvas = Image.new(
            "RGB", (SHEET_COLUMNS * SHEET_TILE_WIDTH, rows * SHEET_TILE_HEIGHT), "white"
        )
        draw = ImageDraw.Draw(canvas)
        for index, reference in enumerate(group):
            x = index % SHEET_COLUMNS * SHEET_TILE_WIDTH
            y = index // SHEET_COLUMNS * SHEET_TILE_HEIGHT
            draw.rectangle(
                (x, y, x + SHEET_TILE_WIDTH - 1, y + SHEET_TILE_HEIGHT - 1),
                outline="#dddddd",
            )
            if (
                not reference.character_id.isascii()
                or draw.textlength(reference.character_id, font) > SHEET_TILE_WIDTH - 8
            ):
                raise ValueError("reference ID cannot fit in comparison sheet")
            draw.text((x + 4, y + 3), reference.character_id, fill="black", font=font)
            with Image.open(BytesIO(reference.image)) as opened:
                glyph = opened.convert("RGB")
                if glyph.width > REFERENCE_SIDE or glyph.height > REFERENCE_SIDE:
                    raise ValueError("reference glyph exceeds normalized dimensions")
                canvas.paste(
                    glyph,
                    (x + (SHEET_TILE_WIDTH - glyph.width) // 2, y + 25),
                )
        output = BytesIO()
        canvas.save(output, format="PNG", optimize=True)
        sheets.append((group, output.getvalue()))
    return sheets


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
        scale = REFERENCE_SIDE / max(clean.size)
        thumb = clean.resize(
            tuple(max(1, round(value * scale)) for value in clean.size),
            Image.Resampling.LANCZOS,
        )
        offset = ((REFERENCE_SIDE - thumb.width) // 2, (REFERENCE_SIDE - thumb.height) // 2)
        canvas.paste(thumb, offset)
        output = BytesIO()
        canvas.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


def _cached(path: Path, character_id: str, expected_sha256: str = "") -> bytes | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size, expected_sha256)
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        raw = path.read_bytes()
        if expected_sha256 and hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError("glyph prototype checksum mismatch")
        normalized = _normalize(raw)
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


def _prototype_asset_path(directory: Path, value: str) -> Path | None:
    if not value or "\\" in value:
        return None
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or relative.parts[0] != "assets":
        return None
    if any(part in {"", ".", ".."} for part in relative.parts):
        return None
    root = directory.resolve()
    candidate = root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _prototype_index(directory: Path) -> dict:
    path = directory / "index.json"
    stat = path.stat()
    key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    with _cache_lock:
        cached = _prototype_index_cache.get(key)
    if cached is not None:
        return cached
    index = load_prototype_index(path)
    if index.get("asset_format") != "files-v1" or not isinstance(index.get("classes"), list):
        raise ValueError("glyph prototype bundle is not deployable")
    with _cache_lock:
        _prototype_index_cache.clear()
        _prototype_index_cache[key] = index
    return index


def _load_prototype_references(
    characters: Sequence[Character],
    directory: Path,
    query: bytes,
    limit: int,
) -> list[GlyphReference] | None:
    """Load query-nearest packaged prototypes, or return ``None`` for fallback."""
    try:
        index = _prototype_index(directory)
        by_id = {character.character_id: character for character in characters}
        classes = [
            entry
            for entry in index["classes"]
            if entry.get("character_id") in by_id
            and any(prototype.get("asset") for prototype in entry.get("prototypes", []))
        ]
        ranked = rank_prototype_classes(query, classes, limit=len(classes))
    except Exception as exc:
        logger.warning("glyph_prototype_bundle_unavailable error_type=%s", type(exc).__name__)
        return None
    target = min(limit, len(by_id))
    if len({item.character_id for item in ranked}) < target:
        logger.warning(
            "glyph_prototype_bundle_incomplete ranked_count=%s required_count=%s",
            len(ranked),
            target,
        )
        return None
    if target <= 0:
        return None
    references: list[GlyphReference] = []
    seen: set[str] = set()
    for item in ranked:
        if item.character_id in seen:
            continue
        character = by_id.get(item.character_id)
        path = _prototype_asset_path(directory, item.source)
        if character is None or path is None:
            continue
        normalized = _cached(path, item.character_id, item.sha256)
        if normalized is None:
            continue
        seen.add(item.character_id)
        references.append(
            GlyphReference(
                character_id=item.character_id,
                cn_name=character.cn_name,
                image=normalized,
            )
        )
        if len(references) >= target:
            return references
    logger.warning(
        "glyph_prototype_bundle_incomplete usable_count=%s required_count=%s",
        len(references),
        target,
    )
    return None


def _candidate_pairs(characters: Sequence[Character]) -> list[tuple[Character, str]]:
    pairs: list[tuple[Character, str]] = []
    for character in characters:
        name = _asset_name(character.image_url)
        if name:
            pairs.append((character, name))
    return pairs


def _feature(raw: bytes) -> bytes | None:
    """A tiny aspect-preserving ink feature used to shortlist candidate glyphs."""
    try:
        with Image.open(BytesIO(raw)) as opened:
            grayscale = ImageOps.autocontrast(ImageOps.exif_transpose(opened).convert("L"))
            mask = grayscale.point(lambda value: 255 if value < 128 else 0)
            box = mask.getbbox()
            if box:
                grayscale = grayscale.crop(box)
            width, height = grayscale.size
            scale = FEATURE_SIDE / max(width, height)
            resized = grayscale.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.Resampling.BOX,
            )
            canvas = Image.new("L", (FEATURE_SIDE, FEATURE_SIDE), 255)
            canvas.paste(
                resized,
                ((FEATURE_SIDE - resized.width) // 2, (FEATURE_SIDE - resized.height) // 2),
            )
            return canvas.tobytes()
    except (OSError, ValueError):
        return None


def _cached_feature(path: Path, character_id: str) -> bytes | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (character_id, stat.st_mtime_ns, stat.st_size)
    with _cache_lock:
        cached = _feature_cache.get(key)
    if cached is not None:
        return cached
    try:
        feature = _feature(path.read_bytes())
    except OSError:
        return None
    if feature is None:
        return None
    with _cache_lock:
        if len(_feature_cache) > 5000:
            _feature_cache.clear()
        _feature_cache[key] = feature
    return feature


def _rank_candidates(
    pairs: list[tuple[Character, str]],
    media_directory: Path,
    query: bytes,
) -> list[tuple[Character, str]]:
    """Order candidates by coarse glyph similarity to the query photo.

    Deterministic CPU image processing only: no model training, no GPU, no
    automatic retraining. Candidates whose feature cannot be read are kept at
    the end so a single bad asset never removes a character from the set.
    """
    query_feature = _feature(query)
    if query_feature is None:
        return pairs
    scored: list[tuple[int, Character, str]] = []
    unranked: list[tuple[Character, str]] = []
    for character, name in pairs:
        feature = _cached_feature(media_directory / name, character.character_id)
        if feature is None:
            unranked.append((character, name))
            continue
        distance = sum(
            abs(left - right) for left, right in zip(query_feature, feature, strict=True)
        )
        scored.append((distance, character, name))
    scored.sort(key=lambda item: item[0])
    return [(character, name) for _, character, name in scored] + unranked


def load_references(
    characters: Sequence[Character],
    media_directory: Path,
    limit: int = MAX_REFERENCES,
    query: bytes | None = None,
    prototype_directory: Path | None = None,
) -> list[GlyphReference]:
    """Return reviewed reference glyphs, skipping entries without a usable image.

    When the dictionary is larger than ``limit`` and a ``query`` photo is given,
    the closest glyphs are chosen by a coarse local feature instead of taking an
    arbitrary prefix, so every published character stays reachable.
    """
    if query is not None and limit > 0 and prototype_directory is not None:
        prototype_references = _load_prototype_references(
            characters, prototype_directory, query, limit
        )
        if prototype_references is not None:
            return prototype_references
    pairs = _candidate_pairs(characters)
    if query is not None and len(pairs) > limit:
        pairs = _rank_candidates(pairs, media_directory, query)
    references: list[GlyphReference] = []
    for character, name in pairs:
        if len(references) >= limit:
            break
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
