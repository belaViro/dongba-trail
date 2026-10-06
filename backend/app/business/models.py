"""Persistent business records. Cultural content is versioned JSON, transactions are relational."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def identifier() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(UTC).isoformat()


MYSQL_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_bin",
}


class Base(DeclarativeBase):
    __table_args__ = MYSQL_OPTIONS


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(Text, default="")
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="tourist")
    merchant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class SessionToken(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[str] = mapped_column(String(40))


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    merchant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class EntityRevision(Base):
    __tablename__ = "entity_revisions"
    __table_args__ = (UniqueConstraint("entity_id", "version"), MYSQL_OPTIONS)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    resource: Mapped[str] = mapped_column(String(30), index=True)
    version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    snapshot: Mapped[dict] = mapped_column(JSON)


class Sample(Base):
    __tablename__ = "samples"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    recognition_id: Mapped[str | None] = mapped_column(
        ForeignKey("recognitions.request_id"), nullable=True, index=True
    )
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    character_id: Mapped[str | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True, index=True
    )
    image_uri: Mapped[str] = mapped_column(String(1000))
    sample_type: Mapped[str] = mapped_column(String(20), default="real_photo")
    scene: Mapped[str] = mapped_column(String(100), default="other")
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    label_source: Mapped[str] = mapped_column(String(30), default="manual")
    review_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    dataset_split: Mapped[str] = mapped_column(String(20), default="unassigned")
    dataset_version: Mapped[str] = mapped_column(String(100), default="", index=True)
    source_ref: Mapped[str] = mapped_column(String(1000), default="")
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now, index=True)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class CouponStock(Base):
    __tablename__ = "coupon_stock"
    coupon_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    stock: Mapped[int] = mapped_column(Integer)
    claimed_count: Mapped[int] = mapped_column(Integer, default=0)


class Claim(Base):
    __tablename__ = "coupon_claims"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    coupon_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    merchant_id: Mapped[str] = mapped_column(String(64), index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="available")
    claimed_at: Mapped[str] = mapped_column(String(40), default=now)
    verified_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reward_key: Mapped[str | None] = mapped_column(String(150), unique=True, nullable=True)


class Enrollment(Base):
    __tablename__ = "quest_enrollments"
    __table_args__ = (UniqueConstraint("user_id", "quest_id"), MYSQL_OPTIONS)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    quest_id: Mapped[str] = mapped_column(ForeignKey("entities.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    joined_at: Mapped[str] = mapped_column(String(40), default=now)
    completed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reward_claim_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Stamp(Base):
    __tablename__ = "stamps"
    __table_args__ = (UniqueConstraint("user_id", "node_id"), MYSQL_OPTIONS)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    quest_id: Mapped[str] = mapped_column(String(64))
    node_id: Mapped[str] = mapped_column(ForeignKey("entities.id"))
    character_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(20))
    obtained_at: Mapped[str] = mapped_column(String(40), default=now)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class RecognitionRecord(Base):
    __tablename__ = "recognitions"
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    observed_text: Mapped[str] = mapped_column(Text, default="")
    rag_hits: Mapped[list] = mapped_column(JSON, default=list)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    scene: Mapped[str] = mapped_column(String(20), default="camera")
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed_character_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    history_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    recognition_id: Mapped[str] = mapped_column(ForeignKey("recognitions.request_id"), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    character_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class TagClaim(Base):
    __tablename__ = "tag_claims"
    __table_args__ = (UniqueConstraint("merchant_id", "character_id"), MYSQL_OPTIONS)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    merchant_id: Mapped[str] = mapped_column(String(64), index=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("entities.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("user_id", "event_id"), MYSQL_OPTIONS)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    event_id: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    event: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    merchant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    recognition_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[str] = mapped_column(String(40), default=now)
