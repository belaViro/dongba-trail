"""Evaluate the packaged prototype bundle through the production reference loader."""

from __future__ import annotations

import argparse
import json
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.glyph_refs import load_references  # noqa: E402
from backend.app.schemas import Character  # noqa: E402

DEFAULT_IMAGES = ROOT / "\u4e1c\u5df4\u5b57\u56fe\u7247_\u6309\u4e2d\u6587\u542b\u4e49\u547d\u540d"
DEFAULT_MANIFEST = ROOT / "data" / "db1404_full.json"
DEFAULT_BUNDLE = ROOT / "runtime" / "glyph-prototype-bundle"
DEFAULT_OUTPUT = ROOT / "runtime" / "glyph-prototype-bundle" / "runtime-evaluation.json"


def resize_query(raw: bytes, long_edge: int) -> bytes:
    with Image.open(BytesIO(raw)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        if long_edge > 0 and max(image.size) < long_edge:
            scale = long_edge / max(image.size)
            image = image.resize(
                tuple(max(1, round(value * scale)) for value in image.size),
                Image.Resampling.LANCZOS,
            )
        output = BytesIO()
        image.save(output, format="JPEG", quality=95)
        return output.getvalue()


def evaluate(images: Path, manifest_path: Path, bundle: Path, long_edge: int) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name_to_ids: dict[str, set[str]] = {}
    characters = []
    for entry in manifest["entries"]:
        if entry["status"] != "published":
            continue
        character_id = f"DB1404_{entry['source_no']:04d}"
        name_to_ids.setdefault(entry["name"], set()).add(character_id)
        characters.append(
            Character(
                character_id=character_id,
                cn_name=entry["name"],
                culture_summary="Runtime shortlist evaluation only",
                source_ref="Local DB1404 manifest",
                status="draft",
            )
        )
    rows = []
    for path in sorted(images.glob("*.jpg"), key=lambda item: item.name):
        expected = name_to_ids.get(path.stem, set())
        if not expected:
            raise ValueError(f"no published mapping for {path.name}")
        started = time.perf_counter()
        references = load_references(
            characters,
            ROOT / "runtime" / "media-does-not-participate",
            query=resize_query(path.read_bytes(), long_edge),
            prototype_directory=bundle,
        )
        ids = [reference.character_id for reference in references]
        rows.append(
            {
                "name": path.stem,
                "expected_ids": sorted(expected),
                "shortlist_has_correct": bool(expected.intersection(ids)),
                "rank": next(
                    (index + 1 for index, value in enumerate(ids) if value in expected), None
                ),
                "reference_count": len(ids),
                "unique_reference_count": len(set(ids)),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        )
    if len(rows) != 50:
        raise ValueError(f"expected exactly 50 named images, found {len(rows)}")
    result = {
        "scope": "integrated local shortlist recall only; no external model call",
        "case_count": len(rows),
        "query_long_edge": long_edge,
        "top_200": sum(row["shortlist_has_correct"] for row in rows),
        "all_reference_counts_200": all(row["reference_count"] == 200 for row in rows),
        "all_references_unique": all(row["unique_reference_count"] == 200 for row in rows),
        "mean_ms": round(sum(row["elapsed_ms"] for row in rows) / len(rows), 3),
        "max_ms": max(row["elapsed_ms"] for row in rows),
        "missing": [row["name"] for row in rows if not row["shortlist_has_correct"]],
        "cases": rows,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--query-long-edge", type=int, default=512)
    args = parser.parse_args()
    result = evaluate(args.images, args.manifest, args.bundle, args.query_long_edge)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in result if key != "cases"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
