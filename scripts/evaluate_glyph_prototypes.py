"""Evaluate DB1404 shortlist recall on the 50 named glyph images, without API calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.glyph_prototypes import (  # noqa: E402
    encode_feature,
    image_feature,
    load_prototype_index,
    rank_prototype_classes,
)

DEFAULT_DATASET = ROOT / "数据集" / "DB1404"
DEFAULT_IMAGES = ROOT / "东巴字图片_按中文含义命名"
DEFAULT_MANIFEST = ROOT / "data" / "db1404_full.json"
DEFAULT_INDEX = ROOT / "runtime" / "glyph-prototypes" / "index.json"
DEFAULT_OUTPUT = ROOT / "runtime" / "glyph-prototypes" / "evaluation.json"
TOP_K = (1, 5, 20, 50, 100, 200, 500)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def resize_query(raw: bytes, long_edge: int) -> tuple[bytes, list[int]]:
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
        return output.getvalue(), list(image.size)


def prototype(path: Path, source: str, *, imported_shape: bool = False) -> dict | None:
    raw = path.read_bytes()
    feature_raw = raw
    if imported_shape:
        with Image.open(BytesIO(raw)) as opened:
            normalized = ImageOps.autocontrast(ImageOps.exif_transpose(opened).convert("L")).resize(
                (512, 512), Image.Resampling.LANCZOS
            )
            output = BytesIO()
            normalized.save(output, format="PNG")
            feature_raw = output.getvalue()
    feature = image_feature(feature_raw)
    if feature is None:
        return None
    return {"source": source, "sha256": sha256(raw), "feature": encode_feature(feature)}


def baseline_classes(manifest: dict, dataset: Path, include_variant: bool) -> list[dict]:
    classes = []
    for entry in manifest["entries"]:
        if entry["status"] != "published":
            continue
        number = entry["source_no"]
        directory = dataset / f"{number:04d}"
        filenames = [entry["primary_file"]]
        if include_variant and entry["variant_file"] not in filenames:
            filenames.append(entry["variant_file"])
        prototypes = []
        for filename in filenames:
            item = prototype(
                directory / filename,
                f"{number:04d}/{filename}",
                imported_shape=True,
            )
            if item is not None:
                prototypes.append(item)
        classes.append({"character_id": f"DB1404_{number:04d}", "prototypes": prototypes})
    return classes


def duplicate_report(raw: bytes, expected_ids: set[str], dataset: Path) -> dict:
    digest = sha256(raw)
    feature = image_feature(raw)
    exact = []
    same_feature = []
    for character_id in sorted(expected_ids):
        directory = dataset / character_id.removeprefix("DB1404_")
        for path in sorted(directory.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            sample = path.read_bytes()
            if sha256(sample) == digest:
                exact.append(f"{directory.name}/{path.name}")
            if feature is not None and image_feature(sample) == feature:
                same_feature.append(f"{directory.name}/{path.name}")
    return {
        "exact_source_matches": exact,
        "same_feature_source_count": len(same_feature),
        "same_feature_sources_first_20": same_feature[:20],
    }


def rank_one(raw: bytes, classes: list[dict], expected: set[str], excluded: set[str]) -> dict:
    started = time.perf_counter()
    ranked = rank_prototype_classes(raw, classes, limit=max(TOP_K), excluded_sha256=excluded)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    rank = next(
        (index + 1 for index, item in enumerate(ranked) if item.character_id in expected), None
    )
    matching = next((item for item in ranked if item.character_id in expected), None)
    return {
        "rank": rank,
        "nearest_expected_source": matching.source if matching else None,
        "nearest_expected_distance": matching.distance if matching else None,
        "top_ids": [item.character_id for item in ranked[:5]],
        "elapsed_ms": elapsed_ms,
    }


def summarize(rows: list[dict], method: str) -> dict:
    ranks = [row["methods"][method]["rank"] for row in rows]
    latencies = [row["methods"][method]["elapsed_ms"] for row in rows]
    return {
        **{
            f"top_{value}": sum(rank is not None and rank <= value for rank in ranks)
            for value in TOP_K
        },
        "mean_ms": round(sum(latencies) / len(latencies), 3),
        "max_ms": max(latencies),
    }


def evaluate(
    dataset: Path,
    images: Path,
    manifest_path: Path,
    index_path: Path,
    query_long_edge: int,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    index = load_prototype_index(index_path)
    published = {
        f"DB1404_{entry['source_no']:04d}"
        for entry in manifest["entries"]
        if entry["status"] == "published"
    }
    name_to_ids: dict[str, set[str]] = {}
    for entry in manifest["entries"]:
        character_id = f"DB1404_{entry['source_no']:04d}"
        if character_id in published:
            name_to_ids.setdefault(entry["name"], set()).add(character_id)
    primary = baseline_classes(manifest, dataset, include_variant=False)
    primary_variant = baseline_classes(manifest, dataset, include_variant=True)
    multi = [entry for entry in index["classes"] if entry["character_id"] in published]
    rows = []
    folder_digest = hashlib.sha256()
    for path in sorted(images.glob("*.jpg"), key=lambda item: item.name):
        raw = path.read_bytes()
        folder_digest.update(path.name.encode("utf-8") + b"\0" + raw)
        expected = name_to_ids.get(path.stem, set())
        if not expected:
            raise ValueError(f"no published DB1404 mapping for {path.name}")
        leakage = duplicate_report(raw, expected, dataset)
        query, query_size = resize_query(raw, query_long_edge)
        excluded = {sha256(raw)}
        row = {
            "name": path.stem,
            "file": path.name,
            "sha256": sha256(raw),
            "expected_ids": sorted(expected),
            "query_size": query_size,
            **leakage,
            "methods": {
                "primary": rank_one(query, primary, expected, set()),
                "primary_variant": rank_one(query, primary_variant, expected, set()),
                "multi_prototype": rank_one(query, multi, expected, set()),
                "multi_prototype_leave_exact_out": rank_one(query, multi, expected, excluded),
            },
        }
        rows.append(row)
        print(f"evaluated={len(rows)} name={path.stem}", flush=True)
    if len(rows) != 50:
        raise ValueError(f"expected exactly 50 named JPG images, found {len(rows)}")
    methods = next(iter(rows))["methods"]
    return {
        "scope": "local shortlist recall only; no external model call and no camera accuracy claim",
        "target_folder": str(images.relative_to(ROOT)),
        "target_folder_sha256": folder_digest.hexdigest(),
        "query_long_edge": query_long_edge,
        "index_sha256": sha256(index_path.read_bytes()),
        "index_stats": index["stats"],
        "case_count": len(rows),
        "exact_duplicate_cases": sum(bool(row["exact_source_matches"]) for row in rows),
        "same_feature_cases": sum(row["same_feature_source_count"] > 0 for row in rows),
        "summary": {method: summarize(rows, method) for method in methods},
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--query-long-edge", type=int, default=512)
    args = parser.parse_args()
    result = evaluate(
        args.dataset,
        args.images,
        args.manifest,
        args.index,
        args.query_long_edge,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
