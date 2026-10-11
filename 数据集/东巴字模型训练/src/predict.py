"""Single-image Top-5 from a trusted, locally generated inference artifact."""

import argparse
import json
from pathlib import Path

import torch
from common import HOME
from model import GlyphCNN
from PIL import Image

from data import tensor_image


def predict(artifact, image_path):
    checkpoint = torch.load(artifact, map_location="cpu", weights_only=True)
    labels = checkpoint["labels"]
    torch.set_num_threads(2)
    model = GlyphCNN(len(labels))
    model.load_state_dict(checkpoint["model"])
    model.eval()
    with Image.open(image_path) as image, torch.inference_mode():
        scores, indices = (
            model(tensor_image(image).unsqueeze(0)).softmax(1).topk(min(5, len(labels)))
        )
    return [
        {**labels[index], "reference_score": score}
        for index, score in zip(indices[0].tolist(), scores[0].tolist(), strict=True)
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=HOME / "reports/cpu_v2/inference.pt")
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "candidates": predict(args.model, args.image),
                "warning": "Uncalibrated scores, not accuracy; unknown rejection not supported.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
