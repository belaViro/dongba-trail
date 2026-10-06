"""SHARE-01: owner-only, idempotent asynchronous travel-poster generation."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from urllib.parse import urlsplit

from fastapi import BackgroundTasks, Depends, Request
from pydantic import Field
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from backend.app.business.auth import current_user
from backend.app.business.models import Entity, Event, User
from backend.app.errors import ApiError
from backend.app.image_provider import ensure_configured, generate_poster_art
from backend.app.media import (
    ASSET_NAME,
    PosterInput,
    local_asset,
    save_asset,
    wechat_share_code,
)
from backend.app.poster_art import finish_poster, poster_materials, share_code_material
from backend.app.system_config import image_effective

JOB_KIND = "poster_jobs"
logger = logging.getLogger(__name__)


class PosterJobInput(PosterInput):
    request_id: str = Field(min_length=12, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")


def prepare(database, settings, owner: str, payload: PosterInput):
    ids = list(dict.fromkeys(payload.character_ids))
    if not set(ids).issubset(database.allowed_poster_character_ids(owner)):
        raise ApiError(403, "CHARACTER_NOT_COLLECTED", "Choose collected characters")
    with database.session() as session:
        records = []
        for identifier in ids:
            entity = session.get(Entity, identifier)
            if entity is None or entity.kind != "characters" or entity.status != "published":
                raise ApiError(404, "CHARACTER_NOT_FOUND", "Published character was not found")
            local_asset(settings, entity.data.get("image_url", ""))
            records.append(dict(entity.data))
        active = image_effective(session, settings)
    ensure_configured(active)
    materials = poster_materials(settings, records)  # Validate before any paid image call.
    return active, records, materials


async def optional_share_code(settings):
    """SHARE-01: unavailable optional codes must not block a genuine AI poster."""
    try:
        return await wechat_share_code(settings, "poster")
    except ApiError as exc:
        if exc.code != "WECHAT_SHARE_UNAVAILABLE":
            raise
        # Do not log raw WeChat errors, request URLs, tokens, or configuration values.
        logger.warning("Poster share code unavailable; creating poster without a code")
        return None


async def generate_poster(database, settings, owner: str, payload: PosterInput):
    active, records, materials = await run_in_threadpool(
        prepare, database, settings, owner, payload
    )
    # Only send a genuine optional code; no placeholder or user-facing technical annotation.
    code = await optional_share_code(settings)
    if code is not None:
        materials.append(share_code_material(code))
    artwork = await generate_poster_art(
        active, payload.template, materials, records, payload.caption, code is not None
    )
    image = await run_in_threadpool(finish_poster, artwork, code)
    name = await run_in_threadpool(save_asset, settings, image, owner, "poster")

    def track():
        with database.write() as session:
            session.add(
                Event(
                    event_id=name[:-4],
                    user_id=owner,
                    event="poster_generate",
                    entity_type="posters",
                    entity_id=name[:-4],
                )
            )

    await run_in_threadpool(track)
    return {
        "id": name[:-4],
        "url": f"/api/v1/media/{name}",
        "share_code_available": code is not None,
    }


def poster_media_url(url: str) -> str:
    """SHARE-01: recover legacy loopback URLs without rewriting stored/paid jobs."""
    parsed = urlsplit(url)
    prefix = "/api/v1/media/"
    if (
        parsed.scheme in {"http", "https"}
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and parsed.path.startswith(prefix)
        and ASSET_NAME.fullmatch(parsed.path.removeprefix(prefix))
    ):
        return parsed.path
    return url


def job_view(row):
    result = {"id": row.id, "status": row.status}
    if row.status == "completed":
        result.update(
            url=poster_media_url(row.data["url"]),
            share_code_available=row.data["share_code_available"],
        )
    elif row.status == "failed":
        result["error_code"] = row.data.get("error_code", "IMAGE_PROVIDER_UNAVAILABLE")
    return result


def get_job(database, identifier, owner):
    with database.write() as session:
        row = session.get(Entity, identifier)
        if row is None or row.kind != JOB_KIND or row.data.get("owner") != owner:
            raise ApiError(404, "NOT_FOUND", "Poster job not found")
        # Interrupted process/host jobs become explicitly failed; never silently re-bill/retry.
        age = (datetime.now(UTC) - datetime.fromisoformat(row.created_at)).total_seconds()
        if row.status in {"queued", "generating"} and age > 480:
            row.status = "failed"
            row.data = {**row.data, "error_code": "IMAGE_PROVIDER_TIMEOUT"}
        return job_view(row)


async def work(database, settings, identifier, owner, payload):
    def transition(status, fields=None):
        with database.write() as session:
            row = session.get(Entity, identifier, with_for_update=True)
            if row is None or row.status not in {"queued", "generating"}:
                return False
            age = (datetime.now(UTC) - datetime.fromisoformat(row.created_at)).total_seconds()
            if age > 480:
                row.status = "failed"
                row.data = {**row.data, "error_code": "IMAGE_PROVIDER_TIMEOUT"}
                return False
            if status == "generating" and row.status != "queued":
                return False
            row.status = status
            row.data = {**row.data, **(fields or {})}
            return True

    if not await run_in_threadpool(transition, "generating"):
        return
    try:
        result = await generate_poster(database, settings, owner, payload)
        await run_in_threadpool(
            transition,
            "completed",
            {"url": result["url"], "share_code_available": result["share_code_available"]},
        )
    except Exception as exc:
        # Raw provider errors/URLs/credentials never enter status, audit, or client messages.
        code = exc.code if isinstance(exc, ApiError) else "IMAGE_PROVIDER_UNAVAILABLE"
        await run_in_threadpool(transition, "failed", {"error_code": code})


def install_poster_jobs(app, settings):
    @app.post("/api/v1/share/poster/jobs", status_code=202, tags=["Media"])
    async def create_job(
        payload: PosterJobInput,
        request: Request,
        tasks: BackgroundTasks,
        user: User = Depends(current_user),
    ):
        database = request.app.state.database
        digest = hashlib.sha256((user.id + "\0" + payload.request_id).encode()).hexdigest()
        identifier = "posterjob_" + digest[:52]
        fingerprint = hashlib.sha256(
            json.dumps(
                payload.model_dump(exclude={"request_id"}), ensure_ascii=False, sort_keys=True
            ).encode()
        ).hexdigest()

        def existing():
            with database.session() as session:
                row = session.get(Entity, identifier)
                if row:
                    if row.kind != JOB_KIND or row.data.get("fingerprint") != fingerprint:
                        raise ApiError(
                            409, "POSTER_REQUEST_CONFLICT", "Use a new request for changes"
                        )
                    return True
            return False

        if await run_in_threadpool(existing):
            return await run_in_threadpool(get_job, database, identifier, user.id)
        await run_in_threadpool(prepare, database, settings, user.id, payload)

        def insert():
            try:
                with database.write() as session:
                    session.add(
                        Entity(
                            id=identifier,
                            kind=JOB_KIND,
                            status="queued",
                            data={
                                "owner": user.id,
                                "fingerprint": fingerprint,
                            },
                        )
                    )
                return True
            except IntegrityError:
                existing()
                return False

        if await run_in_threadpool(insert):
            tasks.add_task(work, database, settings, identifier, user.id, payload)
        return await run_in_threadpool(get_job, database, identifier, user.id)

    @app.get("/api/v1/share/poster/jobs/{identifier}", tags=["Media"])
    def read_job(identifier: str, request: Request, user: User = Depends(current_user)):
        return get_job(request.app.state.database, identifier, user.id)
