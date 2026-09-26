"""Seed linked, realistic fictional operating data into the Dongba application.

The script is additive and idempotent. It calls the application's content and
coupon workflows so dashboard totals, stock, claims, redemptions, audit rows and
entity revisions stay consistent. It is a dry run unless ``--apply`` and an
exact database-name confirmation are both supplied.
"""

import argparse
import json
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.business.content import save_entity, save_user  # noqa: E402
from backend.app.business.database import Database  # noqa: E402
from backend.app.business.models import (  # noqa: E402
    Claim,
    CouponStock,
    Entity,
    Event,
    RecognitionRecord,
    User,
)
from backend.app.business.workflows import (  # noqa: E402
    claim_coupon,
    statistics,
    verify_coupon,
)
from backend.app.config import Settings  # noqa: E402

CATALOG_PATH = ROOT / "data" / "operational_demo.json"
EVENT_PREFIX = "opsdemo:v1"


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def load_catalog(instant: datetime) -> dict:
    source = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    merchants = source["merchants"]
    start_at = iso(instant - timedelta(days=30))
    end_at = iso(instant + timedelta(days=180))
    products = [
        {
            "id": row_id,
            "merchant_id": merchants[index]["id"],
            "name": name,
            "description": description,
            "price": price,
            "character_ids": character_ids,
            "status": "published",
        }
        for row_id, index, name, description, price, character_ids in source["products"]
    ]
    coupons = [
        {
            "id": row_id,
            "merchant_id": merchants[index]["id"],
            "title": title,
            "rule": rule,
            "stock": stock,
            "per_user_limit": 1,
            "start_at": start_at,
            "end_at": end_at,
            "status": "published",
        }
        for row_id, index, title, rule, stock in source["coupons"]
    ]
    activities = [
        {
            "id": row_id,
            "merchant_id": merchants[index]["id"],
            "name": name,
            "description": description,
            "capacity": capacity,
            "start_at": start_at,
            "end_at": end_at,
            "status": "published",
        }
        for row_id, index, name, description, capacity in source["activities"]
    ]
    pois = [
        {
            "id": f"OPS_POI_{index + 1:02d}",
            "name": merchant["name"],
            "description": f"{source['notice']} {merchant['description']}",
            "latitude": merchant["latitude"],
            "longitude": merchant["longitude"],
            "poi_type": "merchant",
            "merchant_id": merchant["id"],
            "character_ids": merchant["character_ids"],
            "status": "published",
        }
        for index, merchant in enumerate(merchants)
    ]
    return {
        **source,
        "products": products,
        "coupons": coupons,
        "activities": activities,
        "pois": pois,
    }


def database_name(url: str) -> str:
    return (make_url(url).database or "").strip("/")


def active_admin(session) -> User:
    actor = session.scalar(
        select(User).where(User.role == "admin", User.status == "active").order_by(User.created_at)
    )
    if actor is None:
        raise RuntimeError("No active administrator exists; create one before seeding data")
    return actor


def ensure_entity(session, resource, payload, actor, created):
    existing = session.get(Entity, payload["id"])
    if existing is not None:
        if existing.kind != resource:
            raise RuntimeError(
                f"ID collision: {payload['id']} is {existing.kind}, expected {resource}"
            )
        return existing
    save_entity(session, resource, payload, actor)
    created[resource] = created.get(resource, 0) + 1
    return session.get(Entity, payload["id"])


def ensure_user(session, payload, actor, created, credentials):
    existing = session.scalar(select(User).where(User.username == payload["username"]))
    if existing is not None:
        if existing.role != payload["role"] or existing.merchant_id != payload.get("merchant_id"):
            raise RuntimeError(f"Username collision for {payload['username']}")
        return existing
    password = secrets.token_urlsafe(24)
    save_user(session, {**payload, "password": password}, actor)
    row = session.scalar(select(User).where(User.username == payload["username"]))
    created["users"] = created.get("users", 0) + 1
    if payload["role"] == "merchant":
        credentials.append(
            {
                "username": payload["username"],
                "password": password,
                "display_name": payload["display_name"],
                "merchant_id": payload["merchant_id"],
            }
        )
    return row


def ensure_event(session, **values):
    exists = session.scalar(
        select(Event.id).where(
            Event.user_id == values["user_id"], Event.event_id == values["event_id"]
        )
    )
    if exists:
        return False
    session.add(Event(**values))
    return True


def seed_entities(session, data, actor, created):
    for merchant in data["merchants"]:
        payload = {
            key: value for key, value in merchant.items() if key not in {"username", "display_name"}
        }
        payload["description"] = f"{data['notice']} {payload['description']}"
        payload["status"] = "published"
        ensure_entity(session, "merchants", payload, actor, created)
    for resource in ("pois", "products", "activities", "coupons"):
        for payload in data[resource]:
            ensure_entity(session, resource, payload, actor, created)


def seed_users(session, data, actor, instant, created, credentials):
    merchant_users = {}
    for merchant in data["merchants"]:
        merchant_users[merchant["id"]] = ensure_user(
            session,
            {
                "username": merchant["username"],
                "display_name": merchant["display_name"],
                "role": "merchant",
                "merchant_id": merchant["id"],
                "status": "active",
            },
            actor,
            created,
            credentials,
        )
    visitors = []
    for number in range(1, 25):
        visitor = ensure_user(
            session,
            {
                "username": f"visitor.lijiang.{number:03d}",
                "display_name": f"古城访客{number:02d}",
                "role": "tourist",
                "status": "active",
            },
            actor,
            created,
            credentials,
        )
        if visitor.created_at[:10] == instant.date().isoformat():
            visitor.created_at = iso(instant - timedelta(days=(number * 3) % 45, hours=number % 8))
        visitors.append(visitor)
    return merchant_users, visitors


def seed_claims(session, data, merchant_users, visitors, instant, created):
    coupon_ids = [row["id"] for row in data["coupons"]]
    plan = [(index, index % 8, index % 3 != 2) for index in range(24)]
    plan += [(index, (index + 3) % 8, index < 8) for index in range(12)]
    claim_ids = []
    for sequence, (visitor_index, coupon_index, should_redeem) in enumerate(plan, 1):
        visitor = visitors[visitor_index]
        coupon_id = coupon_ids[coupon_index]
        coupon = session.get(Entity, coupon_id)
        claim = session.scalar(
            select(Claim).where(Claim.user_id == visitor.id, Claim.coupon_id == coupon_id)
        )
        is_new = claim is None
        if is_new:
            claim = claim_coupon(session, coupon_id, visitor.id)
            created["claims"] = created.get("claims", 0) + 1
        claimed_at = instant - timedelta(days=(sequence * 2) % 10, hours=(sequence % 7) + 1)
        if is_new:
            claim.claimed_at = iso(claimed_at)
            claim_event = session.scalar(
                select(Event).where(Event.event_id == f"server:coupon_claim:{claim.id}")
            )
            if claim_event:
                claim_event.created_at = claim.claimed_at
        if should_redeem and claim.status == "available":
            verify_coupon(session, claim.code, merchant_users[coupon.merchant_id])
            claim.verified_at = iso(claimed_at + timedelta(hours=2, minutes=sequence % 40))
            verify_event = session.scalar(
                select(Event).where(Event.event_id == f"server:verify:{claim.id}")
            )
            if verify_event:
                verify_event.created_at = claim.verified_at
            created["redemptions"] = created.get("redemptions", 0) + 1
        claim_ids.append(claim.id)
    return coupon_ids, claim_ids


def seed_recognitions_and_events(session, data, visitors, instant, created):
    characters = data["recognition_characters"]
    for index in range(16):
        request_id = f"OPS_DEMO_REC_{index + 1:03d}"
        character_id = characters[index % len(characters)]
        if session.get(RecognitionRecord, request_id) is None:
            session.add(
                RecognitionRecord(
                    request_id=request_id,
                    user_id=visitors[index].id,
                    status="NEED_USER_CONFIRM",
                    provider="operational-demo",
                    model="linked-scenario-v1",
                    candidates=[
                        {
                            "character_id": character_id,
                            "score": round(0.91 - index / 200, 3),
                        }
                    ],
                    latency_ms=720 + index * 23,
                    scene="album" if index % 4 == 0 else "camera",
                    confirmed_character_id=character_id,
                    created_at=iso(instant - timedelta(days=index % 8, hours=(index * 2) % 10)),
                )
            )
            created["recognitions"] = created.get("recognitions", 0) + 1
    for index, visitor in enumerate(visitors):
        merchant = data["merchants"][index % len(data["merchants"])]
        product = data["products"][index % len(data["products"])]
        timestamp = instant - timedelta(days=index % 10, hours=index % 6)
        recognition_id = f"OPS_DEMO_REC_{index % 16 + 1:03d}" if index < 16 else None
        specs = [
            ("home_view", None, None, None),
            ("merchant_impression", "merchants", merchant["id"], merchant["id"]),
            ("merchant_detail", "merchants", merchant["id"], merchant["id"]),
            ("product_detail", "products", product["id"], merchant["id"]),
        ]
        if index % 2 == 0:
            specs.append(("navigate", "merchants", merchant["id"], merchant["id"]))
        if index % 3 == 0:
            specs.append(("share", "characters", characters[index % len(characters)], None))
        for position, (event, entity_type, entity_id, merchant_id) in enumerate(specs):
            if ensure_event(
                session,
                event_id=f"{EVENT_PREFIX}:{index + 1:03d}:{position:02d}:{event}",
                user_id=visitor.id,
                event=event,
                entity_type=entity_type,
                entity_id=entity_id,
                merchant_id=merchant_id,
                recognition_id=(
                    recognition_id if event in {"merchant_impression", "merchant_detail"} else None
                ),
                created_at=iso(timestamp + timedelta(minutes=position * 7)),
            ):
                created["events"] = created.get("events", 0) + 1


def verify(session, data, coupon_ids, claim_ids):
    usernames = [merchant["username"] for merchant in data["merchants"]]
    usernames += [f"visitor.lijiang.{number:03d}" for number in range(1, 25)]
    users = session.scalar(
        select(func.count()).select_from(User).where(User.username.in_(usernames))
    )
    claims = session.scalar(select(func.count()).select_from(Claim).where(Claim.id.in_(claim_ids)))
    redemptions = session.scalar(
        select(func.count())
        .select_from(Claim)
        .where(Claim.id.in_(claim_ids), Claim.status == "used")
    )
    if users != 28 or claims != 36 or redemptions < 24:
        raise RuntimeError(
            f"Operational verification failed: users={users}, claims={claims}, "
            f"redemptions={redemptions}"
        )
    for coupon_id in coupon_ids:
        inventory = session.get(CouponStock, coupon_id)
        actual = session.scalar(
            select(func.count()).select_from(Claim).where(Claim.coupon_id == coupon_id)
        )
        if inventory is None or inventory.claimed_count != actual:
            raise RuntimeError(f"Coupon stock mismatch for {coupon_id}")
    return {
        "demo_users": users,
        "merchant_users": 4,
        "tourist_users": 24,
        "merchants": 4,
        "products": 8,
        "pois": 4,
        "activities": 4,
        "coupons": 8,
        "claims": claims,
        "redemptions": redemptions,
        "recognitions": 16,
    }


def seed(session, instant):
    actor = active_admin(session)
    data = load_catalog(instant)
    created = {}
    credentials = []
    character_ids = sorted(
        {
            character_id
            for merchant in data["merchants"]
            for character_id in merchant["character_ids"]
        }
    )
    missing = [
        character_id
        for character_id in character_ids
        if not session.scalar(
            select(Entity.id).where(
                Entity.id == character_id,
                Entity.kind == "characters",
                Entity.status == "published",
            )
        )
    ]
    if missing:
        raise RuntimeError(f"Published DB1404 entries are missing: {', '.join(missing)}")
    seed_entities(session, data, actor, created)
    merchant_users, visitors = seed_users(session, data, actor, instant, created, credentials)
    coupon_ids, claim_ids = seed_claims(session, data, merchant_users, visitors, instant, created)
    seed_recognitions_and_events(session, data, visitors, instant, created)
    session.flush()
    return {
        "dataset": data["dataset"],
        "created": created,
        "verified": verify(session, data, coupon_ids, claim_ids),
    }, credentials


def write_private_credentials(path, rows):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    usernames = {row["username"] for row in existing}
    merged = existing + [row for row in rows if row["username"] not in usernames]
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", default="")
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "runtime" / "operational-demo-report.json",
    )
    parser.add_argument(
        "--credentials-report",
        type=Path,
        default=ROOT / "runtime" / "operational-demo-merchant-credentials.json",
    )
    args = parser.parse_args()
    settings = Settings()
    instant = datetime.now(UTC)
    target = database_name(settings.database_url)
    if not settings.database_url.startswith("mysql+pymysql://"):
        raise SystemExit("Operational data can only be seeded into MySQL")
    database = Database(settings.database_url)
    with database.session() as session:
        baseline = statistics(session)
    plan = {
        "mode": "apply" if args.apply else "dry-run",
        "database": target,
        "dataset": load_catalog(instant)["dataset"],
        "baseline": baseline,
        "planned": {
            "merchant_users": 4,
            "tourist_users": 24,
            "merchants": 4,
            "products": 8,
            "pois": 4,
            "activities": 4,
            "coupons": 8,
            "claims": 36,
            "planned_redemptions": 24,
            "recognitions": 16,
        },
    }
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if args.confirm_database != target:
        raise SystemExit(f"Refusing to write: pass --confirm-database {target!r}")
    with database.write() as session:
        result, credentials = seed(session, instant)
    with database.session() as session:
        after = statistics(session)
        role_counts = dict(
            session.execute(select(User.role, func.count()).group_by(User.role)).all()
        )
        merchant_stats = {
            merchant["id"]: statistics(session, merchant["id"])
            for merchant in load_catalog(instant)["merchants"]
        }
    report = {
        **plan,
        **result,
        "after": after,
        "role_counts": role_counts,
        "merchant_stats": merchant_stats,
        "dashboard_delta": {
            key: after.get(key, 0) - baseline.get(key, 0)
            for key in (
                "users",
                "active_users_today",
                "recognitions",
                "coupon_claims",
                "redemptions",
            )
        },
        "credentials_report": str(args.credentials_report),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_private_credentials(args.credentials_report, credentials)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
