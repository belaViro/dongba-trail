"""Prepare and add the curated DB1404 character set through the admin API.

Preparation is local and read-only against the supplied dataset. Live import is
explicit, additive-only, requires MySQL database confirmation, and never reads
or resets an administrator password.
"""

import argparse
import json
import shutil
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SUPPORTED_COLLECTIONS = {
    "DB1404_REPRESENTATIVE_V1",
    "DB1404_REPRESENTATIVE_EXPANSION_V2",
}
IMPORT_PACING_SECONDS = 1.7


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/db1404_curated.json")
    parser.add_argument("--source-dir", type=Path, default=ROOT / "数据集/DB1404")
    parser.add_argument("--bundle-dir", type=Path, default=ROOT / "runtime/db1404/import-bundle")
    parser.add_argument("--bundle-zip", type=Path, default=ROOT / "runtime/db1404-import.zip")
    parser.add_argument("--report", type=Path, default=ROOT / "runtime/db1404-import-report.json")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--import-live", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--base", default="http://127.0.0.1:8010")
    return parser.parse_args()


def load_manifest(path):
    content = json.loads(path.read_text(encoding="utf-8"))
    collection = content.get("collection")
    entries = content.get("entries", [])
    if collection not in SUPPORTED_COLLECTIONS or not entries:
        raise SystemExit("Expected a supported non-empty DB1404 collection")
    numbers = [entry["source_no"] for entry in entries]
    if len(numbers) != len(set(numbers)):
        raise SystemExit("Duplicate DB1404 source number")
    return content


def image_path(source_dir, number, filename):
    path = source_dir / f"{number:04d}" / filename
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def normalized_image(source, target):
    with Image.open(source) as image:
        clean = ImageOps.exif_transpose(image).convert("L")
        clean = ImageOps.autocontrast(clean).resize((512, 512), Image.Resampling.LANCZOS)
        clean.convert("RGB").save(target, format="PNG", optimize=True)


def prepare(manifest, source_dir, bundle_dir, bundle_zip):
    if bundle_dir.exists():
        resolved = bundle_dir.resolve()
        runtime = (ROOT / "runtime").resolve()
        if runtime not in resolved.parents:
            raise SystemExit("Bundle cleanup is restricted to project runtime")
        shutil.rmtree(bundle_dir)
    image_dir = bundle_dir / "images"
    image_dir.mkdir(parents=True)
    packaged = {**manifest, "prepared_at": datetime.now(UTC).isoformat()}
    for entry in packaged["entries"]:
        number = entry["source_no"]
        outputs = []
        for role, key in (("primary", "primary_file"), ("variant", "variant_file")):
            target_name = f"DB1404_{number:04d}-{role}.png"
            normalized_image(image_path(source_dir, number, entry[key]), image_dir / target_name)
            outputs.append(target_name)
        entry["prepared_images"] = outputs
    (bundle_dir / "manifest.json").write_text(
        json.dumps(packaged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    bundle_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_dir).as_posix())
    print(json.dumps({"prepared": len(packaged["entries"]), "zip": str(bundle_zip)}))


def payload(entry, source_title, notice, image_urls):
    number = entry["source_no"]
    status = entry.get("status", "draft")
    source = f"{source_title}，第{entry['page']}页，编号{number}；DB1404/{number:04d}"
    detail = "\n\n".join(
        (
            entry["intro"],
            entry["visual"],
            entry["usage"],
            "本词条选取同一编号下两份手写样本，用于展示书写者之间在线条、比例和局部连接上的差异；两图均保持相同释义，不据此推定年代或流派。",
            f"资料位置：{source}。{notice}",
        )
    )
    return {
        "id": f"DB1404_{number:04d}",
        "status": status,
        "cn_name": entry["name"],
        "source_no": number,
        "alias": entry["aliases"],
        "keywords": list(
            dict.fromkeys(["DB1404", entry["name"], entry["category_l1"], entry["category_l2"]])
        ),
        "commercial_tags": [],
        "category_l1": entry["category_l1"],
        "category_l2": entry["category_l2"],
        "culture_summary": entry["intro"],
        "culture_detail": detail,
        "source_ref": source,
        "image_url": image_urls[0],
        "audio_url": "",
        "variants": [{"image_url": image_urls[1], "source_ref": f"{source}，同类手写样本"}],
        "tags": ["DB1404", "代表字", "已发布" if status == "published" else "待审核"],
    }


def remove_uploaded(settings, urls):
    for url in urls:
        name = url.rsplit("/", 1)[-1]
        for path in (settings.media_directory / name, settings.media_directory / f"{name}.json"):
            path.unlink(missing_ok=True)


def live_import(manifest, bundle_dir, report_path, base, confirmation):
    if not confirmation:
        raise SystemExit("--confirm-database is required for live import")
    from sqlalchemy import delete, func, select
    from sqlalchemy.engine import make_url

    from backend.app.business.auth import digest, token_response
    from backend.app.business.database import Database
    from backend.app.business.models import Audit, Entity, EntityRevision, SessionToken, User
    from backend.app.config import Settings

    settings = Settings()
    if not settings.database_url.startswith("mysql+pymysql://"):
        raise SystemExit("Live import requires MySQL")
    if make_url(settings.database_url).database != confirmation:
        raise SystemExit("Database confirmation mismatch; no changes made")
    packaged = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    if packaged["collection"] != manifest["collection"]:
        raise SystemExit("Bundle/manifest collection mismatch")
    database = Database(settings.database_url)
    token = None
    report = {
        "collection": manifest["collection"],
        "started_at": datetime.now(UTC).isoformat(),
        "created": [],
        "existing": [],
        "verified": [],
    }
    try:
        with database.write() as session:
            identity = session.execute(
                select(
                    User.id,
                    User.username,
                    User.display_name,
                    User.role,
                    User.merchant_id,
                    User.status,
                    User.created_at,
                )
                .where(User.role == "admin", User.status == "active")
                .limit(1)
            ).one_or_none()
            if identity is None:
                raise RuntimeError("No active administrator")
            actor = SimpleNamespace(**identity._mapping)
            token = token_response(session, actor, SimpleNamespace(session_hours=1))["access_token"]
            session.add(
                Audit(
                    user_id=actor.id,
                    action="import_db1404",
                    entity_type="character_collection",
                    entity_id=manifest["collection"],
                    detail={"count": len(packaged["entries"]), "additive_only": True},
                )
            )
        with httpx.Client(
            base_url=base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            trust_env=False,
        ) as client:
            me = client.get("/api/v1/auth/me")
            me.raise_for_status()
            if me.json()["id"] != actor.id:
                raise RuntimeError("API/database identity mismatch")
            for entry in packaged["entries"]:
                entity_id = f"DB1404_{entry['source_no']:04d}"
                with database.session() as session:
                    exists = session.get(Entity, entity_id) is not None
                if exists:
                    report["existing"].append(entity_id)
                    continue
                uploaded = []
                try:
                    for filename in entry["prepared_images"]:
                        path = bundle_dir / "images" / filename
                        with path.open("rb") as stream:
                            response = client.post(
                                "/api/v1/media", files={"file": (filename, stream, "image/png")}
                            )
                        response.raise_for_status()
                        uploaded.append(response.json()["url"])
                    response = client.post(
                        "/api/v1/admin/characters",
                        json=payload(entry, packaged["source_title"], packaged["notice"], uploaded),
                    )
                    response.raise_for_status()
                    report["created"].append(entity_id)
                except Exception:
                    remove_uploaded(settings, uploaded)
                    raise
                time.sleep(IMPORT_PACING_SECONDS)
            with database.session() as session:
                for entry in packaged["entries"]:
                    entity_id = f"DB1404_{entry['source_no']:04d}"
                    expected_status = entry.get("status", "draft")
                    row = session.get(Entity, entity_id)
                    revision_count = session.scalar(
                        select(func.count())
                        .select_from(EntityRevision)
                        .where(EntityRevision.entity_id == entity_id)
                    )
                    urls = (
                        []
                        if row is None
                        else [
                            row.data.get("image_url", ""),
                            *(item.get("image_url", "") for item in row.data.get("variants", [])),
                        ]
                    )
                    assets_present = all(
                        (settings.media_directory / url.rsplit("/", 1)[-1]).is_file()
                        and (settings.media_directory / f"{url.rsplit('/', 1)[-1]}.json").is_file()
                        for url in urls
                    )
                    valid = bool(
                        row
                        and row.kind == "characters"
                        and row.status == expected_status
                        and row.data.get("source_no") == entry["source_no"]
                        and row.data.get("cn_name") == entry["name"]
                        and row.data.get("image_url")
                        and len(row.data.get("variants", [])) == 1
                        and assets_present
                        and revision_count
                    )
                    report["verified"].append(
                        {
                            "id": entity_id,
                            "valid": valid,
                            "assets": len(urls),
                            "revisions": revision_count,
                        }
                    )
                    if not valid:
                        raise RuntimeError("Imported entity verification failed")
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        print(f"STOPPED {type(exc).__name__}; inspect scoped report", flush=True)
    finally:
        if token:
            with database.write() as session:
                session.execute(
                    delete(SessionToken).where(SessionToken.token_hash == digest(token))
                )
        database.engine.dispose()
        report["finished_at"] = datetime.now(UTC).isoformat()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "created": len(report["created"]),
                    "existing": len(report["existing"]),
                    "verified": sum(item["valid"] for item in report["verified"]),
                    "error_type": report.get("error_type"),
                },
                ensure_ascii=False,
            )
        )
    if report.get("error_type"):
        raise SystemExit(1)


def main():
    args = arguments()
    manifest = load_manifest(args.manifest)
    if args.prepare:
        prepare(manifest, args.source_dir, args.bundle_dir, args.bundle_zip)
    if args.import_live:
        live_import(
            manifest,
            args.bundle_dir,
            args.report,
            args.base,
            args.confirm_database,
        )
    if not args.prepare and not args.import_live:
        print(
            json.dumps({"collection": manifest["collection"], "entries": len(manifest["entries"])})
        )


if __name__ == "__main__":
    main()
