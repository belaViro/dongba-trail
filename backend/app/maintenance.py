"""Bounded retention of personal history and unused generated media."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from starlette.concurrency import run_in_threadpool

from backend.app.business.models import (
    Entity,
    EntityRevision,
    Event,
    Feedback,
    LoginAttempt,
    RecognitionRecord,
    Sample,
    SessionToken,
)
from backend.app.business.samples import delete_samples
from backend.app.media import ASSET_NAME, referenced_asset_names

logger = logging.getLogger(__name__)


def purge_expired(database, settings, *, current_time=None, dry_run=False):
    current_time = current_time or datetime.now(UTC)
    cutoff = current_time - timedelta(days=settings.retention_days)
    counts = {
        "recognitions": 0,
        "feedback": 0,
        "events": 0,
        "sessions": 0,
        "samples": 0,
        "media": 0,
    }
    with database.write() as session:
        # Lock before deleting related rows so concurrent confirmations cannot race cleanup.
        ids = session.scalars(
            select(RecognitionRecord.request_id)
            .where(RecognitionRecord.created_at < cutoff.isoformat())
            .with_for_update()
        ).all()
        counts["recognitions"] = len(ids)
        counts["samples"] = delete_samples(
            session,
            settings,
            recognition_ids=ids,
            created_before=cutoff.isoformat(),
            dry_run=dry_run,
        )
        session.flush()
        queries = {
            "feedback": (Feedback, Feedback.recognition_id.in_(ids)),
            "events": (Event, Event.created_at < cutoff.isoformat()),
            "sessions": (SessionToken, SessionToken.expires_at < current_time.isoformat()),
        }
        for key, (model, condition) in queries.items():
            if dry_run:
                counts[key] = len(session.scalars(select(model).where(condition)).all())
            else:
                counts[key] = session.execute(delete(model).where(condition)).rowcount
        if not dry_run:
            session.execute(
                update(Event).where(Event.recognition_id.in_(ids)).values(recognition_id=None)
            )
            session.execute(delete(RecognitionRecord).where(RecognitionRecord.request_id.in_(ids)))
            session.execute(
                delete(LoginAttempt).where(
                    LoginAttempt.started_at < (current_time - timedelta(days=1)).isoformat()
                )
            )
        referenced = referenced_asset_names(
            settings, (row.data for row in session.scalars(select(Entity)).all())
        )
        referenced.update(
            referenced_asset_names(settings, session.scalars(select(EntityRevision.snapshot)).all())
        )
        # Dictionary source samples are operator-managed. Active samples must not
        # be removed by the generic unused-media sweep (including during dry-run).
        referenced.update(
            uri.rsplit("/", 1)[-1] for uri in session.scalars(select(Sample.image_uri))
        )
    for metadata_path in settings.media_directory.glob("*.png.json"):
        name = metadata_path.name.removesuffix(".json")
        if not ASSET_NAME.fullmatch(name) or name in referenced:
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if datetime.fromisoformat(metadata["created_at"]) >= cutoff:
                continue
            counts["media"] += 1
            if not dry_run:
                (settings.media_directory / name).unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning("retention_media_invalid asset=%s", name)
    return counts


async def retention_loop(database, settings):
    while True:
        await asyncio.sleep(3600)
        try:
            counts = await run_in_threadpool(purge_expired, database, settings)
            logger.info("retention_complete counts=%s", counts)
        except Exception as exc:
            logger.error("retention_failed error_type=%s", type(exc).__name__)
