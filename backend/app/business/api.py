from fastapi import APIRouter, Depends, Query, Request
from pydantic import ValidationError
from sqlalchemy import delete, select

from backend.app.errors import ApiError

from .auth import current_user, require_merchant, require_operations, user_dict
from .content import (
    audit,
    claim_dict,
    disable_entity,
    entity,
    list_entities,
    nearby,
    save_entity,
    save_user,
    serialize,
    weights,
)
from .models import (
    Audit,
    Claim,
    Enrollment,
    Entity,
    Event,
    Favorite,
    Feedback,
    RecognitionRecord,
    Setting,
    Stamp,
    TagClaim,
    User,
)
from .schemas import (
    MERCHANT_CREATE_SCHEMAS,
    PATCH_SCHEMAS,
    RESOURCE_SCHEMAS,
    USER_PATCH,
    Checkin,
    Confirm,
    EventInput,
    ManualComplete,
    Review,
    TagRequest,
    UserInput,
    Verify,
    Weights,
)
from .workflows import (
    claim_coupon,
    complete_node,
    delete_user_history,
    enrollment_dict,
    join_quest,
    lock_user,
    quest_nodes,
    statistics,
    verify_coupon,
)

router = APIRouter(prefix="/api/v1", tags=["Business"])
MerchantProfilePatch = PATCH_SCHEMAS["merchants"]


@router.get("/characters/{character_id}/nearby")
def character_nearby(
    character_id: str,
    request: Request,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
):
    if (latitude is None) != (longitude is None):
        raise ApiError(422, "LOCATION_INCOMPLETE", "Both coordinates are required")
    with request.app.state.database.session() as session:
        user = current_user(request) if request.headers.get("Authorization") else None
        return nearby(session, character_id, latitude, longitude, user.id if user else None)


@router.get("/map/pois")
def map_pois(
    request: Request,
    q: str = "",
    character_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    with request.app.state.database.session() as session:
        return list_entities(
            session,
            "pois",
            q=q,
            status="published",
            character_id=character_id,
            public=True,
            limit=limit,
            offset=offset,
        )


def register_public(resource):
    def listing(
        request: Request,
        q: str = "",
        merchant_id: str | None = None,
        character_id: str | None = None,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=100),
    ):
        with request.app.state.database.session() as session:
            return list_entities(
                session,
                resource,
                q=q,
                status="published",
                offset=offset,
                limit=limit,
                merchant_id=merchant_id,
                character_id=character_id,
                public=True,
            )

    def detail(entity_id: str, request: Request):
        with request.app.state.database.session() as session:
            row = entity(session, resource, entity_id, published=True)
            output = serialize(row, session)
            if resource == "quests":
                output["nodes"] = quest_nodes(session, row.id)
            return output

    router.add_api_route(f"/{resource}", listing, methods=["GET"], name=f"list_{resource}")
    router.add_api_route(
        f"/{resource}/{{entity_id}}", detail, methods=["GET"], name=f"get_{resource}"
    )


for public_resource in ("characters", "merchants", "products", "activities", "coupons", "quests"):
    register_public(public_resource)


@router.post("/coupons/{coupon_id}/claim")
def claim(
    coupon_id: str,
    request: Request,
    recognition_id: str | None = None,
    user: User = Depends(current_user),
):
    with request.app.state.database.write() as session:
        if recognition_id:
            record = session.get(RecognitionRecord, recognition_id)
            if not record or record.user_id != user.id:
                raise ApiError(404, "RECOGNITION_NOT_FOUND", "Recognition does not exist")
        result = claim_coupon(session, coupon_id, user.id)
        if recognition_id:
            session.flush()
            event = session.scalar(
                select(Event).where(Event.event_id == f"server:coupon_claim:{result.id}")
            )
            event.recognition_id = recognition_id
        return claim_dict(session, result)


@router.post("/coupons/verify")
def verify(payload: Verify, request: Request, user: User = Depends(require_merchant)):
    with request.app.state.database.write() as session:
        return verify_coupon(session, payload.code, user)


@router.get("/me/coupons")
def my_coupons(request: Request, user: User = Depends(current_user)):
    with request.app.state.database.session() as session:
        rows = session.scalars(
            select(Claim).where(Claim.user_id == user.id).order_by(Claim.claimed_at.desc())
        ).all()
        return {"items": [claim_dict(session, row) for row in rows], "total": len(rows)}


@router.post("/quests/{quest_id}/join")
def join(quest_id: str, request: Request, user: User = Depends(current_user)):
    with request.app.state.database.write() as session:
        return join_quest(session, quest_id, user)


@router.post("/quests/{quest_id}/checkin")
def checkin(quest_id: str, payload: Checkin, request: Request, user: User = Depends(current_user)):
    with request.app.state.database.write() as session:
        return complete_node(session, quest_id, payload, user)


@router.get("/me/quests")
def my_quests(request: Request, user: User = Depends(current_user)):
    with request.app.state.database.session() as session:
        rows = session.scalars(
            select(Enrollment)
            .where(Enrollment.user_id == user.id)
            .order_by(Enrollment.joined_at.desc())
        ).all()
        return {"items": [enrollment_dict(session, row) for row in rows], "total": len(rows)}


@router.get("/me/stamps")
def my_stamps(request: Request, user: User = Depends(current_user)):
    with request.app.state.database.session() as session:
        rows = session.scalars(
            select(Stamp).where(Stamp.user_id == user.id).order_by(Stamp.obtained_at.desc())
        ).all()
        items = [
            {**serialize(row), "name": session.get(Entity, row.node_id).data["name"]}
            for row in rows
        ]
        return {"items": items, "total": len(items)}


@router.get("/me/history")
def history(
    request: Request,
    user: User = Depends(current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
):
    with request.app.state.database.session() as session:
        rows = session.scalars(
            select(RecognitionRecord)
            .where(
                RecognitionRecord.user_id == user.id, RecognitionRecord.history_deleted.is_(False)
            )
            .order_by(RecognitionRecord.created_at.desc())
        ).all()
        return {
            "items": [serialize(row) for row in rows[offset : offset + limit]],
            "total": len(rows),
        }


@router.delete("/me/history")
def clear_history(request: Request, user: User = Depends(current_user)):
    with request.app.state.database.write() as session:
        lock_user(session, user.id)
        removed = delete_user_history(session, user.id)
        audit(session, user, "delete_history", "users", user.id, {"removed": removed})
    return {"deleted": removed}


@router.get("/me/favorites")
def favorites(request: Request, user: User = Depends(current_user)):
    with request.app.state.database.session() as session:
        rows = session.scalars(
            select(Entity)
            .join(Favorite, Favorite.character_id == Entity.id)
            .where(Favorite.user_id == user.id, Entity.status == "published")
            .order_by(Favorite.created_at.desc())
        ).all()
        return {"items": [serialize(row) for row in rows], "total": len(rows)}


@router.put("/me/favorites/{character_id}")
def favorite(character_id: str, request: Request, user: User = Depends(current_user)):
    with request.app.state.database.write() as session:
        lock_user(session, user.id)
        character = entity(session, "characters", character_id, published=True)
        key = {"user_id": user.id, "character_id": character_id}
        if session.get(Favorite, key) is None:
            session.add(Favorite(**key))
        return serialize(character)


@router.delete("/me/favorites/{character_id}")
def unfavorite(character_id: str, request: Request, user: User = Depends(current_user)):
    with request.app.state.database.write() as session:
        session.execute(
            delete(Favorite).where(
                Favorite.user_id == user.id, Favorite.character_id == character_id
            )
        )
    return {"removed": True}


@router.post("/recognize/{recognition_id}/confirm")
def confirm(
    recognition_id: str, payload: Confirm, request: Request, user: User = Depends(current_user)
):
    with request.app.state.database.write() as session:
        record = session.scalar(
            select(RecognitionRecord)
            .where(RecognitionRecord.request_id == recognition_id)
            .with_for_update()
        )
        if not record or record.user_id != user.id or record.history_deleted:
            raise ApiError(404, "RECOGNITION_NOT_FOUND", "Recognition does not exist")
        if payload.character_id:
            allowed = {item["character_id"] for item in record.candidates}
            if payload.character_id not in allowed:
                raise ApiError(
                    422, "CANDIDATE_INVALID", "Selection must belong to the original candidates"
                )
            entity(session, "characters", payload.character_id, published=True)
        elif not payload.comment:
            raise ApiError(422, "FEEDBACK_EMPTY", "Select a candidate or describe the correction")
        feedback = session.scalar(select(Feedback).where(Feedback.recognition_id == recognition_id))
        if feedback and feedback.status != "pending":
            if (
                feedback.character_id == payload.character_id
                and feedback.comment == payload.comment
            ):
                return serialize(feedback)
            raise ApiError(409, "FEEDBACK_REVIEWED", "Reviewed feedback cannot be changed")
        if feedback is None:
            feedback = Feedback(recognition_id=recognition_id, user_id=user.id)
            session.add(feedback)
        feedback.character_id, feedback.comment = payload.character_id, payload.comment
        record.confirmed_character_id = payload.character_id
        session.flush()
        return serialize(feedback)


@router.post("/events")
def event_ingest(payload: EventInput, request: Request, user: User = Depends(current_user)):
    with request.app.state.database.write() as session:
        lock_user(session, user.id)
        existing = session.scalar(
            select(Event).where(Event.event_id == payload.event_id, Event.user_id == user.id)
        )
        if existing:
            if existing.user_id != user.id:
                raise ApiError(409, "EVENT_ID_CONFLICT", "Event identifier is already in use")
            return {"accepted": True, "duplicate": True}
        merchant_id = None
        if payload.entity_id:
            if payload.entity_type not in RESOURCE_SCHEMAS:
                raise ApiError(422, "EVENT_ENTITY_INVALID", "Event entity type is invalid")
            row = entity(session, payload.entity_type, payload.entity_id, published=True)
            merchant_id = row.id if row.kind == "merchants" else row.merchant_id
        if payload.recognition_id:
            recognition = session.get(RecognitionRecord, payload.recognition_id)
            if not recognition or recognition.user_id != user.id:
                raise ApiError(404, "RECOGNITION_NOT_FOUND", "Recognition does not exist")
        session.add(Event(**payload.model_dump(), user_id=user.id, merchant_id=merchant_id))
        return {"accepted": True, "duplicate": False}


@router.get("/admin/stats")
def admin_stats(request: Request, user: User = Depends(require_operations)):
    with request.app.state.database.session() as session:
        return statistics(session)


@router.get("/merchant/stats")
def merchant_stats(request: Request, user: User = Depends(require_merchant)):
    with request.app.state.database.session() as session:
        return statistics(session, user.merchant_id)


@router.get("/admin/settings")
def get_settings(request: Request, user: User = Depends(require_operations)):
    with request.app.state.database.session() as session:
        return weights(session)


@router.patch("/admin/settings")
def patch_settings(payload: dict, request: Request, user: User = Depends(require_operations)):
    with request.app.state.database.write() as session:
        try:
            value = Weights.model_validate({**weights(session), **payload}).model_dump()
        except ValidationError as exc:
            raise ApiError(
                422, "INVALID_WEIGHTS", "Known weights must be between zero and one and sum to one"
            ) from exc
        record = session.get(Setting, "recommendation_weights")
        if record is None:
            session.add(Setting(key="recommendation_weights", value=value))
        else:
            record.value = value
        audit(session, user, "update", "settings", "recommendation_weights", value)
        return value


@router.post("/admin/quests/{quest_id}/complete-node")
def manual_node(
    quest_id: str,
    payload: ManualComplete,
    request: Request,
    actor: User = Depends(require_operations),
):
    with request.app.state.database.write() as session:
        user = session.get(User, payload.user_id)
        if user is None:
            raise ApiError(404, "USER_NOT_FOUND", "User not found")
        return complete_node(
            session, quest_id, Checkin(node_id=payload.node_id), user, manual_actor=actor
        )


def special_list(request, model, q, status, offset, limit, *, merchant_id=None):
    with request.app.state.database.session() as session:
        query = select(model)
        if merchant_id:
            query = query.where(model.merchant_id == merchant_id)
        if status and hasattr(model, "status"):
            query = query.where(model.status == status)
        ordering = model.claimed_at if model is Claim else model.created_at
        rows = session.scalars(query.order_by(ordering.desc())).all()
        data = [
            claim_dict(session, row) if isinstance(row, Claim) else serialize(row) for row in rows
        ]
        if q:
            data = [row for row in data if q.casefold() in str(row).casefold()]
        return {"items": data[offset : offset + limit], "total": len(data)}


def register_special(resource, model):
    def listing(
        request: Request,
        user: User = Depends(require_operations),
        q: str = "",
        status: str | None = None,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=100),
    ):
        return special_list(request, model, q, status, offset, limit)

    router.add_api_route(
        f"/admin/{resource}", listing, methods=["GET"], name=f"admin_list_{resource}"
    )


for special_resource, special_model in (
    ("feedback", Feedback),
    ("recognitions", RecognitionRecord),
    ("audit", Audit),
    ("tag-claims", TagClaim),
):
    register_special(special_resource, special_model)


@router.patch("/admin/feedback/{feedback_id}")
def review_feedback(
    feedback_id: str, payload: Review, request: Request, user: User = Depends(require_operations)
):
    with request.app.state.database.write() as session:
        row = session.get(Feedback, feedback_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Feedback not found")
        if payload.status == "rejected" and not payload.review_note:
            raise ApiError(422, "REVIEW_NOTE_REQUIRED", "A rejection needs an explanation")
        row.status, row.review_note, row.reviewed_by = payload.status, payload.review_note, user.id
        audit(session, user, "review", "feedback", row.id, payload.model_dump())
        return serialize(row)


@router.patch("/admin/tag-claims/{claim_id}")
def review_tag(
    claim_id: str, payload: Review, request: Request, user: User = Depends(require_operations)
):
    with request.app.state.database.write() as session:
        row = session.scalar(select(TagClaim).where(TagClaim.id == claim_id).with_for_update())
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Tag claim not found")
        if payload.status == "rejected" and not payload.review_note:
            raise ApiError(422, "REVIEW_NOTE_REQUIRED", "A rejection needs an explanation")
        merchant = entity(session, "merchants", row.merchant_id, lock=True)
        relationships = set(merchant.data.get("character_ids", []))
        if payload.status == "approved":
            entity(session, "characters", row.character_id, published=True)
            relationships.add(row.character_id)
        else:
            relationships.discard(row.character_id)
        merchant.data = {**merchant.data, "character_ids": sorted(relationships)}
        row.status, row.review_note, row.reviewed_by = payload.status, payload.review_note, user.id
        audit(session, user, "review", "tag-claims", row.id, payload.model_dump())
        return serialize(row)


@router.get("/merchant/profile")
def merchant_profile(request: Request, user: User = Depends(require_merchant)):
    with request.app.state.database.session() as session:
        return serialize(entity(session, "merchants", user.merchant_id), session, privileged=True)


@router.patch("/merchant/profile")
def update_profile(
    payload: MerchantProfilePatch, request: Request, user: User = Depends(require_merchant)
):
    with request.app.state.database.write() as session:
        return save_entity(
            session,
            "merchants",
            payload.model_dump(mode="json", exclude_unset=True),
            user,
            user.merchant_id,
            merchant=True,
        )


@router.get("/merchant/tag-claims")
def tag_claims(
    request: Request,
    user: User = Depends(require_merchant),
    q: str = "",
    status: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
):
    return special_list(request, TagClaim, q, status, offset, limit, merchant_id=user.merchant_id)


@router.post("/merchant/tag-claims")
def request_tag(payload: TagRequest, request: Request, user: User = Depends(require_merchant)):
    with request.app.state.database.write() as session:
        entity(session, "merchants", user.merchant_id, lock=True)
        entity(session, "characters", payload.character_id, published=True)
        existing = session.scalar(
            select(TagClaim).where(
                TagClaim.merchant_id == user.merchant_id,
                TagClaim.character_id == payload.character_id,
            )
        )
        if existing:
            if existing.status == "rejected":
                existing.status, existing.review_note, existing.reviewed_by = "pending", "", None
            return serialize(existing)
        row = TagClaim(merchant_id=user.merchant_id, character_id=payload.character_id)
        session.add(row)
        session.flush()
        audit(session, user, "request", "tag-claims", row.id)
        return serialize(row)


@router.get("/merchant/redemptions")
def redemptions(
    request: Request,
    user: User = Depends(require_merchant),
    q: str = "",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
):
    return special_list(request, Claim, q, "used", offset, limit, merchant_id=user.merchant_id)


def register_admin(resource):
    def listing(
        request: Request,
        user: User = Depends(require_operations),
        q: str = "",
        status: str | None = None,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=100),
    ):
        with request.app.state.database.session() as session:
            if resource == "users":
                if user.role != "admin":
                    raise ApiError(403, "FORBIDDEN", "Only administrators can view accounts")
                rows = session.scalars(select(User).order_by(User.created_at.desc())).all()
                rows = [
                    row
                    for row in rows
                    if (not status or row.status == status)
                    and (not q or q.casefold() in f"{row.username} {row.display_name}".casefold())
                ]
                return {
                    "items": [user_dict(row) for row in rows[offset : offset + limit]],
                    "total": len(rows),
                }
            return list_entities(session, resource, q=q, status=status, offset=offset, limit=limit)

    def create(payload: dict, request: Request, user: User = Depends(require_operations)):
        payload = payload.model_dump(mode="json", exclude_unset=True)
        with request.app.state.database.write() as session:
            return (
                save_user(session, payload, user)
                if resource == "users"
                else save_entity(session, resource, payload, user)
            )

    def patch(
        entity_id: str, payload: dict, request: Request, user: User = Depends(require_operations)
    ):
        payload = payload.model_dump(mode="json", exclude_unset=True)
        with request.app.state.database.write() as session:
            return (
                save_user(session, payload, user, entity_id)
                if resource == "users"
                else save_entity(session, resource, payload, user, entity_id)
            )

    def remove(entity_id: str, request: Request, user: User = Depends(require_operations)):
        with request.app.state.database.write() as session:
            return disable_entity(session, resource, entity_id, user)

    create.__annotations__["payload"] = (
        UserInput if resource == "users" else RESOURCE_SCHEMAS[resource]
    )
    patch.__annotations__["payload"] = (
        USER_PATCH if resource == "users" else PATCH_SCHEMAS[resource]
    )
    router.add_api_route(
        f"/admin/{resource}", listing, methods=["GET"], name=f"admin_list_{resource}"
    )
    router.add_api_route(
        f"/admin/{resource}", create, methods=["POST"], name=f"admin_create_{resource}"
    )
    router.add_api_route(
        f"/admin/{resource}/{{entity_id}}",
        patch,
        methods=["PATCH"],
        name=f"admin_update_{resource}",
    )
    router.add_api_route(
        f"/admin/{resource}/{{entity_id}}",
        remove,
        methods=["DELETE"],
        name=f"admin_disable_{resource}",
    )


for admin_resource in (*RESOURCE_SCHEMAS, "users"):
    register_admin(admin_resource)


def register_merchant(resource):
    def listing(
        request: Request,
        user: User = Depends(require_merchant),
        q: str = "",
        status: str | None = None,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=100),
    ):
        with request.app.state.database.session() as session:
            return list_entities(
                session,
                resource,
                q=q,
                status=status,
                offset=offset,
                limit=limit,
                merchant_id=user.merchant_id,
            )

    def create(payload: dict, request: Request, user: User = Depends(require_merchant)):
        payload = payload.model_dump(mode="json", exclude_unset=True)
        with request.app.state.database.write() as session:
            return save_entity(session, resource, payload, user, merchant=True)

    def patch(
        entity_id: str, payload: dict, request: Request, user: User = Depends(require_merchant)
    ):
        payload = payload.model_dump(mode="json", exclude_unset=True)
        with request.app.state.database.write() as session:
            return save_entity(session, resource, payload, user, entity_id, merchant=True)

    def remove(entity_id: str, request: Request, user: User = Depends(require_merchant)):
        with request.app.state.database.write() as session:
            return disable_entity(session, resource, entity_id, user, merchant=True)

    create.__annotations__["payload"] = MERCHANT_CREATE_SCHEMAS[resource]
    patch.__annotations__["payload"] = PATCH_SCHEMAS[resource]
    router.add_api_route(
        f"/merchant/{resource}", listing, methods=["GET"], name=f"merchant_list_{resource}"
    )
    router.add_api_route(
        f"/merchant/{resource}", create, methods=["POST"], name=f"merchant_create_{resource}"
    )
    router.add_api_route(
        f"/merchant/{resource}/{{entity_id}}",
        patch,
        methods=["PATCH"],
        name=f"merchant_update_{resource}",
    )
    router.add_api_route(
        f"/merchant/{resource}/{{entity_id}}",
        remove,
        methods=["DELETE"],
        name=f"merchant_disable_{resource}",
    )


for merchant_resource in ("products", "coupons", "activities"):
    register_merchant(merchant_resource)
