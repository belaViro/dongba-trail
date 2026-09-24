import math
import secrets
from copy import deepcopy
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import delete, func, select

from backend.app.errors import ApiError

from .auth import password_hash, user_dict
from .models import (
    Audit,
    Claim,
    CouponStock,
    Enrollment,
    Entity,
    EntityRevision,
    Favorite,
    RecognitionRecord,
    SessionToken,
    Setting,
    User,
    identifier,
    now,
)
from .schemas import RESOURCE_SCHEMAS, UserInput, Weights


def audit(session, user: User, action: str, resource: str, entity_id: str, detail=None):
    session.add(
        Audit(
            user_id=user.id,
            action=action,
            entity_type=resource,
            entity_id=entity_id,
            detail=detail or {},
        )
    )


def entity(session, resource: str, entity_id: str, *, published=False, lock=False) -> Entity:
    query = select(Entity).where(Entity.id == entity_id, Entity.kind == resource)
    if published:
        query = query.where(Entity.status == "published")
    if lock:
        query = query.with_for_update()
    result = session.scalar(query)
    if result is None:
        raise ApiError(404, "NOT_FOUND", "The requested record does not exist")
    if published and result.merchant_id:
        merchant = session.get(Entity, result.merchant_id)
        if merchant is None or merchant.status != "published":
            raise ApiError(404, "NOT_FOUND", "The requested record is unavailable")
    return result


def serialize(row, session=None, *, privileged=False) -> dict:
    if isinstance(row, User):
        return user_dict(row)
    if not isinstance(row, Entity):
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}
    output = {
        **row.data,
        "id": row.id,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at,
    }
    if row.kind == "characters":
        for key, default in (("source_no", None), ("alias", []), ("keywords", []), ("commercial_tags", [])):
            output.setdefault(key, default)
        output["character_id"] = row.id
    if row.kind == "coupons" and session is not None:
        inventory = session.get(CouponStock, row.id)
        output["stock"] = inventory.stock if inventory else 0
        output["claimed_count"] = inventory.claimed_count if inventory else 0
    if not privileged:
        output.pop("qr_token", None)
    return output


def record_revision(session, row: Entity, action: str, actor_id: str | None):
    # Callers hold the entity lock, keeping version assignment in the same transaction.
    latest = session.scalar(
        select(func.max(EntityRevision.version)).where(EntityRevision.entity_id == row.id)
    ) or 0
    revision = EntityRevision(
        entity_id=row.id,
        resource=row.kind,
        version=latest + 1,
        action=action,
        actor_id=actor_id,
        snapshot=deepcopy(serialize(row, session, privileged=True)),
    )
    session.add(revision)
    session.flush()
    return revision


def ensure_revision_baseline(session, row: Entity):
    if not session.scalar(select(EntityRevision.id).where(EntityRevision.entity_id == row.id).limit(1)):
        record_revision(session, row, "baseline", None)


def within_period(row: Entity) -> bool:
    instant = datetime.now(UTC)
    return (
        datetime.fromisoformat(row.data["start_at"])
        <= instant
        < datetime.fromisoformat(row.data["end_at"])
    )


def require_active(row: Entity):
    if row.status != "published" or not within_period(row):
        raise ApiError(409, "NOT_ACTIVE", "The record is not currently available")


def validate_references(session, resource: str, data: dict):
    if resource == "merchants":
        if (data["latitude"] is None) != (data["longitude"] is None):
            raise ApiError(422, "LOCATION_INCOMPLETE", "Both merchant coordinates are required")
        if data["status"] == "published" and data["latitude"] is None:
            raise ApiError(
                422, "LOCATION_REQUIRED", "Published merchants require a verified location"
            )
    for character_id in data.get("character_ids", []):
        entity(session, "characters", character_id, published=data["status"] == "published")
    for field, kind in (
        ("merchant_id", "merchants"),
        ("poi_id", "pois"),
        ("character_id", "characters"),
        ("reward_coupon_id", "coupons"),
        ("quest_id", "quests"),
    ):
        if data.get(field):
            entity(session, kind, data[field])
    if resource == "characters" and data["status"] in {"reviewed", "published"}:
        if not data["culture_summary"] or not data["source_ref"]:
            raise ApiError(422, "REVIEW_INCOMPLETE", "Cultural summary and source are required")
        if data["status"] == "published" and not (
            data["image_url"] or any(item["image_url"] for item in data["variants"])
        ):
            raise ApiError(422, "GLYPH_REQUIRED", "Published characters require a glyph image")
    if resource == "quest-nodes":
        condition = data["condition"]
        if condition == "recognition" and not data.get("character_id"):
            raise ApiError(422, "NODE_INCOMPLETE", "Recognition nodes need a character")
        if condition == "coupon" and not data.get("merchant_id"):
            raise ApiError(422, "NODE_INCOMPLETE", "Coupon nodes need a merchant")
        if condition == "geofence" and not (data.get("poi_id") or data.get("merchant_id")):
            raise ApiError(422, "NODE_INCOMPLETE", "Geofence nodes need a mapped place")


def save_entity(
    session,
    resource: str,
    payload: dict,
    user: User,
    entity_id: str | None = None,
    *,
    merchant=False,
):
    schema = RESOURCE_SCHEMAS[resource]
    old = entity(session, resource, entity_id, lock=True) if entity_id else None
    if old and merchant and old.merchant_id != user.merchant_id and old.id != user.merchant_id:
        raise ApiError(404, "NOT_FOUND", "The requested record does not exist")
    if old and payload.get("id", entity_id) != entity_id:
        raise ApiError(422, "IMMUTABLE_ID", "Record identifiers cannot be changed")
    if old:
        ensure_revision_baseline(session, old)
    if merchant:
        if any(key in payload for key in ("merchant_quality", "operation_weight")):
            raise ApiError(403, "FORBIDDEN", "Recommendation factors are operations controlled")
        if resource not in {"merchants", "products", "coupons", "activities"}:
            raise ApiError(403, "FORBIDDEN", "Resource is not merchant editable")
        if payload.get("status", "draft") not in {"draft", "disabled"}:
            raise ApiError(403, "REVIEW_REQUIRED", "Operations must review publication")
        if any(key in payload for key in ("character_ids", "tags")):
            old_data = old.data if old else {}
            if any(
                payload.get(key, old_data.get(key, [])) != old_data.get(key, [])
                for key in ("character_ids", "tags")
            ):
                raise ApiError(403, "TAG_REVIEW_REQUIRED", "Cultural relationships require review")
        if resource != "merchants":
            if payload.get("merchant_id", user.merchant_id) != user.merchant_id:
                raise ApiError(403, "FORBIDDEN", "Merchant ownership cannot be changed")
            payload = {**payload, "merchant_id": user.merchant_id}
        payload = {
            **payload,
            "status": "disabled" if payload.get("status") == "disabled" else "draft",
        }
    previous = {**old.data, "status": old.status} if old else {}
    try:
        data = schema.model_validate({**previous, **payload}).model_dump(mode="json")
    except ValidationError as exc:
        raise ApiError(422, "INVALID_ENTITY", "Entity fields are invalid") from exc
    validate_references(session, resource, data)
    if resource == "quest-nodes":
        entity(session, "quests", data["quest_id"], lock=True)
    if old and resource in {"quests", "quest-nodes"}:
        quest_id = old.id if resource == "quests" else old.data["quest_id"]
        enrolled = session.scalar(
            select(Enrollment.id).where(Enrollment.quest_id == quest_id).limit(1)
        )
        protected = (
            ("start_at", "end_at", "reward_coupon_id")
            if resource == "quests"
            else (
                "quest_id",
                "condition",
                "character_id",
                "merchant_id",
                "poi_id",
                "sequence",
                "radius_m",
            )
        )
        if enrolled and any(data.get(key) != old.data.get(key) for key in protected):
            raise ApiError(
                409, "QUEST_IN_USE", "Active quest rules cannot be changed after joining"
            )
        if enrolled and data["status"] != old.status and resource == "quest-nodes":
            raise ApiError(409, "QUEST_IN_USE", "Node publication cannot change after joining")
    if not old and resource == "quest-nodes":
        if session.scalar(
            select(Enrollment.id).where(Enrollment.quest_id == data["quest_id"]).limit(1)
        ):
            raise ApiError(
                409, "QUEST_IN_USE", "Nodes cannot be added after a quest has participants"
            )
    if old and resource == "coupons":
        inventory = session.get(CouponStock, old.id)
        if data["stock"] < inventory.claimed_count:
            raise ApiError(409, "STOCK_BELOW_CLAIMED", "Stock cannot be lower than claims")
        if inventory.claimed_count and any(
            data[key] != old.data.get(key)
            for key in ("merchant_id", "start_at", "end_at", "rule", "per_user_limit")
        ):
            raise ApiError(409, "COUPON_IN_USE", "Issued coupon terms cannot be changed")
        inventory.stock = data["stock"]
    requested_id = data.pop("id", None)
    status = data.pop("status")
    if old:
        row = old
    else:
        row_id = requested_id or (
            "DB_" + secrets.token_hex(12).upper() if resource == "characters" else identifier()
        )
        if session.get(Entity, row_id) is not None:
            raise ApiError(409, "ID_EXISTS", "Record identifier already exists")
        row = Entity(id=row_id, kind=resource)
        session.add(row)
    if resource == "quest-nodes" and data["condition"] == "qr" and not data.get("qr_token"):
        data["qr_token"] = secrets.token_urlsafe(24)
    row.data, row.status = data, status
    row.merchant_id = data.get("merchant_id")
    row.updated_at = now()
    if status in {"reviewed", "published"}:
        row.reviewed_by, row.reviewed_at = user.id, now()
    else:
        row.reviewed_by, row.reviewed_at = None, None
    session.flush()
    if resource == "coupons" and not old:
        session.add(CouponStock(coupon_id=row.id, stock=data["stock"], claimed_count=0))
        session.flush()
    audit(
        session,
        user,
        "update" if old else "create",
        resource,
        row.id,
        {"fields": sorted(payload), "status": status},
    )
    if status in {"reviewed", "published"}:
        audit(session, user, "review_publish", resource, row.id, {"status": status})
    action = "create" if old is None else "update"
    if status in {"reviewed", "published"}:
        action = "review" if status == "reviewed" else "publish"
    elif status == "disabled":
        action = "disable"
    record_revision(session, row, action, user.id)
    return serialize(row, session, privileged=True)


def save_user(session, payload: dict, actor: User, user_id: str | None = None):
    if actor.role != "admin":
        raise ApiError(403, "FORBIDDEN", "Only administrators can manage users")
    old = session.get(User, user_id) if user_id else None
    if user_id and not old:
        raise ApiError(404, "NOT_FOUND", "User not found")
    previous = (
        {key: value for key, value in user_dict(old).items() if key != "created_at"} if old else {}
    )
    try:
        data = UserInput.model_validate({**previous, **payload})
    except ValidationError as exc:
        raise ApiError(422, "INVALID_USER", "User fields are invalid") from exc
    if old and data.id != old.id:
        raise ApiError(422, "IMMUTABLE_ID", "User identifiers cannot be changed")
    if data.username.startswith("wx_") and (not old or old.username != data.username):
        raise ApiError(422, "RESERVED_USERNAME", "WeChat account identifiers are reserved")
    if session.scalar(
        select(User).where(User.username == data.username, User.id != (user_id or ""))
    ):
        raise ApiError(409, "USERNAME_EXISTS", "Username is already in use")
    if data.role == "merchant":
        if not data.merchant_id:
            raise ApiError(422, "MERCHANT_REQUIRED", "A merchant account needs a store")
        entity(session, "merchants", data.merchant_id)
    elif data.merchant_id:
        raise ApiError(422, "INVALID_MERCHANT", "Only merchant accounts can own a store")
    if old and old.id == actor.id and (data.status != "active" or data.role != "admin"):
        raise ApiError(409, "SELF_LOCKOUT", "Administrators cannot disable their own access")
    if not old and not data.password:
        raise ApiError(422, "PASSWORD_REQUIRED", "A password is required")
    row = old or User(id=identifier())
    for key in ("username", "display_name", "role", "merchant_id", "status"):
        setattr(row, key, getattr(data, key))
    if data.password:
        row.password_hash = password_hash(data.password)
    session.add(row)
    session.flush()
    if old:
        session.execute(delete(SessionToken).where(SessionToken.user_id == row.id))
    audit(
        session,
        actor,
        "update" if old else "create",
        "users",
        row.id,
        {"fields": [key for key in payload if key != "password"]},
    )
    return user_dict(row)


def disable_entity(session, resource: str, entity_id: str, user: User, *, merchant=False):
    if resource == "users":
        return save_user(session, {"status": "disabled"}, user, entity_id)
    row = entity(session, resource, entity_id, lock=True)
    if merchant and row.merchant_id != user.merchant_id:
        raise ApiError(404, "NOT_FOUND", "Record not found")
    if resource == "quest-nodes":
        entity(session, "quests", row.data["quest_id"], lock=True)
    if resource == "quest-nodes" and session.scalar(
        select(Enrollment.id).where(Enrollment.quest_id == row.data["quest_id"]).limit(1)
    ):
        raise ApiError(409, "QUEST_IN_USE", "Enrolled quest nodes cannot be disabled")
    ensure_revision_baseline(session, row)
    row.status = "disabled"
    row.updated_at = now()
    session.flush()
    record_revision(session, row, "disable", user.id)
    audit(session, user, "disable", resource, row.id)
    return {"id": row.id, "status": "disabled"}


def list_entities(
    session,
    resource,
    *,
    q="",
    status=None,
    offset=0,
    limit=100,
    merchant_id=None,
    character_id=None,
    public=False,
):
    query = select(Entity).where(Entity.kind == resource)
    if status:
        query = query.where(Entity.status == status)
    if merchant_id:
        query = query.where(Entity.merchant_id == merchant_id)
    rows = session.scalars(query.order_by(Entity.created_at.desc(), Entity.id)).all()
    result = []
    for row in rows:
        if public and resource in {"coupons", "activities", "quests"} and not within_period(row):
            continue
        if public and row.merchant_id:
            merchant = session.get(Entity, row.merchant_id)
            if not merchant or merchant.status != "published":
                continue
        if character_id and character_id not in row.data.get("character_ids", []):
            continue
        if (
            q
            and q.casefold()
            not in " ".join(
                str(row.data.get(key, ""))
                for key in ("name", "cn_name", "title", "description", "source_no", "alias", "keywords", "commercial_tags")
            ).casefold()
        ):
            continue
        result.append(row)
    return {
        "items": [
            serialize(row, session, privileged=not public)
            for row in result[offset : offset + limit]
        ],
        "total": len(result),
    }


def distance_m(latitude, longitude, target_latitude, target_longitude):
    lat1, lat2 = math.radians(latitude), math.radians(target_latitude)
    dlat = lat2 - lat1
    dlon = math.radians(target_longitude - longitude)
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(value)))


def weights(session):
    record = session.get(Setting, "recommendation_weights")
    return record.value if record else Weights().model_dump()


def nearby(session, character_id: str, latitude, longitude, user_id=None):
    entity(session, "characters", character_id, published=True)
    merchants = session.scalars(
        select(Entity).where(Entity.kind == "merchants", Entity.status == "published")
    ).all()
    config = weights(session)
    interests = set()
    if user_id:
        interests.update(
            session.scalars(select(Favorite.character_id).where(Favorite.user_id == user_id)).all()
        )
        interests.update(
            session.scalars(
                select(RecognitionRecord.confirmed_character_id).where(
                    RecognitionRecord.user_id == user_id,
                    RecognitionRecord.confirmed_character_id.is_not(None),
                    RecognitionRecord.history_deleted.is_(False),
                )
            ).all()
        )
    results = []
    for merchant in merchants:
        if character_id not in merchant.data.get("character_ids", []):
            continue
        distance = None
        if (
            latitude is not None
            and longitude is not None
            and merchant.data.get("latitude") is not None
            and merchant.data.get("longitude") is not None
        ):
            distance = distance_m(
                latitude, longitude, merchant.data["latitude"], merchant.data["longitude"]
            )
        coupons = session.scalars(
            select(Entity).where(
                Entity.kind == "coupons",
                Entity.merchant_id == merchant.id,
                Entity.status == "published",
            )
        ).all()
        has_coupon = any(
            within_period(coupon)
            and session.get(CouponStock, coupon.id).claimed_count
            < session.get(CouponStock, coupon.id).stock
            for coupon in coupons
        )
        relationships = set(merchant.data.get("character_ids", []))
        score = config["cultural_relevance"]
        score += config["merchant_quality"] * merchant.data.get("merchant_quality", 0.5)
        score += config["operation_weight"] * merchant.data.get("operation_weight", 0.5)
        score += config["user_behavior_match"] * (
            len(relationships & interests) / max(1, len(relationships))
        )
        score += config["distance_score"] * (
            1 / (1 + distance / 1000) if distance is not None else 0
        )
        score += config["coupon_activity"] * int(has_coupon)
        results.append(
            {
                **serialize(merchant),
                "distance_m": round(distance) if distance is not None else None,
                "recommendation_score": round(score, 4),
                "has_coupon": has_coupon,
            }
        )
    results.sort(key=lambda item: (-item["recommendation_score"], item["id"]))
    return {"items": results[:100], "total": len(results)}


def count(session, model, *conditions):
    return session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def claim_dict(session, row: Claim):
    coupon = session.get(Entity, row.coupon_id)
    data = serialize(row)
    data["coupon"] = serialize(coupon, session) if coupon else None
    if coupon:
        data.update({key: coupon.data[key] for key in ("title", "rule", "start_at", "end_at")})
        if row.status == "available" and datetime.now(UTC) >= datetime.fromisoformat(
            coupon.data["end_at"]
        ):
            data["status"] = "expired"
    return data
