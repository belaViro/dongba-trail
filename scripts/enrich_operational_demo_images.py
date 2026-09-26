"""Attach licensed stock images to the fictional operational demo catalog.

The command is a dry run unless ``--apply`` and an exact database-name
confirmation are both supplied. Images are downloaded, normalized, saved in
the application's media store, and attached through ``save_entity`` so audit
rows and entity revisions remain consistent.
"""

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.business.content import save_entity  # noqa: E402
from backend.app.business.database import Database  # noqa: E402
from backend.app.business.models import Entity, User  # noqa: E402
from backend.app.config import Settings  # noqa: E402
from backend.app.media import local_asset, save_asset  # noqa: E402

MANIFEST_PATH = ROOT / "data" / "operational_demo_images.json"
EXPECTED_ENTITIES = {
    "OPS_MERCHANT_PAPER": "merchants",
    "OPS_MERCHANT_TEA": "merchants",
    "OPS_MERCHANT_SILVER": "merchants",
    "OPS_MERCHANT_GIFT": "merchants",
    "OPS_PRODUCT_PAPER_KIT": "products",
    "OPS_PRODUCT_PAPER_MARK": "products",
    "OPS_PRODUCT_TEA_TABLE": "products",
    "OPS_PRODUCT_TEA_PACK": "products",
    "OPS_PRODUCT_SILVER_PENDANT": "products",
    "OPS_PRODUCT_SILVER_MARK": "products",
    "OPS_PRODUCT_HADA_BOX": "products",
    "OPS_PRODUCT_SNOW_POSTCARD": "products",
}


def database_name(url: str) -> str:
    return (make_url(url).database or "").strip("/")


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    images = manifest.get("images", [])
    by_id = {item.get("entity_id"): item.get("resource") for item in images}
    if len(by_id) != len(images):
        raise ValueError("Operational image manifest contains duplicate entity IDs")
    if by_id != EXPECTED_ENTITIES:
        missing = sorted(set(EXPECTED_ENTITIES) - set(by_id))
        extra = sorted(set(by_id) - set(EXPECTED_ENTITIES))
        mismatched = sorted(
            entity_id
            for entity_id in set(by_id) & set(EXPECTED_ENTITIES)
            if by_id[entity_id] != EXPECTED_ENTITIES[entity_id]
        )
        raise ValueError(
            f"Operational image manifest mismatch: missing={missing}, "
            f"extra={extra}, resource_mismatch={mismatched}"
        )
    for item in images:
        if not item["source_url"].startswith("https://images.unsplash.com/"):
            raise ValueError(f"Unsupported image source for {item['entity_id']}")
        if not item["source_page"].startswith("https://unsplash.com/"):
            raise ValueError(f"Unsupported source page for {item['entity_id']}")
    return manifest


def prepare_image(content: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(content)) as decoded:
            decoded.load()
            oriented = ImageOps.exif_transpose(decoded).convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Downloaded content is not a supported image") from exc
    if oriented.width < 600 or oriented.height < 400:
        raise ValueError(
            f"Source image is too small: {oriented.width}x{oriented.height}; minimum is 600x400"
        )
    fitted = ImageOps.fit(oriented, (1200, 800), method=Image.Resampling.LANCZOS)
    return Image.frombytes("RGB", fitted.size, fitted.tobytes())


def download_images(items: list[dict]) -> dict[str, Image.Image]:
    prepared = {}
    headers = {"User-Agent": "DongbaTrailDemoMedia/1.0"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=45) as client:
        for item in items:
            response = client.get(item["source_url"])
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if not content_type.startswith("image/"):
                raise ValueError(
                    f"Source for {item['entity_id']} returned {content_type or 'no content type'}"
                )
            if len(response.content) > 15 * 1024 * 1024:
                raise ValueError(f"Source for {item['entity_id']} exceeds 15 MiB")
            prepared[item["entity_id"]] = prepare_image(response.content)
    return prepared


def active_admin(session) -> User:
    actor = session.scalar(
        select(User).where(User.role == "admin", User.status == "active").order_by(User.created_at)
    )
    if actor is None:
        raise RuntimeError("No active administrator exists")
    return actor


def current_plan(
    session, settings: Settings, manifest: dict, replace: set[str] | None = None
) -> dict:
    replace = replace or set()
    rows = []
    for item in manifest["images"]:
        row = session.get(Entity, item["entity_id"])
        if row is None or row.kind != item["resource"]:
            actual = None if row is None else row.kind
            raise RuntimeError(
                f"Required entity {item['entity_id']} is {actual!r}, expected {item['resource']!r}"
            )
        image_url = row.data.get("image_url", "")
        local_available = False
        if image_url:
            try:
                local_available = local_asset(settings, image_url).is_file()
            except Exception:  # The plan reports invalid/non-local legacy URLs as replaceable.
                local_available = False
        rows.append(
            {
                "entity_id": row.id,
                "resource": row.kind,
                "status": row.status,
                "current_image_url": image_url,
                "action": "attach"
                if item["entity_id"] in replace or not local_available
                else "skip",
            }
        )
    return {
        "dataset": manifest["dataset"],
        "total": len(rows),
        "attach": sum(row["action"] == "attach" for row in rows),
        "skip": sum(row["action"] == "skip" for row in rows),
        "entities": rows,
    }


def enrich(
    database: Database, settings: Settings, manifest: dict, replace: set[str] | None = None
) -> dict:
    replace = replace or set()
    with database.session() as session:
        plan = current_plan(session, settings, manifest, replace)
    pending = {row["entity_id"] for row in plan["entities"] if row["action"] == "attach"}
    if not pending:
        return {**plan, "attached": 0, "created_assets": []}

    items = [item for item in manifest["images"] if item["entity_id"] in pending]
    images = download_images(items)
    created_assets: list[str] = []
    try:
        with database.write() as session:
            actor = active_admin(session)
            for item in items:
                row = session.get(Entity, item["entity_id"])
                if row is None or row.kind != item["resource"]:
                    raise RuntimeError(
                        f"Entity changed during image enrichment: {item['entity_id']}"
                    )
                name = save_asset(settings, images[item["entity_id"]], actor.id, "content")
                created_assets.append(name)
                metadata_path = settings.media_directory / f"{name}.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata.update(
                    {
                        "dataset": manifest["dataset"],
                        "entity_id": item["entity_id"],
                        "source_url": item["source_url"],
                        "source_page": item["source_page"],
                        "source_description": item["source_description"],
                        "license_name": manifest["license_name"],
                        "license_url": manifest["license_url"],
                        "demo_notice": manifest["notice"],
                    }
                )
                metadata_path.write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                save_entity(
                    session,
                    item["resource"],
                    {"image_url": f"/api/v1/media/{name}", "status": row.status},
                    actor,
                    item["entity_id"],
                )
    except Exception:
        for name in created_assets:
            (settings.media_directory / name).unlink(missing_ok=True)
            (settings.media_directory / f"{name}.json").unlink(missing_ok=True)
        raise

    with database.session() as session:
        verified = current_plan(session, settings, manifest)
    if verified["attach"]:
        raise RuntimeError(f"Image verification failed for {verified['attach']} entities")
    return {**verified, "attached": len(created_assets), "created_assets": created_assets}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", default="")
    parser.add_argument("--replace", action="append", default=[], metavar="ENTITY_ID")
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "runtime" / "operational-demo-image-report.json",
    )
    args = parser.parse_args()
    replace = set(args.replace)
    unknown = sorted(replace - set(EXPECTED_ENTITIES))
    if unknown:
        raise SystemExit(f"Unknown operational image entity: {', '.join(unknown)}")
    settings = Settings()
    target = database_name(settings.database_url)
    if not settings.database_url.startswith("mysql+pymysql://"):
        raise SystemExit("Operational images can only be attached in MySQL")
    manifest = load_manifest()
    database = Database(settings.database_url)
    with database.session() as session:
        plan = current_plan(session, settings, manifest, replace)
    output = {"mode": "apply" if args.apply else "dry-run", "database": target, **plan}
    if not args.apply:
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
    if args.confirm_database != target:
        raise SystemExit(f"Refusing to write: pass --confirm-database {target!r}")
    result = enrich(database, settings, manifest, replace)
    output = {"mode": "apply", "database": target, **result}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
