"""Independent SQL schema for reviewed recognition correction cases."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Integer, String, Text
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


class RagBase(DeclarativeBase):
    __table_args__ = MYSQL_OPTIONS


class RagCase(RagBase):
    __tablename__ = "rag_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=identifier)
    recognition_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sample_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(30), default="manual", index=True)
    original_text: Mapped[str] = mapped_column(Text, default="")
    corrected_text: Mapped[str] = mapped_column(Text, default="")
    character_id: Mapped[str] = mapped_column(String(64), index=True)
    character_name: Mapped[str] = mapped_column(String(100), default="")
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    scene: Mapped[str] = mapped_column(String(100), default="")
    source_ref: Mapped[str] = mapped_column(String(1000), default="")
    correction_note: Mapped[str] = mapped_column(Text, default="")
    image_uri: Mapped[str] = mapped_column(String(1000), default="")
    model_version: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    search_document: Mapped[str] = mapped_column(Text, default="")
    index_error: Mapped[str] = mapped_column(Text, default="")
    deprecated_reason: Mapped[str] = mapped_column(Text, default="")
    retrieval_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    indexed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now, index=True)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
