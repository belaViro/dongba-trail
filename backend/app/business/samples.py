"""Consent-based private image collection, human review and audited dataset exports."""

import json
import re
from datetime import UTC, datetime
from io import BytesIO
from typing import Annotated, Literal
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps
from pydantic import Field, field_validator
from sqlalchemy import and_, event, or_, select
from starlette.concurrency import run_in_threadpool

from backend.app.errors import ApiError
from backend.app.recognition import validate_image

from .auth import current_user, require_operations
from .content import audit, entity, serialize
from .models import RecognitionRecord, Sample, User, now
from .schemas import Input, patch_schema

router = APIRouter(prefix="/api/v1", tags=["Image samples"])
SAMPLE_NAME = re.compile(r"^/api/v1/media/([a-f0-9]{32}\.png)$")
ReviewStatus = Literal["pending", "approved", "rejected"]


class SampleMetadata(Input):
    character_id: str | None = Field(default=None, max_length=64)
    sample_type: Literal["dictionary", "augmented", "real_photo"] = "dictionary"
    scene: str = Field(default="other", min_length=1, max_length=100)
    bbox: list[int] | None = Field(default=None, min_length=4, max_length=4)
    quality_score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    label_source: Literal["source_material", "manual", "user_correction"] = "manual"
    review_status: ReviewStatus = "pending"
    dataset_split: Literal["unassigned", "train", "val", "test"] = "unassigned"
    dataset_version: str = Field(default="", max_length=100)
    source_ref: str = Field(default="", max_length=1000)
    review_note: str = Field(default="", max_length=2000)

    @field_validator("bbox")
    @classmethod
    def valid_bbox(cls, value):
        if value is not None and (min(value) < 0 or value[2] == 0 or value[3] == 0):
            raise ValueError("Bounding box needs nonnegative origin and positive size")
        return value


SamplePatch = patch_schema(SampleMetadata)


class SampleFilters(Input):
    q: str = Field(default="", max_length=200)
    review_status: ReviewStatus | None = None
    character_id: str | None = Field(default=None, max_length=64)
    recognition_id: str | None = Field(default=None, max_length=64)
    dataset_version: str | None = Field(default=None, max_length=100)


class SampleExport(SampleFilters):
    review_status: ReviewStatus = "approved"
    limit: int = Field(default=1000, ge=1, le=10000)


def sample_path(settings, image_uri):
    match = SAMPLE_NAME.fullmatch(image_uri)
    if not match:
        raise ApiError(409, "SAMPLE_IMAGE_UNAVAILABLE", "Sample image is unavailable")
    return settings.media_directory / match[1]


def remove_sample_files(settings, image_uris):
    for image_uri in image_uris:
        path = sample_path(settings, image_uri)
        path.unlink(missing_ok=True)
        path.with_suffix(".png.json").unlink(missing_ok=True)


def _delete_rows(session, settings, rows):
    image_uris = [row.image_uri for row in rows]
    for row in rows:
        session.delete(row)
    # A failed transaction must keep both the row and its image.
    if image_uris:
        event.listen(
            session, "after_commit", lambda _: remove_sample_files(settings, image_uris), once=True
        )
    return len(rows)


def delete_samples(
    session, settings, *, user_id=None, recognition_ids=None, created_before=None, dry_run=False
) -> int:
    if user_id is None and recognition_ids is None and created_before is None:
        raise ValueError("Sample deletion requires a specific scope")
    query = select(Sample)
    if user_id is not None:
        query = query.where(Sample.user_id == user_id)
    expiration = []
    if recognition_ids is not None:
        expiration.append(Sample.recognition_id.in_(recognition_ids))
    if created_before is not None:
        expiration.append(
            and_(
                Sample.created_at < created_before,
                or_(Sample.recognition_id.is_not(None), Sample.consent_version.is_not(None)),
            )
        )
    if expiration:
        # Expiring either the recognition or the consented image ends retention.
        query = query.where(or_(*expiration))
    rows = session.scalars(query.with_for_update() if not dry_run else query).all()
    return len(rows) if dry_run else _delete_rows(session, settings, rows)


def _save_image(settings, content, owner):
    from backend.app.media import save_asset

    validate_image(content, settings)
    with Image.open(BytesIO(content)) as decoded:
        oriented = ImageOps.exif_transpose(decoded).convert("RGB")
        clean = Image.frombytes("RGB", oriented.size, oriented.tobytes())
    return "/api/v1/media/" + save_asset(settings, clean, owner, "sample")


def store_recognition_sample(
    database, settings, *, recognition_id, user_id, content, scene, consent_version
):
    if not consent_version:
        raise ApiError(422, "SAMPLE_CONSENT_REQUIRED", "Image retention requires explicit consent")
    metadata = SampleMetadata(sample_type="real_photo", scene=scene)
    image_uri = None
    try:
        with database.write() as session:
            record = session.scalar(
                select(RecognitionRecord)
                .where(
                    RecognitionRecord.request_id == recognition_id,
                    RecognitionRecord.user_id == user_id,
                    RecognitionRecord.history_deleted.is_(False),
                )
                .with_for_update()
            )
            if record is None:
                raise ApiError(404, "RECOGNITION_NOT_FOUND", "Recognition does not exist")
            existing = session.scalar(select(Sample).where(Sample.recognition_id == recognition_id))
            if existing:
                return serialize(existing)
            image_uri = _save_image(settings, content, user_id)
            row = Sample(
                **metadata.model_dump(),
                recognition_id=recognition_id,
                user_id=user_id,
                image_uri=image_uri,
                consent_version=consent_version,
            )
            session.add(row)
            session.flush()
            return serialize(row)
    except Exception:
        if image_uri:
            remove_sample_files(settings, [image_uri])
        raise


def record_sample_correction(session, recognition_id, character_id):
    for row in session.scalars(
        select(Sample).where(Sample.recognition_id == recognition_id).with_for_update()
    ):
        # A visitor correction never overwrites an operator's completed review.
        if row.review_status == "pending":
            row.character_id = character_id
            row.label_source = "user_correction"
            row.updated_at = now()


def _sample(session, sample_id, user_id=None):
    row = session.scalar(select(Sample).where(Sample.id == sample_id).with_for_update())
    if row is None or (user_id is not None and row.user_id != user_id):
        raise ApiError(404, "SAMPLE_NOT_FOUND", "Sample does not exist")
    return row


def _filtered(session, filters, user_id=None):
    query = select(Sample)
    for key in ("review_status", "character_id", "recognition_id", "dataset_version"):
        value = getattr(filters, key)
        if value is not None:
            query = query.where(getattr(Sample, key) == value)
    if user_id is not None:
        query = query.where(Sample.user_id == user_id)
    rows = session.scalars(query.order_by(Sample.created_at.desc(), Sample.id)).all()
    if filters.q:
        search = filters.q.casefold()
        rows = [
            row
            for row in rows
            if search
            in " ".join(
                str(getattr(row, field) or "")
                for field in (
                    "id",
                    "recognition_id",
                    "character_id",
                    "scene",
                    "dataset_version",
                    "source_ref",
                    "review_note",
                )
            ).casefold()
        ]
    return rows


@router.get("/admin/samples")
def list_samples(
    request: Request,
    user: User = Depends(require_operations),
    filters: SampleFilters = Depends(),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
):
    with request.app.state.database.session() as session:
        rows = _filtered(session, filters)
        return {
            "items": [serialize(row) for row in rows[offset : offset + limit]],
            "total": len(rows),
        }


@router.get("/me/samples")
def my_samples(
    request: Request,
    user: User = Depends(current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
):
    with request.app.state.database.session() as session:
        rows = _filtered(session, SampleFilters(), user.id)
        return {
            "items": [serialize(row) for row in rows[offset : offset + limit]],
            "total": len(rows),
        }


@router.post("/admin/samples/upload")
async def upload_sample(
    request: Request, file: Annotated[UploadFile, File()], user: User = Depends(require_operations)
):
    settings = request.app.state.business_settings
    content = await file.read(settings.max_image_bytes + 1)

    def store():
        image_uri = _save_image(settings, content, user.id)
        try:
            with request.app.state.database.write() as session:
                row = Sample(
                    image_uri=image_uri, sample_type="dictionary", label_source="source_material"
                )
                session.add(row)
                session.flush()
                audit(session, user, "upload", "samples", row.id)
                return serialize(row)
        except Exception:
            remove_sample_files(settings, [image_uri])
            raise

    return await run_in_threadpool(store)


@router.patch("/admin/samples/{sample_id}")
def update_sample(
    sample_id: str, payload: SamplePatch, request: Request, user: User = Depends(require_operations)
):
    from pydantic import ValidationError

    settings = request.app.state.business_settings
    with request.app.state.database.write() as session:
        row = _sample(session, sample_id)
        changes = payload.model_dump(exclude_unset=True)
        previous = {key: getattr(row, key) for key in SampleMetadata.model_fields}
        try:
            data = SampleMetadata.model_validate({**previous, **changes}).model_dump()
        except ValidationError as exc:
            raise ApiError(422, "INVALID_SAMPLE", "Sample metadata is invalid") from exc
        label_fields = (
            "character_id",
            "bbox",
            "sample_type",
            "scene",
            "quality_score",
            "label_source",
            "source_ref",
        )
        if (
            row.review_status == "approved"
            and "review_status" not in changes
            and any(data[key] != previous[key] for key in label_fields)
        ):
            data["review_status"] = "pending"
        if data["character_id"]:
            character = entity(session, "characters", data["character_id"])
        else:
            character = None
        if data["review_status"] == "approved" and (
            character is None
            or character.status not in {"reviewed", "published"}
            or not data["source_ref"]
        ):
            raise ApiError(
                422,
                "SAMPLE_REVIEW_INCOMPLETE",
                "Approval requires a reviewed character and a source",
            )
        if data["review_status"] == "rejected" and not data["review_note"]:
            raise ApiError(422, "REVIEW_NOTE_REQUIRED", "A rejection needs an explanation")
        path = sample_path(settings, row.image_uri)
        if not path.is_file():
            raise ApiError(409, "SAMPLE_IMAGE_UNAVAILABLE", "Sample image is unavailable")
        if data["bbox"]:
            with Image.open(path) as image:
                x, y, width, height = data["bbox"]
                if x + width > image.width or y + height > image.height:
                    raise ApiError(
                        422, "INVALID_SAMPLE_BBOX", "Bounding box exceeds image dimensions"
                    )
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = now()
        if data["review_status"] == "pending":
            row.reviewed_by, row.reviewed_at = None, None
        elif "review_status" in changes or any(data[key] != previous[key] for key in label_fields):
            row.reviewed_by, row.reviewed_at = user.id, now()
        audit(
            session,
            user,
            "review" if "review_status" in changes else "update",
            "samples",
            row.id,
            {
                "fields": sorted(changes),
                "previous_status": previous["review_status"],
                "review_status": row.review_status,
            },
        )
        return serialize(row)


def _image(sample_id, request, user, own=False):
    with request.app.state.database.session() as session:
        row = _sample(session, sample_id, user.id if own else None)
        path = sample_path(request.app.state.business_settings, row.image_uri)
    if not path.is_file():
        raise ApiError(404, "SAMPLE_IMAGE_UNAVAILABLE", "Sample image is unavailable")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/admin/samples/{sample_id}/image")
def sample_image(sample_id: str, request: Request, user: User = Depends(require_operations)):
    return _image(sample_id, request, user)


@router.get("/me/samples/{sample_id}/image")
def my_sample_image(sample_id: str, request: Request, user: User = Depends(current_user)):
    return _image(sample_id, request, user, own=True)


def _remove(sample_id, request, user, own=False):
    with request.app.state.database.write() as session:
        row = _sample(session, sample_id, user.id if own else None)
        _delete_rows(session, request.app.state.business_settings, [row])
        audit(session, user, "delete", "samples", row.id)
    return {"deleted": True}


@router.delete("/admin/samples/{sample_id}")
def remove_sample(sample_id: str, request: Request, user: User = Depends(require_operations)):
    return _remove(sample_id, request, user)


@router.delete("/me/samples/{sample_id}")
def remove_my_sample(sample_id: str, request: Request, user: User = Depends(current_user)):
    return _remove(sample_id, request, user, own=True)


@router.post("/admin/samples/export")
def export_samples(
    payload: SampleExport, request: Request, user: User = Depends(require_operations)
):
    settings = request.app.state.business_settings
    with request.app.state.database.write() as session:
        all_rows = _filtered(session, payload)
        rows = all_rows[: payload.limit]
        output = BytesIO()
        manifest = []
        total_bytes = 0
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for row in rows:
                path = sample_path(settings, row.image_uri)
                if not path.is_file():
                    raise ApiError(
                        409, "SAMPLE_IMAGE_UNAVAILABLE", "A selected sample image is unavailable"
                    )
                total_bytes += path.stat().st_size
                if total_bytes > 100 * 1024 * 1024:
                    raise ApiError(
                        413, "EXPORT_TOO_LARGE", "Narrow filters or reduce the export limit"
                    )
                name = f"images/{row.id}.png"
                archive.write(path, name)
                manifest.append(
                    {
                        **serialize(row),
                        "image_uri": name,
                        "approved_ground_truth": row.review_status == "approved",
                    }
                )
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "format_version": 1,
                        "exported_at": now(),
                        "review_status": payload.review_status,
                        "total": len(manifest),
                        "matched_total": len(all_rows),
                        "truncated": len(all_rows) > len(rows),
                        "items": manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        audit(
            session,
            user,
            "export",
            "samples",
            "collection",
            {
                "row_count": len(rows),
                "review_status": payload.review_status,
                "dataset_version": payload.dataset_version,
                "search_applied": bool(payload.q),
                "truncated": len(all_rows) > len(rows),
            },
        )
    filename = f"dongba-samples-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.zip"
    return Response(
        output.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
