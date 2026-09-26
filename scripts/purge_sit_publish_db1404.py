"""Remove SIT_V1 fixtures and publish the curated DB1404 collection.

This is an explicit production-data maintenance command. It identifies the test
suite by its stable ``SIT_V1_`` entity prefix, removes dependent transactional
rows and fixture media, then publishes exactly 24 ``DB1404_`` characters using
the normal content service so audits and revision snapshots are retained.
"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, or_, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ASSET = re.compile(r"/api/v1/media/([a-f0-9]{32}\.png)")
SIT_PREFIX = "SIT_V1_"
DB1404_PREFIX = "DB1404_"
SIT_PATTERN = r"SIT\_V1\_%"
DB1404_PATTERN = r"DB1404\_%"


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--confirm-suite")
    parser.add_argument("--report", type=Path, default=ROOT / "runtime/data-maintenance.json")
    return parser.parse_args()


def asset_names(value):
    return set(ASSET.findall(json.dumps(value, ensure_ascii=False)))


def contains_any(value, identifiers):
    encoded = json.dumps(value, ensure_ascii=False)
    return any(identifier in encoded for identifier in identifiers)


def prune_identifiers(value, identifiers):
    if isinstance(value, dict):
        return {key: prune_identifiers(item, identifiers) for key, item in value.items()}
    if isinstance(value, list):
        return [
            prune_identifiers(item, identifiers)
            for item in value
            if not (isinstance(item, str) and item in identifiers)
        ]
    return None if isinstance(value, str) and value in identifiers else value


def main():
    args = arguments()
    from backend.app.business.content import save_entity
    from backend.app.business.database import Database
    from backend.app.business.models import (
        Audit,
        Claim,
        CouponStock,
        Enrollment,
        Entity,
        EntityRevision,
        Event,
        Favorite,
        Feedback,
        RecognitionRecord,
        Sample,
        Stamp,
        TagClaim,
        User,
    )
    from backend.app.config import Settings

    settings = Settings()
    database_name = make_url(settings.database_url).database
    if not settings.database_url.startswith("mysql+pymysql://"):
        raise SystemExit("Live maintenance requires MySQL")
    if args.execute and (args.confirm_database != database_name or args.confirm_suite != "SIT_V1"):
        raise SystemExit("Database and suite confirmations are required")

    database = Database(settings.database_url)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "database": database_name,
        "execute": args.execute,
        "deleted": {},
        "published": [],
    }
    fixture_assets = set()
    try:
        with database.write() as session:
            actor = session.scalar(
                select(User).where(User.role == "admin", User.status == "active").limit(1)
            )
            if actor is None:
                raise RuntimeError("No active administrator")
            fixtures = session.scalars(
                select(Entity).where(Entity.id.like(SIT_PATTERN, escape="\\")).with_for_update()
            ).all()
            fixture_ids = {row.id for row in fixtures}
            db1404 = session.scalars(
                select(Entity)
                .where(
                    Entity.id.like(DB1404_PATTERN, escape="\\"),
                    Entity.kind == "characters",
                )
                .order_by(Entity.id)
                .with_for_update()
            ).all()
            if len(db1404) != 24:
                raise RuntimeError("Expected exactly 24 curated DB1404 characters")

            other_entities = session.scalars(
                select(Entity).where(~Entity.id.in_(fixture_ids))
            ).all()
            external_references = [
                row.id for row in other_entities if contains_any(row.data, fixture_ids)
            ]
            report["references_pruned"] = {
                "entities": len(external_references),
                "revisions": 0,
            }

            fixture_revisions = session.scalars(
                select(EntityRevision).where(EntityRevision.entity_id.in_(fixture_ids))
            ).all()
            for row in fixtures:
                fixture_assets.update(asset_names(row.data))
            for row in fixture_revisions:
                fixture_assets.update(asset_names(row.snapshot))
            other_revisions = session.scalars(
                select(EntityRevision).where(~EntityRevision.entity_id.in_(fixture_ids))
            ).all()
            protected_assets = set()
            for row in other_entities:
                protected_assets.update(asset_names(row.data))
            for row in other_revisions:
                protected_assets.update(asset_names(row.snapshot))
            fixture_assets.difference_update(protected_assets)

            recognitions = session.scalars(select(RecognitionRecord)).all()
            recognition_ids = {
                row.request_id
                for row in recognitions
                if row.confirmed_character_id in fixture_ids
                or contains_any(row.candidates, fixture_ids)
            }
            samples = session.scalars(
                select(Sample).where(
                    or_(
                        Sample.character_id.in_(fixture_ids),
                        Sample.recognition_id.in_(recognition_ids),
                    )
                )
            ).all()
            for row in samples:
                fixture_assets.update(asset_names(row.image_uri))

            audits = session.scalars(select(Audit)).all()
            audit_ids = {
                row.id
                for row in audits
                if row.entity_id in fixture_ids
                or row.entity_id == "SIT_V1"
                or row.action == "seed_sit"
                or "SIT_V1" in json.dumps(row.detail, ensure_ascii=False)
            }
            events = session.scalars(select(Event)).all()
            event_ids = {
                row.id
                for row in events
                if row.entity_id in fixture_ids
                or row.merchant_id in fixture_ids
                or row.recognition_id in recognition_ids
                or row.event_id.startswith("SIT_V1")
            }

            targets = (
                ("samples", Sample, Sample.id.in_([row.id for row in samples])),
                (
                    "feedback",
                    Feedback,
                    or_(
                        Feedback.character_id.in_(fixture_ids),
                        Feedback.recognition_id.in_(recognition_ids),
                    ),
                ),
                ("events", Event, Event.id.in_(event_ids)),
                ("favorites", Favorite, Favorite.character_id.in_(fixture_ids)),
                (
                    "stamps",
                    Stamp,
                    or_(
                        Stamp.quest_id.in_(fixture_ids),
                        Stamp.node_id.in_(fixture_ids),
                        Stamp.character_id.in_(fixture_ids),
                    ),
                ),
                ("enrollments", Enrollment, Enrollment.quest_id.in_(fixture_ids)),
                ("claims", Claim, Claim.coupon_id.in_(fixture_ids)),
                ("coupon_stock", CouponStock, CouponStock.coupon_id.in_(fixture_ids)),
                (
                    "tag_claims",
                    TagClaim,
                    or_(
                        TagClaim.character_id.in_(fixture_ids),
                        TagClaim.merchant_id.in_(fixture_ids),
                    ),
                ),
                (
                    "recognitions",
                    RecognitionRecord,
                    RecognitionRecord.request_id.in_(recognition_ids),
                ),
                ("revisions", EntityRevision, EntityRevision.entity_id.in_(fixture_ids)),
                ("audit", Audit, Audit.id.in_(audit_ids)),
                ("entities", Entity, Entity.id.in_(fixture_ids)),
            )
            if args.execute:
                for row in other_entities:
                    if not contains_any(row.data, fixture_ids):
                        continue
                    cleaned = prune_identifiers(row.data, fixture_ids)
                    changes = {
                        key: value for key, value in cleaned.items() if value != row.data.get(key)
                    }
                    save_entity(session, row.kind, changes, actor, row.id)
                for revision in other_revisions:
                    if contains_any(revision.snapshot, fixture_ids):
                        revision.snapshot = prune_identifiers(revision.snapshot, fixture_ids)
                        report["references_pruned"]["revisions"] += 1
                for name, model, condition in targets:
                    report["deleted"][name] = session.execute(
                        delete(model).where(condition)
                    ).rowcount
                for row in db1404:
                    if row.status != "published":
                        save_entity(
                            session,
                            "characters",
                            {"status": "published"},
                            actor,
                            row.id,
                        )
                    report["published"].append(row.id)
                session.add(
                    Audit(
                        user_id=actor.id,
                        action="purge_test_and_publish_db1404",
                        entity_type="character_collection",
                        entity_id="DB1404_REPRESENTATIVE_V1",
                        detail={
                            "purged_suite": "SIT_V1",
                            "fixture_entities": len(fixture_ids),
                            "published_characters": len(db1404),
                        },
                    )
                )
            else:
                for name, model, condition in targets:
                    report["deleted"][name] = len(
                        session.scalars(select(model).where(condition)).all()
                    )
                report["published"] = [row.id for row in db1404]
                session.rollback()

        removed_assets = 0
        if args.execute:
            for name in fixture_assets:
                image = settings.media_directory / name
                metadata = settings.media_directory / f"{name}.json"
                if image.is_file():
                    image.unlink()
                    removed_assets += 1
                metadata.unlink(missing_ok=True)
        report["deleted"]["media"] = removed_assets if args.execute else len(fixture_assets)

        with database.session() as session:
            remaining = session.scalars(
                select(Entity.id).where(Entity.id.like(SIT_PATTERN, escape="\\"))
            ).all()
            published = session.scalars(
                select(Entity.id).where(
                    Entity.id.like(DB1404_PATTERN, escape="\\"),
                    Entity.kind == "characters",
                    Entity.status == "published",
                )
            ).all()
        report["verification"] = {
            "remaining_sit_entities": len(remaining),
            "published_db1404": len(published),
        }
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        print(f"STOPPED {type(exc).__name__}; inspect scoped report", flush=True)
    finally:
        database.engine.dispose()
        report["finished_at"] = datetime.now(UTC).isoformat()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
    if report.get("error_type"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
