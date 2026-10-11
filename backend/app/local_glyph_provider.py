"""CPU inference adapter for the trusted DB1404 glyph classifier artifact."""

import asyncio
import hashlib
import threading
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from backend.app.glyph_refs import GlyphReference
from backend.app.providers import ProviderUnavailable
from backend.app.schemas import Character, ProviderCandidate, ProviderResult


def _artifact_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=8)
def _verified_digest(path: str, size: int, modified_ns: int) -> str:
    del size, modified_ns
    return _artifact_digest(Path(path))


def _canonical_id(class_id: str) -> str:
    value = str(class_id).strip()
    if len(value) == 4 and value.isdigit():
        return f"DB1404_{value}"
    return value


def _normalized(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        image = Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba)
    return ImageOps.pad(image.convert("L"), (64, 64), Image.Resampling.BILINEAR, color=255)


def _model_class(torch):
    nn = torch.nn

    class GlyphCNN(nn.Module):
        def __init__(self, classes: int):
            super().__init__()
            layers = []
            incoming = 1
            for outgoing in (24, 48, 80):
                layers.extend(
                    [
                        nn.Conv2d(incoming, outgoing, 3, padding=1, bias=False),
                        nn.BatchNorm2d(outgoing),
                        nn.ReLU(),
                        nn.MaxPool2d(2),
                    ]
                )
                incoming = outgoing
            self.features = nn.Sequential(*layers, nn.AdaptiveAvgPool2d((4, 4)))
            self.classifier = nn.Sequential(
                nn.Flatten(),
                nn.Linear(80 * 4 * 4, 128),
                nn.LayerNorm(128),
                nn.LeakyReLU(negative_slope=0.1),
                nn.Dropout(0.2),
                nn.Linear(128, classes),
            )

        def forward(self, images):
            return self.classifier(self.features(images))

    return GlyphCNN


@dataclass
class _Runtime:
    torch: object
    model: object
    labels: tuple[str, ...]
    inference_lock: threading.Lock


_RUNTIMES: dict[tuple[str, str, int], _Runtime] = {}
_RUNTIMES_LOCK = threading.Lock()


def _load_runtime(path: Path, expected_sha256: str, threads: int) -> _Runtime:
    key = (str(path.resolve()), expected_sha256, threads)
    with _RUNTIMES_LOCK:
        existing = _RUNTIMES.get(key)
        if existing is not None:
            return existing
        try:
            import torch
        except (ImportError, OSError) as exc:
            raise ProviderUnavailable("Local inference dependency is not installed") from exc
        try:
            details = path.stat()
            digest = _verified_digest(str(path.resolve()), details.st_size, details.st_mtime_ns)
            if not expected_sha256 or digest != expected_sha256:
                raise ProviderUnavailable("Local model integrity check failed")
            checkpoint = torch.load(path, map_location="cpu", weights_only=True)
            labels_data = checkpoint["labels"]
            labels = tuple(_canonical_id(item["class_id"]) for item in labels_data)
            if not labels or len(labels) != len(set(labels)):
                raise ValueError("Model labels are empty or duplicated")
            torch.set_num_threads(threads)
            model = _model_class(torch)(len(labels))
            model.load_state_dict(checkpoint["model"], strict=True)
            model.eval()
        except ProviderUnavailable:
            raise
        except Exception as exc:
            raise ProviderUnavailable("Local model cannot be loaded") from exc
        runtime = _Runtime(torch, model, labels, threading.Lock())
        _RUNTIMES[key] = runtime
        return runtime


class LocalGlyphProvider:
    name = "db1404-local"
    uses_reference_images = False

    def __init__(
        self,
        *,
        artifact_path: Path,
        expected_sha256: str,
        model_version: str,
        threads: int = 2,
    ):
        self.artifact_path = Path(artifact_path).resolve()
        self.expected_sha256 = expected_sha256.strip().lower()
        self.model_version = model_version
        self.threads = threads

    @property
    def configured(self) -> bool:
        try:
            details = self.artifact_path.stat()
            if not self.artifact_path.is_file() or not self.expected_sha256:
                return False
            if (
                _verified_digest(str(self.artifact_path), details.st_size, details.st_mtime_ns)
                != self.expected_sha256
            ):
                return False
            # OPS-03: a valid digest alone does not prove the CPU runtime can load.
            # Successful loads are cached across per-request provider instances.
            _load_runtime(self.artifact_path, self.expected_sha256, self.threads)
            return True
        except (OSError, ProviderUnavailable):
            return False

    def _predict(self, image: bytes, published_ids: frozenset[str]) -> list[ProviderCandidate]:
        runtime = _load_runtime(self.artifact_path, self.expected_sha256, self.threads)
        eligible = [index for index, value in enumerate(runtime.labels) if value in published_ids]
        if not eligible:
            return []
        try:
            with Image.open(BytesIO(image)) as decoded:
                grayscale = _normalized(decoded)
                pixels = list(grayscale.getdata())
        except Exception as exc:
            raise ProviderUnavailable("Local inference image cannot be decoded") from exc
        torch = runtime.torch
        inputs = 1.0 - torch.tensor(pixels, dtype=torch.float32).reshape(1, 1, 64, 64) / 255.0
        with runtime.inference_lock, torch.inference_mode():
            probabilities = runtime.model(inputs).softmax(dim=1)[0]
            eligible_tensor = torch.tensor(eligible, dtype=torch.long)
            eligible_scores = probabilities.index_select(0, eligible_tensor)
            scores, positions = eligible_scores.topk(min(5, len(eligible)))
        return [
            ProviderCandidate(
                character_id=runtime.labels[eligible[positions[index].item()]],
                score=float(scores[index].item()),
            )
            for index in range(len(positions))
        ]

    async def recognize(
        self,
        image: bytes,
        media_type: str,
        characters: tuple[Character, ...],
        references: tuple[GlyphReference, ...] = (),
    ) -> ProviderResult:
        del media_type, references
        if not self.configured:
            raise ProviderUnavailable("Local model is not configured")
        published_ids = frozenset(character.character_id for character in characters)
        candidates = await asyncio.to_thread(self._predict, image, published_ids)
        return ProviderResult(model_version=self.model_version, candidates=candidates)
