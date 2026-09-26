"""Business acceptance tests use synthetic fixtures, never production cultural data."""

import csv
import io
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url

from backend.app.business import Database
from backend.app.business.models import Base, Claim, CouponStock, Entity, Event, User
from backend.app.business.schemas import Checkin
from backend.app.business.workflows import claim_coupon, complete_node, verify_coupon
from backend.app.config import Settings
from backend.app.errors import ApiError
from backend.app.main import create_app

PASSWORD = "test-only-password-123"
ROOT = Path(__file__).resolve().parents[2]


class Context:
    def __init__(self, app, client):
        self.app, self.client = app, client
        response = client.post(
            "/api/v1/auth/setup",
            json={"username": "test_admin", "password": PASSWORD, "display_name": "Test admin"},
        )
        assert response.status_code == 200, response.text
        self.admin_user = response.json()["user"]
        self.admin = {"Authorization": "Bearer " + response.json()["access_token"]}

    def create(self, resource, data):
        response = self.client.post(f"/api/v1/admin/{resource}", json=data, headers=self.admin)
        assert response.status_code == 200, response.text
        return response.json()

    def actor(self, role="tourist", merchant_id=None):
        data = {
            "username": "test_" + uuid4().hex[:12],
            "password": PASSWORD,
            "display_name": "Fixture user",
            "role": role,
        }
        if merchant_id:
            data["merchant_id"] = merchant_id
        user = self.create("users", data)
        response = self.client.post(
            "/api/v1/auth/login", json={"username": data["username"], "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        return user, {"Authorization": "Bearer " + response.json()["access_token"]}

    def character(self, status="published"):
        return self.create(
            "characters",
            {
                "cn_name": "Fixture glyph",
                "culture_summary": "Test only",
                "source_ref": "synthetic:test",
                "image_url": "/api/v1/media/fixture-glyph.png",
                "status": status,
            },
        )

    def merchant(self, characters=None):
        return self.create(
            "merchants",
            {
                "name": "Fixture shop",
                "latitude": 26.87,
                "longitude": 100.23,
                "status": "published",
                "character_ids": characters or [],
            },
        )

    def coupon(self, merchant_id, stock=5, limit=1):
        return self.create(
            "coupons",
            {
                "merchant_id": merchant_id,
                "title": "Fixture coupon",
                "rule": "Synthetic testing only",
                "stock": stock,
                "per_user_limit": limit,
                "status": "published",
                **period(),
            },
        )

    def quest(self, reward_coupon_id=None):
        return self.create(
            "quests",
            {
                "name": "Fixture quest",
                "status": "published",
                "reward_coupon_id": reward_coupon_id,
                **period(),
            },
        )

    def node(self, quest_id, condition, **extra):
        return self.create(
            "quest-nodes",
            {
                "quest_id": quest_id,
                "name": "Fixture node",
                "condition": condition,
                "status": "published",
                **extra,
            },
        )

    def record(self, user_id, character_id, confirmed=False):
        request_id = str(uuid4())
        self.app.state.database.record_recognition(
            request_id=request_id,
            user_id=user_id,
            status="NEED_USER_CONFIRM",
            provider="test",
            model="fixture",
            candidates=[{"character_id": character_id}],
            latency_ms=12,
        )
        if confirmed:
            from backend.app.business.models import RecognitionRecord

            with self.app.state.database.write() as session:
                session.get(RecognitionRecord, request_id).confirmed_character_id = character_id
        return request_id


def period():
    return {
        "start_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "end_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
    }


@pytest.fixture(params=["sqlite", "mysql"])
def context(request, tmp_path):
    if request.param == "mysql":
        if os.getenv("DONGBA_RUN_MYSQL_TESTS") != "1":
            pytest.skip("Set DONGBA_RUN_MYSQL_TESTS=1 to run isolated MySQL integration tests")
        config = dotenv_values(ROOT / ".env")
        url = os.getenv("DONGBA_TEST_DATABASE_URL") or config.get("DONGBA_TEST_DATABASE_URL")
        assert url and make_url(url).database == "dongba_test", "Dedicated test database required"
        engine = create_engine(url)
        Base.metadata.drop_all(engine)
        engine.dispose()
    else:
        url = f"sqlite:///{(tmp_path / 'business.sqlite').as_posix()}"
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=url,
        auto_create_schema=True,
        setup_enabled=True,
        provider_name="unconfigured",
        media_directory=tmp_path / "media",
        request_limit_per_minute=10000,
        privacy_policy_published=True,
        privacy_contact="test@example.invalid",
    )
    app = create_app(settings=settings)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        yield Context(app, client)
    app.state.database.engine.dispose()


def test_setup_is_single_use_and_local(context):
    ctx = context
    assert ctx.client.get("/api/v1/auth/setup-status").json() == {"setup_required": False}
    response = ctx.client.post(
        "/api/v1/auth/setup",
        json={"username": "other_admin", "password": PASSWORD, "display_name": "Second"},
    )
    assert response.status_code == 409
    with TestClient(ctx.app, client=("192.0.2.10", 1000)) as remote:
        response = remote.post(
            "/api/v1/auth/setup",
            json={"username": "third_admin", "password": PASSWORD, "display_name": "Remote"},
        )
        assert response.status_code == 403


def test_auth_revocation_disabled_users_and_password_privacy(context):
    user, headers = context.actor()
    assert "password" not in str(user)
    assert context.client.get("/api/v1/auth/me", headers=headers).json()["id"] == user["id"]
    assert context.client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert context.client.get("/api/v1/auth/me", headers=headers).status_code == 401
    _, second = context.actor()
    assert context.client.get("/api/v1/admin/users", headers=second).status_code == 403
    context.client.patch(
        f"/api/v1/admin/users/{user['id']}", json={"status": "disabled"}, headers=context.admin
    )
    response = context.client.post(
        "/api/v1/auth/login", json={"username": user["username"], "password": PASSWORD}
    )
    assert response.status_code == 401
    with context.app.state.database.session() as session:
        assert PASSWORD not in session.get(User, user["id"]).password_hash


def test_login_failures_are_throttled(context):
    for _ in range(10):
        response = context.client.post(
            "/api/v1/auth/login", json={"username": "missing_user", "password": PASSWORD}
        )
        assert response.status_code == 401
    assert (
        context.client.post(
            "/api/v1/auth/login", json={"username": "missing_user", "password": PASSWORD}
        ).status_code
        == 429
    )


def test_wechat_requires_real_exchange_and_privacy(context):
    client = context.client
    assert (
        client.post(
            "/api/v1/auth/wechat", json={"code": "anything", "privacy_accepted": False}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/wechat", json={"code": "anything", "privacy_accepted": True}
        ).status_code
        == 503
    )
    context.app.state.business_settings.wechat_app_id = "fixture-app"
    context.app.state.business_settings.wechat_app_secret = "fixture-secret"
    received = []

    def exchange(request):
        received.append(request.url.params.get("js_code"))
        return httpx.Response(
            200, json={"openid": "fixture-openid", "session_key": "never-persist"}
        )

    context.app.state.wechat_transport = httpx.MockTransport(exchange)
    response = client.post(
        "/api/v1/auth/wechat", json={"code": "one-time-code", "privacy_accepted": True}
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "tourist"
    assert "openid" not in response.text and "session_key" not in response.text
    assert received == ["one-time-code"]
    context.app.state.wechat_transport = httpx.MockTransport(
        lambda _: httpx.Response(200, json={"errcode": 40029})
    )
    assert (
        client.post(
            "/api/v1/auth/wechat", json={"code": "bad-code", "privacy_accepted": True}
        ).status_code
        == 401
    )


def test_cultural_review_publication_and_tenant_isolation(context):
    draft = context.character("draft")
    assert context.client.get(f"/api/v1/characters/{draft['id']}").status_code == 404
    published = context.character()
    merchant = context.merchant([published["id"]])
    other_merchant = context.merchant()
    _, owner = context.actor("merchant", merchant["id"])
    _, stranger = context.actor("merchant", other_merchant["id"])
    product = context.create(
        "products",
        {"merchant_id": merchant["id"], "name": "Fixture product", "status": "published"},
    )
    assert (
        context.client.patch(
            f"/api/v1/merchant/products/{product['id']}", json={"name": "Stolen"}, headers=stranger
        ).status_code
        == 404
    )
    assert context.client.get("/api/v1/merchant/products", headers=stranger).json()["total"] == 0
    assert (
        context.client.patch(
            "/api/v1/merchant/profile", json={"character_ids": []}, headers=owner
        ).status_code
        == 403
    )
    assert (
        context.client.patch(
            "/api/v1/merchant/profile", json={"status": "published"}, headers=owner
        ).status_code
        == 403
    )
    changed = context.client.patch(
        f"/api/v1/merchant/products/{product['id']}", json={"price": 15}, headers=owner
    )
    assert changed.status_code == 200 and changed.json()["status"] == "draft"
    assert context.client.get(f"/api/v1/products/{product['id']}").status_code == 404
    assert context.client.get("/api/v1/admin/audit", headers=context.admin).json()["total"] > 0


def test_cultural_relationship_review_and_nearby(context):
    character = context.character()
    merchant = context.merchant()
    _, owner = context.actor("merchant", merchant["id"])
    assert context.client.get(f"/api/v1/characters/{character['id']}/nearby").json()["total"] == 0
    claim = context.client.post(
        "/api/v1/merchant/tag-claims", json={"character_id": character["id"]}, headers=owner
    ).json()
    response = context.client.patch(
        f"/api/v1/admin/tag-claims/{claim['id']}",
        json={"status": "approved"},
        headers=context.admin,
    )
    assert response.status_code == 200
    nearby = context.client.get(
        f"/api/v1/characters/{character['id']}/nearby?latitude=26.87&longitude=100.23"
    ).json()
    assert nearby["items"][0]["id"] == merchant["id"]
    assert nearby["items"][0]["distance_m"] == 0
    context.client.delete(f"/api/v1/admin/merchants/{merchant['id']}", headers=context.admin)
    assert context.client.get(f"/api/v1/characters/{character['id']}/nearby").json()["total"] == 0


def test_coupon_limits_expiry_and_idempotent_owned_redemption(context):
    merchant, other = context.merchant(), context.merchant()
    coupon = context.coupon(merchant["id"], stock=1)
    tourist, headers = context.actor()
    _, owner = context.actor("merchant", merchant["id"])
    _, stranger = context.actor("merchant", other["id"])
    claim = context.client.post(f"/api/v1/coupons/{coupon['id']}/claim", headers=headers)
    assert claim.status_code == 200
    listed = context.client.get(f"/api/v1/coupons/{coupon['id']}")
    assert listed.status_code == 200
    assert listed.json()["remaining_count"] == 0
    assert (
        context.client.post(f"/api/v1/coupons/{coupon['id']}/claim", headers=headers).json()["code"]
        == "CLAIM_LIMIT"
    )
    assert (
        context.client.post(
            "/api/v1/coupons/verify", json={"code": claim.json()["code"]}, headers=stranger
        ).status_code
        == 404
    )
    first = context.client.post(
        "/api/v1/coupons/verify", json={"code": claim.json()["code"]}, headers=owner
    )
    second = context.client.post(
        "/api/v1/coupons/verify", json={"code": claim.json()["code"]}, headers=owner
    )
    assert first.json()["already_verified"] is False
    assert second.json()["already_verified"] is True
    assert context.client.get("/api/v1/merchant/redemptions", headers=owner).json()["total"] == 1
    assert context.client.get("/api/v1/merchant/stats", headers=owner).json()["redemptions"] == 1
    assert context.client.get("/api/v1/merchant/stats", headers=stranger).json()["redemptions"] == 0
    assert (
        context.client.patch(
            f"/api/v1/admin/coupons/{coupon['id']}", json={"stock": 0}, headers=context.admin
        ).status_code
        == 409
    )
    assert (
        context.client.patch(
            f"/api/v1/admin/coupons/{coupon['id']}",
            json={"merchant_id": other["id"]},
            headers=context.admin,
        ).status_code
        == 409
    )
    assert (
        context.client.get("/api/v1/me/coupons", headers=headers).json()["items"][0]["user_id"]
        == tourist["id"]
    )


def test_expired_coupons_cannot_be_claimed(context):
    merchant = context.merchant()
    coupon = context.create(
        "coupons",
        {
            "merchant_id": merchant["id"],
            "title": "Expired",
            "rule": "Test",
            "stock": 1,
            "status": "published",
            "start_at": "2020-01-01T00:00:00Z",
            "end_at": "2020-01-02T00:00:00Z",
        },
    )
    _, headers = context.actor()
    assert (
        context.client.post(f"/api/v1/coupons/{coupon['id']}/claim", headers=headers).json()["code"]
        == "NOT_ACTIVE"
    )


def run_workers(context, count, action):
    barrier = Barrier(count)
    database_url = context.app.state.business_settings.database_url

    def work(index):
        db = Database(database_url)
        try:
            barrier.wait(timeout=20)
            with db.write() as session:
                return action(session, index)
        except ApiError as exc:
            return exc.code
        finally:
            db.engine.dispose()

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(work, range(count)))


def test_parallel_claims_never_oversell_across_database_instances(context):
    merchant = context.merchant()
    coupon = context.coupon(merchant["id"], stock=3)
    users = [context.actor()[0] for _ in range(8)]
    results = run_workers(
        context, 8, lambda session, i: claim_coupon(session, coupon["id"], users[i]["id"]).id
    )
    assert results.count("SOLD_OUT") == 5
    with context.app.state.database.session() as session:
        assert session.get(CouponStock, coupon["id"]).claimed_count == 3
        assert len(session.scalars(select(Claim)).all()) == 3


def test_parallel_same_user_claim_and_verify_are_idempotent(context):
    merchant = context.merchant()
    coupon = context.coupon(merchant["id"], stock=10)
    tourist, _ = context.actor()
    owner, _ = context.actor("merchant", merchant["id"])
    results = run_workers(
        context, 6, lambda session, _: claim_coupon(session, coupon["id"], tourist["id"]).id
    )
    assert results.count("CLAIM_LIMIT") == 5
    with context.app.state.database.session() as session:
        claim = session.scalar(select(Claim))
        code = claim.code
    results = run_workers(
        context,
        6,
        lambda session, _: verify_coupon(session, code, session.get(User, owner["id"]))[
            "already_verified"
        ],
    )
    assert results.count(False) == 1 and results.count(True) == 5


def test_recognition_feedback_history_and_favorites_are_private(context):
    character, unrelated = context.character(), context.character()
    tourist, headers = context.actor()
    _, stranger = context.actor()
    request_id = context.record(tourist["id"], character["id"])
    endpoint = f"/api/v1/recognize/{request_id}/confirm"
    assert (
        context.client.post(
            endpoint, json={"character_id": character["id"]}, headers=stranger
        ).status_code
        == 404
    )
    assert (
        context.client.post(
            endpoint, json={"character_id": unrelated["id"]}, headers=headers
        ).status_code
        == 422
    )
    feedback = context.client.post(
        endpoint, json={"character_id": character["id"]}, headers=headers
    ).json()
    assert feedback["status"] == "pending"
    assert context.client.get("/api/v1/me/history", headers=stranger).json()["total"] == 0
    assert (
        context.client.put(f"/api/v1/me/favorites/{character['id']}", headers=headers).status_code
        == 200
    )
    assert context.client.get("/api/v1/me/favorites", headers=stranger).json()["total"] == 0
    assert context.app.state.database.allowed_poster_character_ids(tourist["id"]) == {
        character["id"]
    }
    context.client.delete("/api/v1/me/history", headers=headers)
    assert context.client.get("/api/v1/me/history", headers=headers).json()["total"] == 0
    assert context.client.get("/api/v1/admin/feedback", headers=context.admin).json()["total"] == 0
    context.client.delete(f"/api/v1/me/favorites/{character['id']}", headers=headers)
    assert context.app.state.database.allowed_poster_character_ids(tourist["id"]) == set()


def test_all_quest_conditions_and_rewards(context):
    character, merchant = context.character(), context.merchant()
    reward = context.coupon(merchant["id"], stock=10)
    quest = context.quest(reward["id"])
    nodes = {
        "recognition": context.node(quest["id"], "recognition", character_id=character["id"]),
        "qr": context.node(quest["id"], "qr"),
        "geofence": context.node(quest["id"], "geofence", merchant_id=merchant["id"]),
        "coupon": context.node(quest["id"], "coupon", merchant_id=merchant["id"]),
        "manual": context.node(quest["id"], "manual"),
    }
    tourist, headers = context.actor()
    _, owner = context.actor("merchant", merchant["id"])
    assert "qr_token" not in str(context.client.get(f"/api/v1/quests/{quest['id']}").json())
    check_url = f"/api/v1/quests/{quest['id']}/checkin"
    assert (
        context.client.post(check_url, json={"node_id": nodes["qr"]["id"]}, headers=headers).json()[
            "code"
        ]
        == "JOIN_REQUIRED"
    )
    context.client.post(f"/api/v1/quests/{quest['id']}/join", headers=headers)
    assert (
        context.client.post(
            check_url, json={"node_id": nodes["manual"]["id"]}, headers=headers
        ).status_code
        == 403
    )
    assert (
        context.client.post(
            check_url, json={"node_id": nodes["qr"]["id"], "qr_token": "bad"}, headers=headers
        ).status_code
        == 409
    )
    assert (
        context.client.post(
            check_url,
            json={"node_id": nodes["geofence"]["id"], "latitude": 0, "longitude": 0},
            headers=headers,
        ).status_code
        == 409
    )
    request_id = context.record(tourist["id"], character["id"], confirmed=True)
    claim = context.client.post(f"/api/v1/coupons/{reward['id']}/claim", headers=headers).json()
    context.client.post("/api/v1/coupons/verify", json={"code": claim["code"]}, headers=owner)
    payloads = [
        {"node_id": nodes["recognition"]["id"], "recognition_id": request_id},
        {"node_id": nodes["qr"]["id"], "qr_token": nodes["qr"]["qr_token"]},
        {"node_id": nodes["geofence"]["id"], "latitude": 26.87, "longitude": 100.23},
        {"node_id": nodes["coupon"]["id"], "claim_id": claim["id"]},
    ]
    for payload in payloads:
        response = context.client.post(check_url, json=payload, headers=headers)
        assert response.status_code == 200, response.text
    response = context.client.post(
        f"/api/v1/admin/quests/{quest['id']}/complete-node",
        json={"user_id": tourist["id"], "node_id": nodes["manual"]["id"]},
        headers=context.admin,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    assert response.json()["reward_claim_id"]
    repeat = context.client.post(check_url, json=payloads[0], headers=headers)
    assert repeat.json()["already_completed"] is True
    assert context.client.get("/api/v1/me/stamps", headers=headers).json()["total"] == 5
    assert context.client.get("/api/v1/me/coupons", headers=headers).json()["total"] == 2


def test_parallel_quest_completion_rewards_once(context):
    merchant = context.merchant()
    coupon = context.coupon(merchant["id"], stock=10)
    quest = context.quest(coupon["id"])
    node = context.node(quest["id"], "qr")
    tourist, headers = context.actor()
    context.client.post(f"/api/v1/quests/{quest['id']}/join", headers=headers)
    payload = Checkin(node_id=node["id"], qr_token=node["qr_token"])
    results = run_workers(
        context,
        6,
        lambda session, _: complete_node(
            session, quest["id"], payload, session.get(User, tourist["id"])
        )["already_completed"],
    )
    assert results.count(False) == 1 and results.count(True) == 5
    with context.app.state.database.session() as session:
        assert session.get(CouponStock, coupon["id"]).claimed_count == 1


def test_quest_rules_freeze_and_manual_cannot_bypass_conditions(context):
    quest = context.quest()
    node = context.node(quest["id"], "qr")
    tourist, headers = context.actor()
    context.client.post(f"/api/v1/quests/{quest['id']}/join", headers=headers)
    assert (
        context.client.patch(
            f"/api/v1/admin/quest-nodes/{node['id']}",
            json={"condition": "manual"},
            headers=context.admin,
        ).status_code
        == 409
    )
    assert (
        context.client.delete(
            f"/api/v1/admin/quest-nodes/{node['id']}", headers=context.admin
        ).status_code
        == 409
    )
    response = context.client.post(
        f"/api/v1/admin/quests/{quest['id']}/complete-node",
        json={"user_id": tourist["id"], "node_id": node["id"]},
        headers=context.admin,
    )
    assert response.json()["code"] == "MANUAL_NOT_ALLOWED"


def test_events_dedupe_and_conversion_cannot_be_forged(context):
    merchant = context.merchant()
    _, headers = context.actor()
    payload = {
        "event": "navigate",
        "event_id": str(uuid4()),
        "entity_type": "merchants",
        "entity_id": merchant["id"],
    }
    assert (
        context.client.post("/api/v1/events", json=payload, headers=headers).json()["duplicate"]
        is False
    )
    assert (
        context.client.post("/api/v1/events", json=payload, headers=headers).json()["duplicate"]
        is True
    )
    assert (
        context.client.post(
            "/api/v1/events", json={**payload, "event": "verify"}, headers=headers
        ).status_code
        == 422
    )
    with context.app.state.database.session() as session:
        assert len(session.scalars(select(Event).where(Event.event == "navigate")).all()) == 1


def test_settings_reject_unknown_keys_and_invalid_weights(context):
    assert (
        context.client.patch(
            "/api/v1/admin/settings", json={"api_key": "secret"}, headers=context.admin
        ).status_code
        == 422
    )
    assert (
        context.client.patch(
            "/api/v1/admin/settings", json={"distance_score": 1}, headers=context.admin
        ).status_code
        == 422
    )
    response = context.client.patch(
        "/api/v1/admin/settings",
        json={"distance_score": 0.20, "cultural_relevance": 0.40},
        headers=context.admin,
    )
    assert response.status_code == 200
    assert response.json()["cultural_relevance"] == 0.40


def test_persistence_survives_new_database_instance(context):
    character = context.character()
    second = Database(context.app.state.business_settings.database_url)
    try:
        assert second.published_characters()[0]["character_id"] == character["id"]
        with second.session() as session:
            assert session.get(Entity, character["id"]).reviewed_by == context.admin_user["id"]
    finally:
        second.engine.dispose()


def test_missing_glyph_and_coordinates_cannot_be_published(context):
    response = context.client.post(
        "/api/v1/admin/characters",
        headers=context.admin,
        json={
            "cn_name": "No image",
            "culture_summary": "Test",
            "source_ref": "test",
            "status": "published",
        },
    )
    assert response.json()["code"] == "GLYPH_REQUIRED"
    response = context.client.post(
        "/api/v1/admin/merchants",
        headers=context.admin,
        json={
            "name": "No location",
            "status": "published",
        },
    )
    assert response.json()["code"] == "LOCATION_REQUIRED"
    draft = context.create("merchants", {"name": "Draft location"})
    assert draft["latitude"] is None and draft["longitude"] is None


def test_events_same_identifier_are_scoped_per_user(context):
    _, first = context.actor()
    _, second = context.actor()
    payload = {"event": "home_view", "event_id": str(uuid4())}
    assert (
        context.client.post("/api/v1/events", json=payload, headers=first).json()["duplicate"]
        is False
    )
    assert (
        context.client.post("/api/v1/events", json=payload, headers=second).json()["duplicate"]
        is False
    )


def test_earned_reward_retries_after_quest_expiry_without_repeating_stamps(context):
    merchant = context.merchant()
    coupon = context.coupon(merchant["id"], stock=0)
    quest = context.quest(coupon["id"])
    node = context.node(quest["id"], "qr")
    _, headers = context.actor()
    context.client.post(f"/api/v1/quests/{quest['id']}/join", headers=headers)
    endpoint = f"/api/v1/quests/{quest['id']}/checkin"
    response = context.client.post(
        endpoint,
        headers=headers,
        json={
            "node_id": node["id"],
            "qr_token": node["qr_token"],
        },
    )
    assert response.json()["status"] == "completed"
    assert response.json()["reward_pending"] is True
    with context.app.state.database.write() as session:
        # Advance this synthetic route's expiry while preserving already earned progress.
        row = session.get(Entity, quest["id"])
        row.data = {**row.data, "end_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()}
    context.client.patch(
        f"/api/v1/admin/coupons/{coupon['id']}", headers=context.admin, json={"stock": 1}
    )
    response = context.client.post(endpoint, headers=headers, json={"node_id": node["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["reward_pending"] is False
    assert response.json()["reward_claim_id"]
    assert context.client.get("/api/v1/me/stamps", headers=headers).json()["total"] == 1


def test_public_timed_lists_exclude_expired_and_future_records(context):
    merchant = context.merchant()
    active = context.coupon(merchant["id"])
    context.create(
        "coupons",
        {
            "merchant_id": merchant["id"],
            "title": "Expired",
            "rule": "Fixture",
            "stock": 1,
            "status": "published",
            "start_at": "2020-01-01T00:00:00Z",
            "end_at": "2020-02-01T00:00:00Z",
        },
    )
    context.create(
        "coupons",
        {
            "merchant_id": merchant["id"],
            "title": "Future",
            "rule": "Fixture",
            "stock": 1,
            "status": "published",
            "start_at": "2099-01-01T00:00:00Z",
            "end_at": "2099-02-01T00:00:00Z",
        },
    )
    assert [row["id"] for row in context.client.get("/api/v1/coupons").json()["items"]] == [
        active["id"]
    ]


def test_recommendation_uses_ops_factors_and_user_interests(context):
    character = context.character()
    first = context.merchant([character["id"]])
    second = context.merchant([character["id"]])
    context.client.patch(
        f"/api/v1/admin/merchants/{first['id']}",
        headers=context.admin,
        json={"merchant_quality": 1, "operation_weight": 1},
    )
    context.client.patch(
        f"/api/v1/admin/merchants/{second['id']}",
        headers=context.admin,
        json={"merchant_quality": 0, "operation_weight": 0},
    )
    endpoint = f"/api/v1/characters/{character['id']}/nearby"
    guest = context.client.get(endpoint).json()["items"]
    assert guest[0]["id"] == first["id"]
    _, headers = context.actor()
    context.client.put(f"/api/v1/me/favorites/{character['id']}", headers=headers)
    personalized = context.client.get(endpoint, headers=headers).json()["items"]
    assert personalized[0]["recommendation_score"] > guest[0]["recommendation_score"]
    _, owner = context.actor("merchant", first["id"])
    assert (
        context.client.patch(
            "/api/v1/merchant/profile", headers=owner, json={"operation_weight": 1}
        ).status_code
        == 403
    )


def test_audited_exports_are_bounded_and_formula_safe(context):
    context.create(
        "characters",
        {
            "cn_name": "=1+1",
            "culture_summary": "CSV fixture",
            "source_ref": "test:csv",
            "image_url": "/api/v1/media/fixture.png",
            "status": "published",
        },
    )
    context.character()
    _, tourist = context.actor()
    assert (
        context.client.post(
            "/api/v1/admin/exports/characters", json={}, headers=tourist
        ).status_code
        == 403
    )
    assert (
        context.client.post(
            "/api/v1/admin/exports/users", json={}, headers=context.admin
        ).status_code
        == 404
    )
    assert (
        context.client.post(
            "/api/v1/admin/exports/characters", json={"limit": 10001}, headers=context.admin
        ).status_code
        == 422
    )
    exported = context.client.post(
        "/api/v1/admin/exports/characters", json={"q": "=1+1"}, headers=context.admin
    )
    assert exported.status_code == 200, exported.text
    assert exported.json()["row_count"] == 1
    rows = list(csv.DictReader(io.StringIO(exported.json()["content"].lstrip("\ufeff"))))
    assert rows[0]["cn_name"] == "'=1+1"
    assert "password_hash" not in exported.text and "access_token" not in exported.text
    limited = context.client.post(
        "/api/v1/admin/exports/characters", json={"limit": 1}, headers=context.admin
    ).json()
    assert limited["row_count"] == 1 and limited["truncated"] is True
    audit_rows = context.client.get("/api/v1/admin/audit", headers=context.admin).json()["items"]
    assert sum(row["action"] == "export" for row in audit_rows) == 2


def test_openapi_exposes_create_and_patch_fields(context):
    contract = context.app.openapi()
    schemas = contract["components"]["schemas"]
    create = contract["paths"]["/api/v1/admin/characters"]["post"]
    reference = create["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert "variants" in schemas[reference.split("/")[-1]]["properties"]
    patch = contract["paths"]["/api/v1/admin/coupons/{entity_id}"]["patch"]
    reference = patch["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert "stock" in schemas[reference.split("/")[-1]]["properties"]
    assert not schemas[reference.split("/")[-1]].get("required")
