"""Generate neutral map markers, never representations of Dongba glyphs."""

from pathlib import Path

from PIL import Image, ImageDraw

target = Path(__file__).resolve().parents[1] / "assets"
target.mkdir(exist_ok=True)
for category, color in (
    ("merchant", "#176b58"),
    ("culture", "#ac5747"),
    ("quest", "#3874a1"),
):
    image = Image.new("RGBA", (104, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon([(16, 57), (88, 57), (52, 121)], fill=color)
    draw.ellipse((8, 4, 96, 92), fill=color, outline="white", width=5)
    draw.ellipse((33, 29, 71, 67), fill="white")
    image.resize((52, 64), Image.Resampling.LANCZOS).save(target / f"marker-{category}.png")
print("Generated three neutral map marker PNG assets.")
