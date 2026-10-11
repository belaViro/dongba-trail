"""Build a deterministic multi-prototype index from the local DB1404 dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.glyph_prototypes import (  # noqa: E402
    PROTOTYPE_FEATURE_SIDE,
    PROTOTYPE_INDEX_VERSION,
    PrototypeCandidate,
    encode_feature,
    image_feature,
    select_representative_prototypes,
)

DEFAULT_SOURCE = ROOT / "数据集" / "DB1404"
DEFAULT_OUTPUT = ROOT / "runtime" / "glyph-prototypes" / "index.json"


def scan_class(directory: Path, count: int, trim_fraction: float) -> dict:
    candidates: list[PrototypeCandidate] = []
    unreadable = 0
    signature = hashlib.sha256()
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        stat = path.stat()
        signature.update(f"{path.name}\0{stat.st_size}\n".encode())
        try:
            raw = path.read_bytes()
        except OSError:
            unreadable += 1
            continue
        feature = image_feature(raw)
        if feature is None:
            unreadable += 1
            continue
        candidates.append(
            PrototypeCandidate(source=f"{directory.name}/{path.name}", feature=feature)
        )
    selected = select_representative_prototypes(
        candidates, count=count, trim_fraction=trim_fraction
    )
    prototypes = []
    for item in selected:
        raw = (directory.parent / item.source).read_bytes()
        prototypes.append(
            {
                "source": item.source,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "feature": encode_feature(item.feature),
            }
        )
    return {
        "character_id": f"DB1404_{int(directory.name):04d}",
        "source_no": int(directory.name),
        "sample_count": len(candidates),
        "unreadable_count": unreadable,
        "source_signature": signature.hexdigest(),
        "prototypes": prototypes,
    }


def build(source: Path, output: Path, count: int, trim_fraction: float, workers: int) -> dict:
    started = time.perf_counter()
    directories = sorted(
        (path for path in source.iterdir() if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
    )
    if not directories:
        raise ValueError(f"no DB1404 class directories found under {source}")
    classes = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(scan_class, path, count, trim_fraction): path for path in directories
        }
        for completed, future in enumerate(as_completed(futures), 1):
            classes.append(future.result())
            if completed % 50 == 0 or completed == len(futures):
                print(f"scanned_classes={completed}/{len(futures)}", flush=True)
    classes.sort(key=lambda item: item["source_no"])
    source_digest = hashlib.sha256()
    for entry in classes:
        source_digest.update(f"{entry['source_no']}\0{entry.pop('source_signature')}\n".encode())
    artifact = {
        "version": PROTOTYPE_INDEX_VERSION,
        "feature_side": PROTOTYPE_FEATURE_SIDE,
        "prototypes_per_class": count,
        "trim_fraction": trim_fraction,
        "source_digest": source_digest.hexdigest(),
        "classes": classes,
        "stats": {
            "class_count": len(classes),
            "sample_count": sum(item["sample_count"] for item in classes),
            "prototype_count": sum(len(item["prototypes"]) for item in classes),
            "unreadable_count": sum(item["unreadable_count"] for item in classes),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(json.dumps(artifact["stats"], ensure_ascii=False), flush=True)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--trim-fraction", type=float, default=0.1)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    args = parser.parse_args()
    if args.count < 1 or not 0 <= args.trim_fraction < 1 or args.workers < 1:
        parser.error("count/workers must be positive and trim-fraction must be in [0, 1)")
    build(args.source, args.output, args.count, args.trim_fraction, args.workers)


if __name__ == "__main__":
    main()
