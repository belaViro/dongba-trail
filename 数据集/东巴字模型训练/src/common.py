"""Offline experiment helpers (AI-02 / D-081)."""

import hashlib
import json
import os
from pathlib import Path

from PIL import Image, ImageOps

HOME = Path(__file__).resolve().parents[1]
PROJECT = HOME.parents[1]


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalized(image):
    """Deterministic letterbox shared by audit, training and inference."""
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        image = Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba)
    return ImageOps.pad(image.convert("L"), (64, 64), Image.Resampling.BILINEAR, color=255)


def code_fingerprint():
    return fingerprint({p.name: sha_file(p) for p in sorted((HOME / "src").glob("*.py"))})


def verified_manifest(directory):
    directory = Path(directory)
    manifest = read_json(directory / "manifest.json")
    if fingerprint(manifest["fingerprints"]) != manifest["split_fingerprint"]:
        raise ValueError("Split fingerprint is invalid")
    for name, digest in manifest["fingerprints"].items():
        if sha_file(directory / name) != digest:
            raise ValueError(f"Split artifact changed: {name}")
    return manifest
