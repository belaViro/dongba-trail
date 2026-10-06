"""Reviewed text-memory retrieval for recognition corrections.

RAG cases are deliberately kept separate from the business database.  The
retriever is a small, explainable lexical index: only manually reviewed cases
are searchable, and every hit exposes the matched terms and correction note.
This is not model training and never silently confirms a recognition result.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.errors import ApiError
from backend.app.rag_models import RagCase

from .business.auth import require_operations
from .business.content import audit, entity
from .business.models import Sample, User

router = APIRouter(prefix="/api/v1", tags=["RAG case library"])
SEARCHABLE_STATUSES = {"approved", "indexed"}
# AI-01 / D-065: reviewed memory is advisory. A lexical hit below this score is
# too weak to introduce a dictionary entry the vision provider never returned.
MIN_APPLY_SCORE = 0.45
TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[^\W\u4e00-\u9fff]+", re.UNICODE)


def now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_text(value: Any) -> str:
    value = "" if value is None else str(value)
    return " ".join(value.casefold().strip().split())


def text_terms(value: Any) -> list[str]:
    return [term for term in TOKEN_RE.findall(normalize_text(value)) if term]


def _strings(value: Any, limit: int = 100) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:limit] if str(item).strip()]


def build_search_document(data: dict[str, Any]) -> str:
    values = [
        data.get("original_text", ""),
        data.get("corrected_text", ""),
        data.get("character_name", ""),
        *(_strings(data.get("aliases"))),
        *(_strings(data.get("keywords"))),
        data.get("scene", ""),
        data.get("source_ref", ""),
        data.get("correction_note", ""),
    ]
    return normalize_text(" ".join(str(value) for value in values if value))


def content_hash(data: dict[str, Any]) -> str:
    canonical = {
        key: data.get(key)
        for key in (
            "original_text",
            "corrected_text",
            "character_id",
            "character_name",
            "aliases",
            "keywords",
            "scene",
            "source_ref",
            "correction_note",
            "image_uri",
            "sample_id",
        )
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def serialize_case(row: RagCase, *, score: float | None = None, matched_terms=None) -> dict:
    result = {
        "id": row.id,
        "recognition_id": row.recognition_id,
        "sample_id": row.sample_id,
        "source_type": row.source_type,
        "original_text": row.original_text,
        "corrected_text": row.corrected_text,
        "text": row.original_text,
        "answer": row.corrected_text,
        "character_id": row.character_id,
        "character_name": row.character_name,
        "aliases": row.aliases or [],
        "keywords": row.keywords or [],
        "scene": row.scene,
        "source_ref": row.source_ref,
        "correction_note": row.correction_note,
        "review_note": row.correction_note,
        "image_uri": row.image_uri,
        "model_version": row.model_version,
        "status": row.status,
        "index_error": row.index_error,
        "deprecated_reason": row.deprecated_reason,
        "retrieval_count": row.retrieval_count,
        "created_by": row.created_by,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at,
        "indexed_at": row.indexed_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if score is not None:
        result["score"] = round(score, 6)
    if matched_terms is not None:
        result["matched_terms"] = matched_terms
    return result


def _case_data(payload: dict[str, Any], previous: RagCase | None = None) -> dict[str, Any]:
    def value(name: str, alias: str = "", default: Any = ""):
        if name in payload:
            return payload[name]
        if alias and alias in payload:
            return payload[alias]
        return getattr(previous, name, default) if previous is not None else default

    data = {
        "original_text": value("original_text", "text"),
        "corrected_text": value("corrected_text", "answer"),
        "character_id": value("character_id"),
        "character_name": value("character_name"),
        "aliases": _strings(value("aliases", default=[])),
        "keywords": _strings(value("keywords", default=[])),
        "scene": value("scene"),
        "source_ref": value("source_ref"),
        "correction_note": value("correction_note", "review_note"),
        "image_uri": value("image_uri"),
        "sample_id": value("sample_id"),
        "recognition_id": value("recognition_id"),
        "model_version": value("model_version"),
    }
    for key in ("original_text", "corrected_text", "character_id"):
        data[key] = str(data[key] or "").strip()
    for key in (
        "character_name",
        "scene",
        "source_ref",
        "correction_note",
        "image_uri",
        "sample_id",
        "recognition_id",
        "model_version",
    ):
        data[key] = str(data[key] or "").strip()
    if not data["corrected_text"]:
        raise ApiError(422, "INVALID_RAG_CASE", "A correction answer is required")
    if not data["character_id"]:
        raise ApiError(422, "INVALID_RAG_CASE", "A reviewed character is required")
    data["search_document"] = build_search_document(data)
    data["content_hash"] = content_hash(data)
    return data


def upsert_pending_case(
    database, payload: dict[str, Any], *, source_type: str, actor_id: str | None = None
):
    """Create or refresh a pending case from an approved business source."""
    data = _case_data(payload)
    data["source_type"] = source_type
    with database.write() as session:
        row = None
        if data.get("recognition_id"):
            row = session.scalar(
                select(RagCase).where(RagCase.recognition_id == data["recognition_id"])
            )
        if row is None and data.get("sample_id"):
            row = session.scalar(select(RagCase).where(RagCase.sample_id == data["sample_id"]))
        if row is not None and row.content_hash == data["content_hash"]:
            return serialize_case(row)
        if row is None:
            row = RagCase(created_by=actor_id, status="pending")
            session.add(row)
        protected = {"source_type", "created_by"}
        for key, value in data.items():
            if key not in protected:
                setattr(row, key, value)
        row.source_type = source_type
        # Business corrections supersede a previously reviewed/indexed case and
        # must go through human review again before becoming searchable.
        if row.status not in {"draft", "pending"}:
            row.status = "pending"
            row.reviewed_by = None
            row.reviewed_at = None
            row.indexed_at = None
        row.index_error = ""
        row.updated_at = now()
        session.flush()
        return serialize_case(row)


def _score(query: str, document: str) -> tuple[float, list[str]]:
    query_normalized = normalize_text(query)
    document_normalized = normalize_text(document)
    if not query_normalized or not document_normalized:
        return 0.0, []
    query_terms = list(dict.fromkeys(text_terms(query_normalized)))
    matched = [term for term in query_terms if term in document_normalized]
    if not matched:
        return 0.0, []
    coverage = len(matched) / max(1, len(query_terms))
    exact = 1.0 if query_normalized in document_normalized else 0.0
    score = min(1.0, 0.55 * coverage + 0.45 * exact)
    return score, matched


def index_feedback_case(database, payload: dict, *, actor_id: str) -> dict:
    """FEEDBACK-01: the feedback review is the only approval, not a queue."""
    data = _case_data(payload)
    with database.write() as session:
        row = session.scalar(
            select(RagCase).where(RagCase.recognition_id == data["recognition_id"])
        )
        if row is not None and row.status == "deprecated":
            # Retrying a completed review must not silently reactivate a disabled case.
            return serialize_case(row)
        if row is None:
            row = RagCase(created_by=actor_id)
            session.add(row)
        for key, value in data.items():
            setattr(row, key, value)
        row.source_type = "feedback"
        row.status = "indexed"
        row.review_note = data["correction_note"]
        row.reviewed_by = actor_id
        row.reviewed_at = now()
        row.indexed_at = now()
        reindex_case(row)
        session.flush()
        return serialize_case(row)


def retrieve(database, query: str, *, limit: int = 5, business_database=None) -> list[dict]:
    if database is None or not normalize_text(query):
        return []
    with database.write() as session:
        rows = session.scalars(
            select(RagCase)
            .where(RagCase.status.in_(SEARCHABLE_STATUSES))
            .order_by(RagCase.updated_at.desc())
        ).all()
        # Separate databases cannot commit atomically. An orphaned RAG write
        # must never affect recognition before the authoritative review commits.
        approved = set()
        if business_database is not None:
            from backend.app.business.models import Feedback

            with business_database.session() as business_session:
                approved = set(
                    business_session.execute(
                        select(Feedback.recognition_id, Feedback.character_id).where(
                            Feedback.status == "approved"
                        )
                    ).all()
                )
        ranked = []
        for row in rows:
            if (
                row.source_type == "feedback"
                and (row.recognition_id, row.character_id) not in approved
            ):
                continue
            score, matched = _score(query, row.search_document)
            if score <= 0:
                continue
            ranked.append((score, row.updated_at, row, matched))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        for _, _, row, _ in ranked[:limit]:
            row.retrieval_count = (row.retrieval_count or 0) + 1
        return [
            serialize_case(row, score=score, matched_terms=matched)
            for score, _, row, matched in ranked[:limit]
        ]


def reindex_case(row: RagCase) -> None:
    data = {
        "original_text": row.original_text,
        "corrected_text": row.corrected_text,
        "character_id": row.character_id,
        "character_name": row.character_name,
        "aliases": row.aliases or [],
        "keywords": row.keywords or [],
        "scene": row.scene,
        "source_ref": row.source_ref,
        "correction_note": row.correction_note,
        "image_uri": row.image_uri,
        "sample_id": row.sample_id,
    }
    row.search_document = build_search_document(data)
    row.content_hash = content_hash(data)
    row.index_error = ""
    row.updated_at = now()
    if row.status == "approved":
        row.status = "indexed"
        row.indexed_at = now()


def reindex_all(database) -> dict[str, int]:
    with database.write() as session:
        rows = session.scalars(select(RagCase)).all()
        for row in rows:
            reindex_case(row)
        return {"total": len(rows), "indexed": sum(row.status == "indexed" for row in rows)}


def apply_hits(candidates, hits: list[dict], dictionary):
    """Add reviewed memory candidates without letting memory outrank the model.

    D-065: reviewed corrections accumulate across all visitors, so a lexical
    hit is a memory of *some past* photo, not evidence about this one. Provider
    candidates therefore keep their own order and RAG may only append published
    entries the provider did not return. Memory defines the order only when the
    provider returned no usable candidate at all, where an advisory suggestion
    is still better than a blank result.
    """
    ordered_ids: list[str] = []
    for hit in hits:
        score = hit.get("score")
        if score is not None and float(score) < MIN_APPLY_SCORE:
            continue
        character_id = hit.get("character_id")
        if character_id and character_id not in ordered_ids:
            ordered_ids.append(character_id)
    if not ordered_ids:
        return candidates, False

    merged = list(candidates)
    present = {candidate.character_id for candidate in merged}
    provider_ranked = bool(merged)
    for character_id in ordered_ids:
        if len(merged) >= 5:
            break
        character = dictionary.get(character_id)
        if character is None or character.character_id in present:
            continue
        merged.append(dictionary_candidate(character, provider_score=None))
        present.add(character.character_id)
    if provider_ranked:
        # Only report memory as applied when it actually contributed a candidate.
        return merged[:5], len(merged) > len(candidates)
    return merged[:5], bool(merged)


def dictionary_candidate(character, provider_score=None):
    from backend.app.schemas import RecognitionCandidate

    return RecognitionCandidate(
        character_id=character.character_id,
        cn_name=character.cn_name,
        culture_summary=character.culture_summary,
        source_ref=character.source_ref,
        image_url=character.image_url,
        variants=character.variants,
        provider_score=provider_score,
    )


class RagInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str | None = Field(default=None, max_length=2000)
    answer: str | None = Field(default=None, max_length=2000)
    original_text: str | None = Field(default=None, max_length=2000)
    corrected_text: str | None = Field(default=None, max_length=2000)
    character_id: str | None = Field(default=None, max_length=64)
    character_name: str | None = Field(default=None, max_length=100)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=100)
    scene: str = Field(default="", max_length=100)
    source_ref: str = Field(default="", max_length=1000)
    correction_note: str = Field(default="", max_length=2000)
    review_note: str = Field(default="", max_length=2000)
    image_uri: str = Field(default="", max_length=1000)
    sample_id: str | None = Field(default=None, max_length=64)
    recognition_id: str | None = Field(default=None, max_length=64)
    model_version: str = Field(default="", max_length=100)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["approved", "rejected", "pending"]
    review_note: str = Field(default="", max_length=2000)


class DeprecateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=2000)


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=50)


def _database(request: Request):
    database = getattr(request.app.state, "rag_database", None)
    if database is None:
        raise ApiError(503, "RAG_DATABASE_UNAVAILABLE", "The RAG database is not configured")
    try:
        with database.session() as session:
            session.execute(select(RagCase.id).limit(1))
    except SQLAlchemyError as exc:
        raise ApiError(503, "RAG_DATABASE_UNAVAILABLE", "The RAG database is unavailable") from exc
    return database


def _validate_character(request: Request, character_id: str):
    with request.app.state.database.session() as session:
        entity(session, "characters", character_id, published=True)


def _row(database, case_id: str):
    with database.session() as session:
        row = session.get(RagCase, case_id)
        if row is None:
            raise ApiError(404, "RAG_CASE_NOT_FOUND", "RAG case does not exist")
        return row


@router.get("/admin/rag/cases")
def list_cases(
    request: Request,
    q: str = "",
    status: str = "",
    character_id: str = "",
    scene: str = "",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    user: User = Depends(require_operations),
):
    database = _database(request)
    with database.session() as session:
        query = select(RagCase)
        if status:
            query = query.where(RagCase.status == status)
        if character_id:
            query = query.where(RagCase.character_id == character_id)
        if scene:
            query = query.where(RagCase.scene == scene)
        rows = session.scalars(query.order_by(RagCase.updated_at.desc())).all()
        if q:
            needle = normalize_text(q)
            rows = [row for row in rows if needle in normalize_text(row.search_document)]
        return {
            "items": [serialize_case(row) for row in rows[offset : offset + limit]],
            "total": len(rows),
        }


@router.get("/admin/rag/stats")
def stats(request: Request, user: User = Depends(require_operations)):
    database = _database(request)
    with database.session() as session:
        total = session.scalar(select(func.count()).select_from(RagCase)) or 0
        counts = {
            status: session.scalar(
                select(func.count()).select_from(RagCase).where(RagCase.status == status)
            )
            or 0
            for status in ("draft", "pending", "approved", "indexed", "rejected", "deprecated")
        }
        return {"total": total, **counts}


@router.post("/admin/rag/cases", deprecated=True)
def create_case(payload: RagInput, request: Request, user: User = Depends(require_operations)):
    _database(request)
    data = _case_data(payload.model_dump(exclude_unset=True))
    _validate_character(request, data["character_id"])
    raise ApiError(409, "RAG_FEEDBACK_WORKFLOW_REQUIRED", "Create cases by approving feedback")


@router.patch("/admin/rag/cases/{case_id}")
def update_case(
    case_id: str, payload: RagInput, request: Request, user: User = Depends(require_operations)
):
    database = _database(request)
    with database.write() as session:
        row = session.get(RagCase, case_id)
        if row is None:
            raise ApiError(404, "RAG_CASE_NOT_FOUND", "RAG case does not exist")
        if row.source_type == "feedback":
            raise ApiError(409, "RAG_FEEDBACK_WORKFLOW_REQUIRED", "Use the feedback review")
        before_hash = row.content_hash
        data = _case_data(payload.model_dump(exclude_unset=True), row)
        _validate_character(request, data["character_id"])
        for key, value in data.items():
            setattr(row, key, value)
        if row.content_hash != before_hash and row.status in SEARCHABLE_STATUSES:
            row.status = "pending"
            row.reviewed_by = None
            row.reviewed_at = None
            row.indexed_at = None
        row.updated_at = now()
        session.flush()
        result = serialize_case(row)
    with request.app.state.database.write() as session:
        audit(session, user, "update", "rag_cases", case_id, {"status": result["status"]})
    return result


@router.post("/admin/rag/cases/{case_id}/review")
def review_case(
    case_id: str, payload: ReviewInput, request: Request, user: User = Depends(require_operations)
):
    database = _database(request)
    if payload.status == "rejected" and not payload.review_note:
        raise ApiError(422, "RAG_REVIEW_NOTE_REQUIRED", "A rejection needs an explanation")
    with database.write() as session:
        row = session.get(RagCase, case_id)
        if row is None:
            raise ApiError(404, "RAG_CASE_NOT_FOUND", "RAG case does not exist")
        if row.source_type == "feedback":
            raise ApiError(409, "RAG_FEEDBACK_WORKFLOW_REQUIRED", "Use the feedback review")
        if payload.status in {"approved", "pending"}:
            _case_data(serialize_case(row))
            _validate_character(request, row.character_id)
        row.status = "indexed" if payload.status == "approved" else payload.status
        row.correction_note = payload.review_note or row.correction_note
        row.reviewed_by = user.id
        row.reviewed_at = now()
        row.indexed_at = now() if row.status == "indexed" else None
        row.updated_at = now()
        if row.status == "indexed":
            reindex_case(row)
        session.flush()
        result = serialize_case(row)
    with request.app.state.database.write() as session:
        audit(session, user, "review", "rag_cases", case_id, {"status": result["status"]})
    return result


@router.post("/admin/rag/cases/{case_id}/deprecate")
def deprecate_case(
    case_id: str,
    payload: DeprecateInput,
    request: Request,
    user: User = Depends(require_operations),
):
    database = _database(request)
    with database.write() as session:
        row = session.get(RagCase, case_id)
        if row is None:
            raise ApiError(404, "RAG_CASE_NOT_FOUND", "RAG case does not exist")
        row.status = "deprecated"
        row.deprecated_reason = payload.reason
        row.updated_at = now()
        result = serialize_case(row)
    with request.app.state.database.write() as session:
        audit(session, user, "deprecate", "rag_cases", case_id, {"reason": "provided"})
    return result


@router.post("/admin/rag/cases/{case_id}/reindex")
def reindex(case_id: str, request: Request, user: User = Depends(require_operations)):
    database = _database(request)
    with database.write() as session:
        row = session.get(RagCase, case_id)
        if row is None:
            raise ApiError(404, "RAG_CASE_NOT_FOUND", "RAG case does not exist")
        if row.source_type == "feedback":
            from backend.app.business.models import Feedback

            with request.app.state.database.session() as business_session:
                feedback = business_session.scalar(
                    select(Feedback).where(Feedback.recognition_id == row.recognition_id)
                )
                if not feedback or feedback.status != "approved":
                    raise ApiError(409, "RAG_FEEDBACK_WORKFLOW_REQUIRED", "Approve feedback first")
                if feedback.character_id != row.character_id:
                    raise ApiError(409, "RAG_FEEDBACK_WORKFLOW_REQUIRED", "Feedback differs")
            _validate_character(request, row.character_id)
            row.status = "approved"
            row.deprecated_reason = ""
        reindex_case(row)
        session.flush()
        return serialize_case(row)


@router.post("/admin/rag/rebuild")
def rebuild(request: Request, user: User = Depends(require_operations)):
    result = reindex_all(_database(request))
    with request.app.state.database.write() as session:
        audit(session, user, "rebuild", "rag_cases", "collection", result)
    return result


@router.post("/admin/rag/search")
def search(payload: SearchInput, request: Request, user: User = Depends(require_operations)):
    items = retrieve(
        _database(request),
        payload.text,
        limit=payload.limit,
        business_database=request.app.state.database,
    )
    return {"items": items, "total": len(items)}


@router.get("/admin/rag/cases/{case_id}/image")
def case_image(case_id: str, request: Request, user: User = Depends(require_operations)):
    database = _database(request)
    with database.session() as session:
        row = session.get(RagCase, case_id)
        if row is None:
            raise ApiError(404, "RAG_CASE_NOT_FOUND", "RAG case does not exist")
        image_uri, sample_id = row.image_uri, row.sample_id
    if sample_id:
        with request.app.state.database.session() as session:
            sample = session.get(Sample, sample_id)
            image_uri = sample.image_uri if sample else ""
    if not image_uri or not image_uri.startswith("/api/v1/media/"):
        raise ApiError(404, "RAG_IMAGE_UNAVAILABLE", "RAG case image is unavailable")
    from .business.samples import sample_path

    try:
        path = sample_path(request.app.state.business_settings, image_uri)
    except ApiError as exc:
        raise ApiError(404, "RAG_IMAGE_UNAVAILABLE", "RAG case image is unavailable") from exc
    if not Path(path).is_file():
        raise ApiError(404, "RAG_IMAGE_UNAVAILABLE", "RAG case image is unavailable")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
