import base64
import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO

from PIL import Image, ImageDraw

from backend.app.glyph_prototypes import image_feature
from backend.app.glyph_refs import build_reference_sheets, load_references
from backend.app.schemas import Character


def glyph(horizontal=False, offset=0):
    image = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(image)
    if horizontal:
        draw.rectangle((10, 29 + offset, 54, 34 + offset), fill=0)
    else:
        draw.rectangle((29 + offset, 10, 34 + offset, 54), fill=0)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def character(character_id, image_url=""):
    return Character(
        character_id=character_id,
        cn_name=character_id,
        culture_summary="Fixture only",
        source_ref="Fixture only",
        status="published",
        reviewed_by="fixture",
        reviewed_at=datetime(2026, 1, 1, tzinfo=UTC),
        image_url=image_url,
    )


def prototype(asset, raw):
    return {
        "asset": asset,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "feature": base64.b64encode(image_feature(raw)).decode("ascii"),
    }


def write_bundle(directory, classes, assets):
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in assets.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (directory / "index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "feature_side": 16,
                "asset_format": "files-v1",
                "classes": classes,
            }
        ),
        encoding="utf-8",
    )


def test_runtime_uses_query_nearest_prototype_image(tmp_path):
    bundle = tmp_path / "bundle"
    horizontal = glyph(horizontal=True)
    vertical = glyph()
    classes = [
        {
            "character_id": "BB",
            "prototypes": [
                prototype("assets/b-far.png", vertical),
                prototype("assets/b-near.png", horizontal),
            ],
        },
        {"character_id": "AA", "prototypes": [prototype("assets/a.png", vertical)]},
        {"character_id": "CC", "prototypes": [prototype("assets/c.png", vertical)]},
    ]
    write_bundle(
        bundle,
        classes,
        {
            "assets/b-far.png": vertical,
            "assets/b-near.png": horizontal,
            "assets/a.png": vertical,
            "assets/c.png": vertical,
        },
    )
    references = load_references(
        [character("AA"), character("BB"), character("CC")],
        tmp_path / "media",
        limit=2,
        query=horizontal,
        prototype_directory=bundle,
    )
    assert references[0].character_id == "BB"
    assert image_feature(references[0].image) != image_feature(vertical)
    assert len({item.character_id for item in references}) == 2


def test_runtime_returns_200_unique_classes_and_ten_sheets(tmp_path):
    bundle = tmp_path / "bundle"
    raw = glyph(horizontal=True)
    classes = [
        {
            "character_id": f"C{index:03d}",
            "prototypes": [prototype("assets/shared.png", raw)],
        }
        for index in range(205)
    ]
    write_bundle(bundle, classes, {"assets/shared.png": raw})
    references = load_references(
        [character(f"C{index:03d}") for index in range(205)],
        tmp_path / "media",
        query=raw,
        prototype_directory=bundle,
    )
    assert len(references) == 200
    assert len({item.character_id for item in references}) == 200
    assert len(build_reference_sheets(references)) == 10


def test_missing_or_corrupt_bundle_falls_back_without_persisting_query(tmp_path, caplog):
    media = tmp_path / "media"
    media.mkdir()
    raw = glyph(horizontal=True)
    primary = media / "a.png"
    primary.write_bytes(raw)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.json").write_text("not json", encoding="utf-8")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    references = load_references(
        [character("AA", "/api/v1/media/a.png")],
        media,
        query=raw,
        prototype_directory=bundle,
    )
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert [item.character_id for item in references] == ["AA"]
    assert before == after
    assert "glyph_prototype_bundle_unavailable" in caplog.text
    assert hashlib.sha256(raw).hexdigest() not in caplog.text


def test_incomplete_bundle_falls_back_to_primary_images(tmp_path, caplog):
    media = tmp_path / "media"
    media.mkdir()
    raw = glyph(horizontal=True)
    (media / "a.png").write_bytes(raw)
    (media / "b.png").write_bytes(glyph())
    bundle = tmp_path / "bundle"
    write_bundle(
        bundle,
        [{"character_id": "AA", "prototypes": [prototype("assets/a.png", raw)]}],
        {"assets/a.png": raw},
    )
    references = load_references(
        [
            character("AA", "/api/v1/media/a.png"),
            character("BB", "/api/v1/media/b.png"),
        ],
        media,
        limit=2,
        query=raw,
        prototype_directory=bundle,
    )
    assert [item.character_id for item in references] == ["AA", "BB"]
    assert "glyph_prototype_bundle_incomplete" in caplog.text


def test_bundle_rejects_asset_path_traversal_and_falls_back(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    raw = glyph(horizontal=True)
    (media / "a.png").write_bytes(raw)
    bundle = tmp_path / "bundle"
    classes = [{"character_id": "AA", "prototypes": [prototype("assets/../outside.png", raw)]}]
    write_bundle(bundle, classes, {})
    references = load_references(
        [character("AA", "/api/v1/media/a.png")],
        media,
        query=raw,
        prototype_directory=bundle,
    )
    assert [item.character_id for item in references] == ["AA"]
