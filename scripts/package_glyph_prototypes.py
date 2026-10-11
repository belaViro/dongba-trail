"""Package selected DB1404 prototypes into a deployable, path-independent bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.glyph_prototypes import load_prototype_index  # noqa: E402

DEFAULT_SOURCE = ROOT / "data" / "DB1404"
if not DEFAULT_SOURCE.exists():
    DEFAULT_SOURCE = ROOT / "\u6570\u636e\u96c6" / "DB1404"
DEFAULT_INDEX = ROOT / "runtime" / "glyph-prototypes" / "index.json"
DEFAULT_OUTPUT = ROOT / "runtime" / "glyph-prototype-bundle"
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _source_path(root: Path, value: str) -> Path:
    if not value or "\\" in value:
        raise ValueError("prototype source must be a relative POSIX path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("prototype source escapes the dataset")
    resolved_root = root.resolve()
    path = resolved_root.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("prototype source escapes the dataset") from exc
    return path


def package(source: Path, index_path: Path, output: Path) -> dict:
    index = load_prototype_index(index_path)
    output.mkdir(parents=True, exist_ok=True)
    assets_directory = output / "assets"
    assets_directory.mkdir(exist_ok=True)
    classes = []
    asset_paths: set[str] = set()
    total_asset_bytes = 0
    asset_digest = hashlib.sha256()
    for entry in index["classes"]:
        packaged_prototypes = []
        for prototype in entry.get("prototypes", []):
            path = _source_path(source, prototype["source"])
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if prototype.get("sha256") and prototype["sha256"] != digest:
                raise ValueError(f"prototype checksum changed for {entry['character_id']}")
            suffix = path.suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                raise ValueError(f"unsupported prototype asset type for {entry['character_id']}")
            relative_asset = PurePosixPath("assets", digest[:2], f"{digest}{suffix}")
            asset = output.joinpath(*relative_asset.parts)
            asset.parent.mkdir(exist_ok=True)
            if asset.exists():
                if hashlib.sha256(asset.read_bytes()).hexdigest() != digest:
                    raise ValueError("content-addressed prototype asset is corrupt")
            else:
                temporary = asset.with_suffix(asset.suffix + ".tmp")
                temporary.write_bytes(raw)
                temporary.replace(asset)
            asset_name = relative_asset.as_posix()
            if asset_name not in asset_paths:
                asset_paths.add(asset_name)
                total_asset_bytes += len(raw)
                asset_digest.update(asset_name.encode("utf-8") + b"\0" + digest.encode("ascii"))
            packaged_prototypes.append(
                {
                    "asset": asset_name,
                    "sha256": digest,
                    "feature": prototype["feature"],
                }
            )
        classes.append(
            {
                key: value
                for key, value in entry.items()
                if key not in {"prototypes", "source_signature"}
            }
            | {"prototypes": packaged_prototypes}
        )
    artifact = {
        key: value
        for key, value in index.items()
        if key not in {"classes", "stats", "asset_format", "bundle_stats"}
    }
    artifact.update(
        {
            "asset_format": "files-v1",
            "source_index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
            "classes": classes,
            "stats": index.get("stats", {}),
            "bundle_stats": {
                "class_count": len(classes),
                "prototype_count": sum(len(entry["prototypes"]) for entry in classes),
                "unique_asset_count": len(asset_paths),
                "asset_bytes": total_asset_bytes,
                "asset_manifest_sha256": asset_digest.hexdigest(),
            },
        }
    )
    target = output / "index.json"
    temporary_index = output / "index.json.tmp"
    temporary_index.write_text(
        json.dumps(artifact, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    temporary_index.replace(target)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    artifact = package(args.source, args.index, args.output)
    print(json.dumps(artifact["bundle_stats"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
