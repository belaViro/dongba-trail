"""SHARE-01 / D-062: crop the user-provided image08 artwork, excluding app UI and sample QR."""

import argparse
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    with Image.open(args.source) as source:
        source.load()
        if source.size != (941, 1672):
            raise SystemExit("Expected the reviewed 941x1672 image08 reference")
        reference = source.convert("RGB").crop((503, 132, 929, 1295))
    # Remove the demonstration code AND its captions; never supply a fake code to the model.
    paper = ImageOps.fit(reference.crop((90, 228, 225, 278)), (126, 181))
    paper = paper.filter(ImageFilter.GaussianBlur(1))
    reference.paste(paper, (293, 982))
    target = ROOT / "backend/assets/poster-reference.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    reference.save(target, quality=94, optimize=True)
    print(f"Saved {target.relative_to(ROOT)} ({reference.width}x{reference.height})")


if __name__ == "__main__":
    main()
