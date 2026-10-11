import base64
import hashlib
import json
from io import BytesIO

from PIL import Image, ImageDraw

from backend.app.glyph_prototypes import (
    PrototypeCandidate,
    image_feature,
    rank_prototype_classes,
    select_representative_prototypes,
)
from scripts.package_glyph_prototypes import package


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


def encoded(raw):
    return base64.b64encode(image_feature(raw)).decode("ascii")


def test_prototype_ranking_collapses_classes_and_returns_nearest_source():
    query = glyph(horizontal=True)
    classes = [
        {
            "character_id": "B",
            "prototypes": [
                {"source": "B/far.png", "sha256": "b1", "feature": encoded(glyph())},
                {"source": "B/near.png", "sha256": "b2", "feature": encoded(query)},
            ],
        },
        {
            "character_id": "A",
            "prototypes": [{"source": "A/one.png", "sha256": "a1", "feature": encoded(glyph())}],
        },
    ]
    ranked = rank_prototype_classes(query, classes, limit=200)
    assert [item.character_id for item in ranked] == ["B", "A"]
    assert ranked[0].source == "B/near.png"
    assert len({item.character_id for item in ranked}) == len(ranked)


def test_prototype_ranking_is_deterministic_skips_bad_and_honors_limit():
    query = glyph(horizontal=True)
    classes = [
        {"character_id": "BROKEN", "prototypes": [{"feature": "not base64"}]},
        {
            "character_id": "B",
            "prototypes": [{"source": "b", "sha256": "same", "feature": encoded(query)}],
        },
        {
            "character_id": "A",
            "prototypes": [{"source": "a", "sha256": "other", "feature": encoded(query)}],
        },
    ]
    first = rank_prototype_classes(query, classes, limit=1, excluded_sha256={"same"})
    second = rank_prototype_classes(
        query, list(reversed(classes)), limit=1, excluded_sha256={"same"}
    )
    assert first == second
    assert [item.character_id for item in first] == ["A"]


def test_prototype_ranking_limits_to_200_unique_classes():
    query = glyph(horizontal=True)
    classes = [
        {
            "character_id": f"C{index:03d}",
            "prototypes": [
                {
                    "source": f"{index}.png",
                    "sha256": f"sha-{index}",
                    "feature": encoded(glyph(horizontal=True, offset=index % 3)),
                }
            ],
        }
        for index in range(250)
    ]
    ranked = rank_prototype_classes(query, classes, limit=200)
    assert len(ranked) == 200
    assert len({item.character_id for item in ranked}) == 200


def test_representative_selection_is_diverse_deterministic_and_bounded():
    candidates = [
        PrototypeCandidate(source=f"{index}.png", feature=bytes([index] * 4)) for index in range(10)
    ]
    selected = select_representative_prototypes(candidates, count=3, trim_fraction=0.1)
    again = select_representative_prototypes(list(reversed(candidates)), count=3, trim_fraction=0.1)
    assert selected == again
    assert len(selected) == 3
    assert len({item.source for item in selected}) == 3
    assert select_representative_prototypes(candidates, count=0) == []


def test_blank_and_corrupt_images_have_no_feature():
    blank = BytesIO()
    Image.new("L", (20, 20), 255).save(blank, format="PNG")
    assert image_feature(blank.getvalue()) is None
    assert image_feature(b"not an image") is None


def test_package_builds_path_independent_deployable_assets(tmp_path):
    source = tmp_path / "dataset"
    source_file = source / "0001" / "sample.jpg"
    source_file.parent.mkdir(parents=True)
    raw = glyph(horizontal=True)
    with Image.open(BytesIO(raw)) as opened:
        opened.convert("L").save(source_file, format="JPEG")
    source_raw = source_file.read_bytes()
    index_path = tmp_path / "source-index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "feature_side": 16,
                "classes": [
                    {
                        "character_id": "DB1404_0001",
                        "prototypes": [
                            {
                                "source": "0001/sample.jpg",
                                "sha256": hashlib.sha256(source_raw).hexdigest(),
                                "feature": encoded(source_raw),
                            }
                        ],
                    }
                ],
                "stats": {"class_count": 1, "prototype_count": 1},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "bundle"
    artifact = package(source, index_path, output)
    packaged = artifact["classes"][0]["prototypes"][0]
    assert artifact["asset_format"] == "files-v1"
    assert "source" not in packaged
    assert packaged["asset"].startswith("assets/")
    assert (output / packaged["asset"]).read_bytes() == source_raw
    assert "dataset" not in (output / "index.json").read_text(encoding="utf-8")
