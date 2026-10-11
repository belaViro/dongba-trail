"""Lazy images; stable per-epoch augmentation makes mid-epoch resume repeatable."""

import csv
import hashlib
import io
import random
from pathlib import Path

import numpy as np
import torch
from common import normalized
from PIL import Image, ImageEnhance, ImageFilter
from torch.utils.data import Dataset


def tensor_image(image, rng=None):
    image = normalized(image)
    if rng is not None:
        image = image.rotate(rng.uniform(-7, 7), Image.Resampling.BILINEAR, fillcolor=255)
        scale = rng.uniform(0.92, 1.08)
        dx, dy = rng.uniform(-3, 3), rng.uniform(-3, 3)
        image = image.transform(
            (64, 64),
            Image.Transform.AFFINE,
            (1 / scale, 0, 32 - 32 / scale - dx, 0, 1 / scale, 32 - 32 / scale - dy),
            Image.Resampling.BILINEAR,
            fillcolor=255,
        )
        image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.9, 1.1))
        if rng.random() < 0.15:
            image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0.1, 0.4)))
    array = 1.0 - np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)


class GlyphDataset(Dataset):
    def __init__(self, root, csv_path, augment=False, seed=20261008):
        self.root = Path(root).resolve()
        with Path(csv_path).open(encoding="utf-8", newline="") as stream:
            self.rows = list(csv.DictReader(stream))
        self.augment, self.seed, self.epoch = augment, seed, 0
        for row in self.rows:
            relative = Path(row["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe dataset path")

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        path = (self.root / row["path"]).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Dataset path escapes root")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["file_sha256"]:
            raise ValueError(f"Source image changed after audit: {row['path']}")
        rng = random.Random(self.seed + self.epoch * 1000000007 + index) if self.augment else None
        with Image.open(io.BytesIO(content)) as image:
            tensor = tensor_image(image, rng)
        return tensor, int(row["label"])


def epoch_batches(length, batch_size, seed, epoch, start=0):
    generator = torch.Generator().manual_seed(seed + epoch)
    order = torch.randperm(length, generator=generator).tolist()
    for offset in range(start * batch_size, length, batch_size):
        yield order[offset : offset + batch_size]
