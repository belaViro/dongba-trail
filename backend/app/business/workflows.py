import hmac
import secrets
from datetime import UTC, datetime

from sqlalchemy import delete, select, update

from backend.app.errors import ApiError

from .content import audit, claim_dict, count, distance_m, entity, require_active, serialize
from .models import (
    Claim,
    CouponStock,
    Enrollment,
    Entity,
    Event,
    Feedback,
    RecognitionRecord,
    Stamp,
    User,
    now,
)


def server_event(
    session,
    user_id,
    event_name,
    entity_type,
    entity_id,
    merchant_id=None,
    recognition_id=None,
    unique_key=None,
):
    key = unique_key or f"server:{event_name}:{entity_id}"
    if session.scalar(select(Event.id).where(Event.event_id == key)) is None:
        session.add(
            Event(
                event_id=key,
                user_id=user_id,
                event=event_name,
                entity_type=entity_type,
                entity_id=entity_id,
                merchant_id=merchant_id,
                recognition_id=recognition_id,
            )
        )


def lock_user(session, user_id):
    user = session.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user or user.status != "active":
        raise ApiError(404, "USER_NOT_FOUND", "Active user not found")
    return user


def claim_coupon(session, coupon_id, user_id, *, reward_key=None):
    lock_user(session, user_id)
    coupon = entity(session, "coupons", coupon_id, published=True, lock=True)
    require_active(coupon)
    if reward_key:
        prior = session.scalar(select(Claim).where(Claim.reward_key == reward_key))
        if prior:
            return prior
    elif (
        count(session, Claim, Claim.user_id == user_id, Claim.coupon_id == coupon_id)
        >= coupon.data["per_user_limit"]
    ):
        raise ApiError(409, "CLAIM_LIMIT", "The per-user coupon limit has been reached")
    changed = session.execute(
        update(CouponStock)
        .where(
            CouponStock.coupon_id == coupon_id,
            CouponStock.claimed_count < CouponStock.stock,
        )
        .values(claimed_count=CouponStock.claimed_count + 1)
    )
    if changed.rowcount != 1:
        raise ApiError(409, "SOLD_OUT", "All coupons have been claimed")
    claim = Claim(
        coupon_id=coupon_id,
        user_id=user_id,
        merchant_id=coupon.merchant_id,
        code=secrets.token_urlsafe(18),
        reward_key=reward_key,
    )
    session.add(claim)
    session.flush()
    server_event(session, user_id, "coupon_claim", "coupons", claim.id, coupon.merchant_id)
    return claim


def verify_coupon(session, code: str, user: User):
    claim = session.scalar(select(Claim).where(Claim.code == code).with_for_update())
    if claim is None or claim.merchant_id != user.merchant_id:
        raise ApiError(404, "COUPON_NOT_FOUND", "Coupon code was not found for this merchant")
    if claim.status == "used":
        return {**claim_dict(session, claim), "already_verified": True}
    coupon = entity(session, "coupons", claim.coupon_id, published=True)
    require_active(coupon)
    if claim.status != "available":
        raise ApiError(409, "COUPON_UNAVAILABLE", "Coupon cannot be redeemed")
    claim.status, claim.verified_at, claim.verified_by = "used", now(), user.id
    audit(session, user, "verify", "coupon_claims", claim.id)
    server_event(session, claim.user_id, "verify", "coupons", claim.id, claim.merchant_id)
    return {**claim_dict(session, claim), "already_verified": False}


def quest_nodes(session, quest_id, *, privileged=False):
    rows = session.scalars(
        select(Entity).where(Entity.kind == "quest-nodes", Entity.status == "published")
    ).all()
    nodes = [row for row in rows if row.data["quest_id"] == quest_id]
    return sorted(
        (serialize(node, privileged=privileged) for node in nodes),
        key=lambda node: (node["sequence"], node["id"]),
    )


def enrollment_dict(session, row: Enrollment):
    quest = session.get(Entity, row.quest_id)
    completed = session.scalars(
        select(Stamp.node_id).where(Stamp.user_id == row.user_id, Stamp.quest_id == row.quest_id)
    ).all()
    output = {
        **serialize(quest),
        "quest_id": row.quest_id,
        "enrollment_id": row.id,
        "status": row.status,
        "joined_at": row.joined_at,
        "completed_at": row.completed_at,
        "completed_node_ids": list(completed),
        "reward_claim_id": row.reward_claim_id,
    }
    output["nodes"] = quest_nodes(session, row.quest_id)
    output["reward_pending"] = bool(
        row.completed_at and quest.data.get("reward_coupon_id") and not row.reward_claim_id
    )
    return output


def join_quest(session, quest_id: str, user: User):
    lock_user(session, user.id)
    quest = entity(session, "quests", quest_id, published=True, lock=True)
    require_active(quest)
    if not quest_nodes(session, quest_id):
        raise ApiError(409, "QUEST_NO_NODES", "This quest has no published nodes")
    enrollment = session.scalar(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.quest_id == quest_id)
    )
    if enrollment is None:
        enrollment = Enrollment(user_id=user.id, quest_id=quest_id)
        session.add(enrollment)
        session.flush()
        server_event(
            session,
            user.id,
            "quest_join",
            "quests",
            quest_id,
            unique_key=f"server:quest_join:{enrollment.id}",
        )
    return enrollment_dict(session, enrollment)


def maybe_reward(session, quest: Entity, enrollment: Enrollment):
    if enrollment.status != "completed" or enrollment.reward_claim_id:
        return
    coupon_id = quest.data.get("reward_coupon_id")
    if coupon_id:
        try:
            claim = claim_coupon(
                session, coupon_id, enrollment.user_id, reward_key=f"quest:{enrollment.id}"
            )
            enrollment.reward_claim_id = claim.id
        except ApiError as exc:
            if exc.code not in {"SOLD_OUT", "NOT_ACTIVE", "NOT_FOUND"}:
                raise


def complete_node(session, quest_id: str, payload, user: User, *, manual_actor=None):
    lock_user(session, user.id)
    quest = entity(session, "quests", quest_id)
    enrollment = session.scalar(
        select(Enrollment)
        .where(Enrollment.user_id == user.id, Enrollment.quest_id == quest_id)
        .with_for_update()
    )
    if enrollment is None:
        raise ApiError(409, "JOIN_REQUIRED", "Join the quest before checking in")
    node = entity(session, "quest-nodes", payload.node_id)
    if node.data["quest_id"] != quest_id:
        raise ApiError(404, "NODE_NOT_FOUND", "Node is not part of this quest")
    existing = session.scalar(
        select(Stamp).where(Stamp.user_id == user.id, Stamp.node_id == node.id)
    )
    if existing:
        maybe_reward(session, quest, enrollment)
        return {
            **enrollment_dict(session, enrollment),
            "stamp": serialize(existing),
            "already_completed": True,
        }
    require_active(quest)
    entity(session, "quest-nodes", payload.node_id, published=True)
    condition = node.data["condition"]
    if manual_actor:
        if condition != "manual":
            raise ApiError(
                409, "MANUAL_NOT_ALLOWED", "This node requires its configured verification"
            )
    elif condition == "manual":
        raise ApiError(403, "MANUAL_REQUIRED", "Operations confirmation is required")
    elif condition == "recognition":
        record = session.get(RecognitionRecord, payload.recognition_id or "")
        if (
            record is None
            or record.user_id != user.id
            or record.history_deleted
            or record.created_at < enrollment.joined_at
            or record.confirmed_character_id != node.data["character_id"]
        ):
            raise ApiError(
                409, "RECOGNITION_REQUIRED", "A matching confirmed recognition is required"
            )
    elif condition == "qr":
        expected = node.data.get("qr_token")
        if (
            not expected
            or not payload.qr_token
            or not hmac.compare_digest(expected, payload.qr_token)
        ):
            raise ApiError(409, "QR_INVALID", "The QR code does not match this node")
    elif condition == "geofence":
        if payload.latitude is None or payload.longitude is None:
            raise ApiError(422, "LOCATION_REQUIRED", "A current location is required")
        place = (
            entity(session, "pois", node.data["poi_id"], published=True)
            if node.data.get("poi_id")
            else entity(session, "merchants", node.data["merchant_id"], published=True)
        )
        if place.data.get("latitude") is None or place.data.get("longitude") is None:
            raise ApiError(
                409, "PLACE_NOT_CONFIGURED", "The check-in place has no verified coordinates"
            )
        distance = distance_m(
            payload.latitude, payload.longitude, place.data["latitude"], place.data["longitude"]
        )
        if distance > node.data["radius_m"]:
            raise ApiError(409, "OUTSIDE_GEOFENCE", "Current location is outside the check-in area")
    elif condition == "coupon":
        claim = session.get(Claim, payload.claim_id or "")
        if (
            claim is None
            or claim.user_id != user.id
            or claim.merchant_id != node.data["merchant_id"]
            or claim.status != "used"
            or claim.verified_at < enrollment.joined_at
        ):
            raise ApiError(409, "REDEMPTION_REQUIRED", "A qualifying redeemed coupon is required")
    stamp = Stamp(
        user_id=user.id,
        quest_id=quest_id,
        node_id=node.id,
        character_id=node.data.get("character_id"),
        source=condition,
    )
    session.add(stamp)
    session.flush()
    nodes = quest_nodes(session, quest_id)
    completed_ids = set(
        session.scalars(
            select(Stamp.node_id).where(Stamp.user_id == user.id, Stamp.quest_id == quest_id)
        ).all()
    )
    if nodes and all(item["id"] in completed_ids for item in nodes):
        enrollment.status, enrollment.completed_at = "completed", now()
        server_event(
            session,
            user.id,
            "quest_complete",
            "quests",
            quest_id,
            unique_key=f"server:quest_complete:{enrollment.id}",
        )
        maybe_reward(session, quest, enrollment)
    if manual_actor:
        audit(
            session, manual_actor, "manual_complete", "quest-nodes", node.id, {"user_id": user.id}
        )
    return {
        **enrollment_dict(session, enrollment),
        "stamp": serialize(stamp),
        "already_completed": False,
    }


def delete_user_history(session, user_id: str):
    ids = list(
        session.scalars(
            select(RecognitionRecord.request_id).where(RecognitionRecord.user_id == user_id)
        ).all()
    )
    if ids:
        session.execute(delete(Feedback).where(Feedback.recognition_id.in_(ids)))
        session.execute(
            update(Event).where(Event.recognition_id.in_(ids)).values(recognition_id=None)
        )
        session.execute(delete(RecognitionRecord).where(RecognitionRecord.request_id.in_(ids)))
    return len(ids)


def statistics(session, merchant_id=None):
    from .models import RecognitionRecord

    event_query = select(Event)
    if merchant_id:
        event_query = event_query.where(Event.merchant_id == merchant_id)
    events = session.scalars(event_query).all()
    today = datetime.now(UTC).date().isoformat()
    active_users = {event.user_id for event in events if event.created_at[:10] == today}
    event_counts = {}
    for event in events:
        event_counts[event.event] = event_counts.get(event.event, 0) + 1
    claims = session.scalars(
        select(Claim).where(Claim.merchant_id == merchant_id) if merchant_id else select(Claim)
    ).all()
    recognitions = [] if merchant_id else session.scalars(select(RecognitionRecord)).all()
    active_users.update(row.user_id for row in recognitions if row.created_at[:10] == today)
    daily = {}
    for recognition in recognitions:
        day = recognition.created_at[:10]
        daily.setdefault(
            day, {"date": day, "recognitions": 0, "coupon_claims": 0, "redemptions": 0}
        )["recognitions"] += 1
    for claim in claims:
        day = claim.claimed_at[:10]
        daily.setdefault(
            day, {"date": day, "recognitions": 0, "coupon_claims": 0, "redemptions": 0}
        )["coupon_claims"] += 1
        if claim.verified_at:
            day = claim.verified_at[:10]
            daily.setdefault(
                day, {"date": day, "recognitions": 0, "coupon_claims": 0, "redemptions": 0}
            )["redemptions"] += 1
    sources = {}
    for event in events:
        if event.recognition_id:
            recognition = session.get(RecognitionRecord, event.recognition_id)
            character_id = recognition.confirmed_character_id if recognition else None
            if character_id:
                sources[character_id] = sources.get(character_id, 0) + 1
    return {
        "users": count(session, User) if not merchant_id else None,
        "active_users_today": len(active_users),
        "recognitions": len(recognitions),
        "confirmed_recognitions": sum(bool(row.confirmed_character_id) for row in recognitions),
        "recognition_candidates": sum(bool(row.candidates) for row in recognitions),
        "recognition_failures": sum(bool(row.error_code) for row in recognitions),
        "merchant_impressions": event_counts.get("merchant_impression", 0),
        "merchant_views": event_counts.get("merchant_detail", 0),
        "navigations": event_counts.get("navigate", 0),
        "coupon_claims": len(claims),
        "redemptions": sum(row.status == "used" for row in claims),
        "quest_completions": event_counts.get("quest_complete", 0),
        "events": event_counts,
        "daily": sorted(daily.values(), key=lambda item: item["date"]),
        "sources": [
            {"character_id": key, "count": value}
            for key, value in sorted(sources.items(), key=lambda item: -item[1])
        ],
    }
