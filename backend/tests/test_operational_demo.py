"""QUEST-01/02, MERCHANT-01, GEO-01, OPS-02 demo catalog expansion.

Recognition records in these tests are fixtures, not accuracy evidence.
MySQL uses the existing explicitly gated, isolated dongba_test fixture.
"""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from backend.app.business.models import Entity, EntityRevision, User
from backend.app.business.schemas import RESOURCE_SCHEMAS
from backend.app.business.workflows import statistics
from backend.tests import test_business_api as business_tests
from scripts.seed_operational_demo import (
    active_admin,
    catalog_counts,
    load_catalog,
    seed,
    seed_entities,
)

# Reuse the guarded dongba_test fixture without collecting its test module twice.
context = business_tests.context

EXPECTED = {
    "merchants": 8,
    "products": 16,
    "pois": 14,
    "activities": 12,
    "coupons": 12,
    "quests": 3,
    "quest_nodes": 11,
}


def test_catalog_relationships_and_explicit_demo_labels():
    data = load_catalog(datetime.now(UTC))
    assert catalog_counts(data) == EXPECTED
    ids = set()
    by_id = {}
    for resource in EXPECTED:
        for row in data[resource]:
            assert row["id"] not in ids
            ids.add(row["id"])
            by_id[row["id"]] = row
            payload = {k: v for k, v in row.items() if k not in {"username", "display_name"}}
            RESOURCE_SCHEMAS[resource.replace("_", "-")].model_validate(payload)
    for resource in EXPECTED:
        for row in data[resource]:
            for field in ("merchant_id", "poi_id", "quest_id", "reward_coupon_id"):
                if row.get(field):
                    assert row[field] in by_id
    for quest in data["quests"]:
        nodes = [n for n in data["quest_nodes"] if n["quest_id"] == quest["id"]]
        assert [n["sequence"] for n in nodes] == list(range(1, len(nodes) + 1))
        assert {n["condition"] for n in nodes} == {"qr", "recognition", "geofence"}
        assert "演示" in quest["name"]
        reward = by_id[quest["reward_coupon_id"]]
        assert reward["start_at"] <= quest["start_at"] < quest["end_at"] <= reward["end_at"]
    for resource, start in (("merchants", 4), ("products", 8), ("coupons", 8), ("activities", 4)):
        for row in data[resource][start:]:
            assert "演示" in row.get("name", row.get("title", ""))
    assert len([p for p in data["pois"] if p["poi_type"] == "culture"]) == 6
    assert all(not p["merchant_id"] for p in data["pois"] if p["poi_type"] == "culture")
    assert all("qr_token" not in node for node in data["quest_nodes"])


def test_content_expansion_preserves_old_route_and_completes_new_journeys(context):
    ctx = context
    instant = datetime.now(UTC)
    data = load_catalog(instant)
    characters = {
        char
        for resource in ("merchants", "products", "pois")
        for row in data[resource]
        for char in row["character_ids"]
    }
    for char in sorted(characters):
        ctx.create(
            "characters",
            {
                "id": char,
                "cn_name": "Fixture glyph",
                "culture_summary": "Test only",
                "source_ref": "synthetic:test",
                "image_url": "/api/v1/media/fixture-glyph.png",
                "status": "published",
            },
        )
    old = deepcopy(data)
    for resource, length in {
        "merchants": 4,
        "products": 8,
        "pois": 4,
        "activities": 4,
        "coupons": 8,
        "quests": 1,
        "quest_nodes": 3,
    }.items():
        old[resource] = old[resource][:length]
    database = ctx.app.state.database
    with database.write() as session:
        seed_entities(session, old, active_admin(session), {})
        before = {
            row.id: deepcopy(row.data)
            for row in session.scalars(select(Entity).where(Entity.kind != "characters"))
        }
    tourist, headers = ctx.actor()
    route_id = data["quests"][0]["id"]
    assert ctx.client.post(f"/api/v1/quests/{route_id}/join", headers=headers).status_code == 200
    with database.session() as session:
        metrics_before = statistics(session)
        users_before = session.scalar(select(func.count()).select_from(User))
    with database.write() as session:
        result, credentials = seed(session, instant + timedelta(days=1), content_only=True)
        assert credentials == []
        assert result["verified"] == EXPECTED
        assert result["created"] == {
            "merchants": 4,
            "pois": 10,
            "products": 8,
            "activities": 8,
            "coupons": 4,
            "quests": 2,
            "quest-nodes": 8,
        }
        assert statistics(session) == metrics_before
        assert session.scalar(select(func.count()).select_from(User)) == users_before
        for entity_id, payload in before.items():
            assert session.get(Entity, entity_id).data == payload
        revision_count = session.scalar(select(func.count()).select_from(EntityRevision))
    with database.write() as session:
        rerun, _ = seed(session, instant + timedelta(days=2), content_only=True)
        assert rerun["created"] == {}
        assert session.scalar(select(func.count()).select_from(EntityRevision)) == revision_count
    for resource in ("quests", "merchants", "activities", "products", "coupons"):
        response = ctx.client.get(f"/api/v1/{resource}")
        assert response.status_code == 200
        assert response.json()["total"] == EXPECTED[resource]
    assert ctx.client.get("/api/v1/map/pois").json()["total"] == EXPECTED["pois"]
    pois = {p["id"]: p for p in data["pois"]}
    for quest in data["quests"][1:]:
        route_id = quest["id"]
        detail = ctx.client.get(f"/api/v1/quests/{route_id}").json()
        assert len(detail["nodes"]) == 4
        assert all("qr_token" not in node for node in detail["nodes"])
        assert (
            ctx.client.post(f"/api/v1/quests/{route_id}/join", headers=headers).status_code == 200
        )
        for node in detail["nodes"]:
            payload = {"node_id": node["id"]}
            if node["condition"] == "qr":
                with database.session() as session:
                    token = session.get(Entity, node["id"]).data["qr_token"]
                    assert len(token) >= 16
                payload["qr_token"] = token
            elif node["condition"] == "geofence":
                poi = pois[node["poi_id"]]
                payload.update(latitude=poi["latitude"], longitude=poi["longitude"])
            else:
                payload["recognition_id"] = ctx.record(
                    tourist["id"], node["character_id"], confirmed=True
                )
            response = ctx.client.post(
                f"/api/v1/quests/{route_id}/checkin", json=payload, headers=headers
            )
            assert response.status_code == 200, response.text
        repeated = ctx.client.post(
            f"/api/v1/quests/{route_id}/checkin", json=payload, headers=headers
        )
        assert repeated.status_code == 200
    coupons = ctx.client.get("/api/v1/me/coupons", headers=headers).json()["items"]
    assert sorted(c["coupon_id"] for c in coupons) == sorted(
        quest["reward_coupon_id"] for quest in data["quests"][1:]
    )
