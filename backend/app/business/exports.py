import csv
import io
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import String, cast, func, or_, select

from backend.app.errors import ApiError

from .auth import require_operations
from .content import audit, serialize
from .models import Audit, Entity, Feedback, RecognitionRecord, TagClaim, User
from .schemas import Input

router = APIRouter(prefix="/api/v1/admin/exports", tags=["Audited exports"])

EXPORTS = {
    "characters": (
        Entity,
        (
            "id",
            "cn_name",
            "source_no",
            "alias",
            "keywords",
            "commercial_tags",
            "category_l1",
            "category_l2",
            "culture_summary",
            "culture_detail",
            "source_ref",
            "image_url",
            "audio_url",
            "variants",
            "tags",
            "status",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ),
    ),
    "feedback": (
        Feedback,
        (
            "id",
            "recognition_id",
            "user_id",
            "character_id",
            "comment",
            "status",
            "review_note",
            "reviewed_by",
            "created_at",
        ),
    ),
    "recognitions": (
        RecognitionRecord,
        (
            "request_id",
            "user_id",
            "status",
            "provider",
            "model",
            "candidates",
            "latency_ms",
            "scene",
            "error_code",
            "confirmed_character_id",
            "created_at",
        ),
    ),
    "audit": (
        Audit,
        ("id", "user_id", "action", "entity_type", "entity_id", "detail", "created_at"),
    ),
    "tag-claims": (
        TagClaim,
        ("id", "merchant_id", "character_id", "status", "review_note", "reviewed_by", "created_at"),
    ),
}


class ExportInput(Input):
    q: str = Field(default="", max_length=200)
    status: str | None = Field(default=None, max_length=40)
    limit: int = Field(default=1000, ge=1, le=10000)


class ExportResult(Input):
    filename: str
    content_type: str
    content: str
    row_count: int
    truncated: bool


def csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, dict | list):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    value = str(value)
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        value = "'" + value
    return value


@router.post("/{resource}", response_model=ExportResult)
def export_records(
    resource: str, payload: ExportInput, request: Request, user: User = Depends(require_operations)
):
    if resource not in EXPORTS:
        raise ApiError(404, "EXPORT_UNAVAILABLE", "This resource cannot be exported")
    model, fields = EXPORTS[resource]
    with request.app.state.database.write() as session:
        query = select(model)
        if model is Entity:
            query = query.where(Entity.kind == "characters")
        if payload.status and hasattr(model, "status"):
            query = query.where(model.status == payload.status)
        if payload.q:
            query = query.where(
                or_(
                    *[
                        func.lower(cast(column, String)).contains(
                            payload.q.lower(), autoescape=True
                        )
                        for column in model.__table__.columns
                    ]
                )
            )
        ordering = Entity.updated_at if model is Entity else model.created_at
        rows = session.scalars(query.order_by(ordering.desc()).limit(payload.limit + 1)).all()
        truncated = len(rows) > payload.limit
        rows = rows[: payload.limit]
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(fields)
        for row in rows:
            record = serialize(row, session, privileged=True)
            writer.writerow([csv_cell(record.get(field)) for field in fields])
            if stream.tell() > 10 * 1024 * 1024:
                raise ApiError(413, "EXPORT_TOO_LARGE", "Narrow filters or reduce the export limit")
        content = "\ufeff" + stream.getvalue()
        if len(content.encode("utf-8")) > 10 * 1024 * 1024:
            raise ApiError(413, "EXPORT_TOO_LARGE", "Narrow filters or reduce the export limit")
        audit(
            session,
            user,
            "export",
            resource,
            "collection",
            {
                "row_count": len(rows),
                "truncated": truncated,
                "status": payload.status,
                "search_applied": bool(payload.q),
                "limit": payload.limit,
            },
        )
        return ExportResult(
            filename=f"dongba-{resource}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.csv",
            content_type="text/csv; charset=utf-8",
            content=content,
            row_count=len(rows),
            truncated=truncated,
        )
