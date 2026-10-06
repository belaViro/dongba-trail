"""SHARE-01 / D-062: approved reference assets, full AI artwork, and genuine code only."""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from backend.app.errors import ApiError
from backend.app.media import local_asset

REFERENCE_PATH = Path(__file__).resolve().parents[1] / "assets" / "poster-reference.jpg"


def png_material(name, image):
    output = BytesIO()
    clean = image.copy()
    clean.info.clear()  # Only approved pixels, not EXIF/profile metadata, go upstream.
    clean.save(output, format="PNG")
    return name, output.getvalue(), "image/png"


def poster_materials(settings, records):
    try:
        with Image.open(REFERENCE_PATH) as reference:
            reference.load()
            materials = [png_material("design-reference.png", reference.convert("RGB"))]
    except (OSError, ValueError) as exc:
        raise ApiError(503, "POSTER_REFERENCE_UNAVAILABLE", "Poster reference unavailable") from exc
    for index, record in enumerate(records, 1):
        try:
            with Image.open(local_asset(settings, record["image_url"])) as glyph:
                glyph.load()
                clean = ImageOps.exif_transpose(glyph).convert("RGBA")
                clean.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                materials.append(png_material(f"glyph-{index}.png", clean))
        except (OSError, ValueError) as exc:
            raise ApiError(409, "CHARACTER_IMAGE_UNAVAILABLE", "Glyph image unavailable") from exc
    return materials


def share_code_material(code):
    with Image.open(BytesIO(code)) as image:
        image.load()
        return png_material("mini-program-code.png", image.convert("RGB"))


def finish_poster(artwork, code):
    """Preserve the whole AI design. Only restore a real code's exact machine-readable pixels."""
    image = artwork.convert("RGB")
    if code is not None:
        with Image.open(BytesIO(code)) as original:
            original.load()
            side = round(image.width * 0.18)
            square = ImageOps.pad(
                original.convert("RGB"),
                (side, side),
                method=Image.Resampling.NEAREST,
                color="white",
            )
            margin = round(image.width * 0.04)
            image.paste(square, (image.width - side - margin, image.height - side - margin))
    return image
