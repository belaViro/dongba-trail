from io import BytesIO

from PIL import Image

from scripts.enrich_operational_demo_images import EXPECTED_ENTITIES, load_manifest, prepare_image


def test_operational_image_manifest_covers_demo_merchants_and_products():
    manifest = load_manifest()

    assert manifest["license_url"] == "https://unsplash.com/license"
    assert {item["entity_id"]: item["resource"] for item in manifest["images"]} == (
        EXPECTED_ENTITIES
    )
    by_id = {item["entity_id"]: item for item in manifest["images"]}
    assert by_id["OPS_PRODUCT_TEA_PACK"]["source_url"] != by_id["OPS_MERCHANT_TEA"]["source_url"]


def test_prepare_image_normalizes_and_crops_source():
    source = Image.new("RGB", (900, 900), "#bd8857")
    encoded = BytesIO()
    source.save(encoded, format="JPEG")

    result = prepare_image(encoded.getvalue())

    assert result.mode == "RGB"
    assert result.size == (1200, 800)
