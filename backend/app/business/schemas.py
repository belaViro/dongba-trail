from copy import copy
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Input):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: str = Field(min_length=10, max_length=256)


class Setup(Credentials):
    display_name: str = Field(min_length=1, max_length=100)


class WechatLogin(Input):
    code: str = Field(min_length=1, max_length=512)
    privacy_accepted: bool


class Variant(Input):
    image_url: str = Field(max_length=1000)
    source_ref: str = Field(min_length=1, max_length=1000)


class Content(Input):
    id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{2,64}$")
    status: Literal["draft", "reviewed", "published", "disabled"] = "draft"


class CharacterInput(Content):
    cn_name: str = Field(min_length=1, max_length=100)
    source_no: int | None = Field(default=None, ge=0)
    alias: list[str] = Field(default_factory=list, max_length=50)
    keywords: list[str] = Field(default_factory=list, max_length=100)
    commercial_tags: list[str] = Field(default_factory=list, max_length=50)
    category_l1: str = Field(default="", max_length=100)
    category_l2: str = Field(default="", max_length=100)
    culture_summary: str = Field(default="", max_length=1000)
    culture_detail: str = Field(default="", max_length=20000)
    source_ref: str = Field(default="", max_length=1000)
    image_url: str = Field(default="", max_length=1000)
    audio_url: str = Field(default="", max_length=1000)
    variants: list[Variant] = Field(default_factory=list, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=50)


class MerchantInput(Content):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    address: str = Field(default="", max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    phone: str = Field(default="", max_length=50)
    opening_hours: str = Field(default="", max_length=300)
    image_url: str = Field(default="", max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    character_ids: list[str] = Field(default_factory=list, max_length=100)
    merchant_quality: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    operation_weight: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)


class PoiInput(Content):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    poi_type: str = Field(default="landmark", max_length=100)
    merchant_id: str | None = None
    character_ids: list[str] = Field(default_factory=list, max_length=100)


class ProductInput(Content):
    merchant_id: str
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    price: float = Field(default=0, ge=0, le=1000000, allow_inf_nan=False)
    image_url: str = Field(default="", max_length=1000)
    character_ids: list[str] = Field(default_factory=list, max_length=100)


class TimedContent(Content):
    start_at: datetime
    end_at: datetime

    @field_validator("start_at", "end_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Dates require a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_period(self):
        if self.end_at <= self.start_at:
            raise ValueError("end_at must follow start_at")
        return self


class CouponInput(TimedContent):
    merchant_id: str
    title: str = Field(min_length=1, max_length=200)
    rule: str = Field(min_length=1, max_length=5000)
    stock: int = Field(ge=0, le=10000000)
    per_user_limit: int = Field(default=1, ge=1, le=100)


class ActivityInput(TimedContent):
    merchant_id: str
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    capacity: int = Field(default=1, ge=1, le=1000000)


class QuestInput(TimedContent):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    area: str = Field(default="", max_length=200)
    reward_coupon_id: str | None = None


class NodeInput(Content):
    quest_id: str
    name: str = Field(min_length=1, max_length=200)
    character_id: str | None = None
    merchant_id: str | None = None
    poi_id: str | None = None
    sequence: int = Field(default=1, ge=1, le=1000)
    condition: Literal["recognition", "qr", "geofence", "coupon", "manual"]
    radius_m: int = Field(default=100, ge=10, le=1000)
    qr_token: str | None = Field(default=None, min_length=16, max_length=200)


class UserInput(Input):
    id: str | None = None
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: str | None = Field(default=None, min_length=10, max_length=256)
    display_name: str = Field(min_length=1, max_length=100)
    role: Literal["admin", "operator", "merchant", "tourist"]
    merchant_id: str | None = None
    status: Literal["active", "disabled"] = "active"


class Confirm(Input):
    character_id: str | None = None
    comment: str = Field(default="", max_length=2000)


class Review(Input):
    status: Literal["approved", "rejected", "pending"]
    review_note: str = Field(default="", max_length=2000)


class Checkin(Input):
    node_id: str
    recognition_id: str | None = None
    qr_token: str | None = Field(default=None, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    claim_id: str | None = None


class ManualComplete(Input):
    user_id: str
    node_id: str


class Verify(Input):
    code: str = Field(min_length=1, max_length=100)


class TagRequest(Input):
    character_id: str


class EventInput(Input):
    event: Literal[
        "home_view",
        "recognize_start",
        "character_detail",
        "merchant_impression",
        "merchant_detail",
        "navigate",
        "share",
        "quest_view",
    ]
    entity_type: str | None = Field(default=None, max_length=30)
    entity_id: str | None = Field(default=None, max_length=64)
    recognition_id: str | None = None
    event_id: str = Field(min_length=8, max_length=100)


class Weights(Input):
    cultural_relevance: float = Field(default=0.35, ge=0, le=1)
    distance_score: float = Field(default=0.25, ge=0, le=1)
    merchant_quality: float = Field(default=0.15, ge=0, le=1)
    coupon_activity: float = Field(default=0.10, ge=0, le=1)
    user_behavior_match: float = Field(default=0.10, ge=0, le=1)
    operation_weight: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode="after")
    def normalized(self):
        if abs(sum(self.model_dump().values()) - 1) > 0.0001:
            raise ValueError("Recommendation weights must sum to one")
        return self


RESOURCE_SCHEMAS = {
    "characters": CharacterInput,
    "merchants": MerchantInput,
    "pois": PoiInput,
    "products": ProductInput,
    "coupons": CouponInput,
    "activities": ActivityInput,
    "quests": QuestInput,
    "quest-nodes": NodeInput,
}


def patch_schema(schema):
    fields = {}
    for key, field in schema.model_fields.items():
        optional = copy(field)
        optional.default = None
        optional.default_factory = None
        fields[key] = (field.annotation, optional)
    return create_model(f"{schema.__name__}Patch", __base__=Input, **fields)


PATCH_SCHEMAS = {resource: patch_schema(schema) for resource, schema in RESOURCE_SCHEMAS.items()}
USER_PATCH = patch_schema(UserInput)
MERCHANT_CREATE_SCHEMAS = {
    resource: create_model(
        f"Merchant{schema.__name__}", __base__=schema, merchant_id=(str | None, None)
    )
    for resource, schema in RESOURCE_SCHEMAS.items()
    if resource in {"products", "coupons", "activities"}
}
