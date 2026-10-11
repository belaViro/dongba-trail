"""Deterministic CPU-only glyph prototype selection and retrieval (AI-01).

This module does not train a model. It normalizes handwriting samples into
compact byte features, keeps several representative samples per DB1404 class,
and ranks unique classes by their nearest prototype.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

PROTOTYPE_INDEX_VERSION = 1
PROTOTYPE_FEATURE_SIDE = 16


@dataclass(frozen=True)
class PrototypeCandidate:
    source: str
    feature: bytes
    sha256: str = ""


@dataclass(frozen=True)
class RankedPrototype:
    character_id: str
    distance: int
    source: str
    sha256: str


def image_feature(raw: bytes, side: int = PROTOTYPE_FEATURE_SIDE) -> bytes | None:
    """Return an aspect-preserving grayscale ink feature, or ``None`` if invalid."""
    try:
        with Image.open(BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened).convert("L")
            image = ImageOps.autocontrast(image)
            mask = image.point(lambda value: 255 if value < 128 else 0)
            box = mask.getbbox()
            if box is None:
                return None
            image = image.crop(box)
            width, height = image.size
            scale = side / max(width, height)
            image = image.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.Resampling.BOX,
            )
            canvas = Image.new("L", (side, side), 255)
            canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
            feature = canvas.tobytes()
            if sum(value < 245 for value in feature) < 2:
                return None
            return feature
    except (OSError, ValueError):
        return None


def l1_distance(left: bytes, right: bytes) -> int:
    if len(left) != len(right):
        raise ValueError("prototype feature lengths differ")
    return sum(abs(a - b) for a, b in zip(left, right, strict=True))


def _selection_feature(feature: bytes) -> bytes:
    """Use an 8x8 block feature to keep offline diversity selection inexpensive."""
    if len(feature) != PROTOTYPE_FEATURE_SIDE**2:
        return feature
    values = []
    for block_y in range(8):
        for block_x in range(8):
            offset = block_y * 2 * PROTOTYPE_FEATURE_SIDE + block_x * 2
            values.append(
                sum(
                    (
                        feature[offset],
                        feature[offset + 1],
                        feature[offset + PROTOTYPE_FEATURE_SIDE],
                        feature[offset + PROTOTYPE_FEATURE_SIDE + 1],
                    )
                )
                // 4
            )
    return bytes(values)


def select_representative_prototypes(
    candidates: list[PrototypeCandidate],
    count: int = 8,
    trim_fraction: float = 0.1,
) -> list[PrototypeCandidate]:
    """Select central but diverse representatives with deterministic farthest-first."""
    if count <= 0 or not candidates:
        return []
    ordered = sorted(candidates, key=lambda item: item.source)
    width = len(ordered[0].feature)
    if any(len(item.feature) != width for item in ordered):
        raise ValueError("prototype feature lengths differ")
    selection_features = {item.source: _selection_feature(item.feature) for item in ordered}
    selection_width = len(next(iter(selection_features.values())))
    means = [
        sum(selection_features[item.source][index] for item in ordered) // len(ordered)
        for index in range(selection_width)
    ]
    central = sorted(
        ordered,
        key=lambda item: (
            sum(
                abs(value - means[index])
                for index, value in enumerate(selection_features[item.source])
            ),
            item.source,
        ),
    )
    keep = max(count, round(len(central) * (1 - trim_fraction)))
    eligible = central[: min(len(central), keep)]
    selected = [eligible[0]]
    minimum_distances = [
        l1_distance(selection_features[item.source], selection_features[selected[0].source])
        for item in eligible
    ]
    while len(selected) < min(count, len(eligible)):
        index = max(
            (i for i, item in enumerate(eligible) if item not in selected),
            key=lambda i: (minimum_distances[i], eligible[i].source),
        )
        chosen = eligible[index]
        selected.append(chosen)
        for i, item in enumerate(eligible):
            minimum_distances[i] = min(
                minimum_distances[i],
                l1_distance(selection_features[item.source], selection_features[chosen.source]),
            )
    return selected


def encode_feature(feature: bytes) -> str:
    return base64.b64encode(feature).decode("ascii")


@lru_cache(maxsize=50_000)
def decode_feature(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def load_prototype_index(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("version") != PROTOTYPE_INDEX_VERSION:
        raise ValueError("unsupported glyph prototype index version")
    if value.get("feature_side") != PROTOTYPE_FEATURE_SIDE:
        raise ValueError("unsupported glyph prototype feature size")
    return value


def rank_prototype_classes(
    query: bytes,
    classes: list[dict[str, Any]],
    *,
    limit: int = 200,
    excluded_sha256: set[str] | None = None,
) -> list[RankedPrototype]:
    """Rank unique classes and retain the query-nearest prototype per class."""
    query_feature = image_feature(query)
    if query_feature is None or limit <= 0:
        return []
    excluded = excluded_sha256 or set()
    best_by_character: dict[str, RankedPrototype] = {}
    for entry in classes:
        best: RankedPrototype | None = None
        for prototype in entry.get("prototypes", []):
            sha256 = prototype.get("sha256", "")
            if sha256 and sha256 in excluded:
                continue
            try:
                feature = decode_feature(prototype["feature"])
                distance = l1_distance(query_feature, feature)
                character_id = entry["character_id"]
            except (KeyError, TypeError, ValueError):
                continue
            if not isinstance(character_id, str):
                continue
            candidate = RankedPrototype(
                character_id=character_id,
                distance=distance,
                source=prototype.get("asset") or prototype.get("source", ""),
                sha256=sha256,
            )
            if best is None or (candidate.distance, candidate.source) < (
                best.distance,
                best.source,
            ):
                best = candidate
        if best is not None:
            current = best_by_character.get(best.character_id)
            if current is None or (best.distance, best.source) < (
                current.distance,
                current.source,
            ):
                best_by_character[best.character_id] = best
    ranked = list(best_by_character.values())
    ranked.sort(key=lambda item: (item.distance, item.character_id, item.source))
    return ranked[:limit]
