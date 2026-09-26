"""GOV-01: deterministic test data, explicit target safety and standard naming."""

from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image

from backend.app.business.schemas import RESOURCE_SCHEMAS
from scripts.seed_sit import SOURCE, catalog, check_target, display_name, fixture_id
from scripts.seed_sit import test_image as png


def test_tc_seed_001_catalog_has_53_unique_standard_identifiers():
    rows = catalog()
    assert len(rows) == 53
    assert len({payload["id"] for _, payload in rows}) == 53
    assert all(payload["id"].startswith("SIT_V1_") for _, payload in rows)
    assert display_name("DCT", 1, "基础展示") == "【SIT-DCT-001】基础展示"


def test_tc_seed_002_every_fixture_matches_its_resource_contract():
    for resource, payload in catalog():
        RESOURCE_SCHEMAS[resource].model_validate(payload)


def test_tc_seed_003_names_are_stable_and_dates_have_timezone():
    first = catalog(datetime(2026, 9, 24, tzinfo=UTC))
    second = catalog(datetime(2026, 9, 25, tzinfo=UTC))
    assert [p["id"] for _, p in first] == [p["id"] for _, p in second]
    for (_, before), (_, after) in zip(first, second, strict=True):
        for key in ("cn_name", "name", "title"):
            assert before.get(key) == after.get(key)
        if "start_at" in before:
            assert datetime.fromisoformat(before["start_at"]).tzinfo is not None


def test_tc_seed_004_references_stay_in_test_namespace():
    rows = catalog()
    ids = {payload["id"] for _, payload in rows}
    for _, payload in rows:
        for key in ("merchant_id", "quest_id", "poi_id", "character_id"):
            if payload.get(key):
                assert payload[key] in ids
        assert set(payload.get("character_ids", [])) <= ids


def test_tc_seed_005_cultural_records_are_explicitly_synthetic():
    for resource, payload in catalog():
        if resource == "characters":
            assert payload["source_ref"] == SOURCE
            assert "不是真实东巴字" in payload["culture_summary"]


def test_tc_seed_006_generated_images_are_distinct_valid_pngs():
    one = png(fixture_id("DCT", 1))
    two = png(fixture_id("DCT", 1), 1)
    assert one != two
    with Image.open(BytesIO(one)) as image:
        assert image.format == "PNG" and image.size == (640, 400)


@pytest.mark.parametrize(
    "target",
    [
        "https://example.com",
        "http://39.96.83.196:8010",
        "http://user:secret@localhost",
        "http://localhost/api",
        "http://localhost?token=x",
    ],
)
def test_tc_seed_007_refuses_remote_or_credential_bearing_targets(target):
    with pytest.raises(ValueError):
        check_target(target)


def test_tc_seed_008_loopback_target_is_supported():
    check_target("http://127.0.0.1:8010")
