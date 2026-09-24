"""Logical MySQL and media backup; restore only into an empty migrated database."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import delete, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.business.database import Database  # noqa: E402
from backend.app.business.models import Base, Setting  # noqa: E402
from backend.app.config import Settings  # noqa: E402
from backend.app.media import ASSET_NAME  # noqa: E402


def capture(database):
    if database.engine.dialect.name != "mysql":
        raise ValueError("Backup requires MySQL")
    with database.engine.connect().execution_options(
        isolation_level="REPEATABLE READ"
    ) as connection:
        with connection.begin():
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            records = {
                table.name: [dict(row) for row in connection.execute(select(table)).mappings()]
                for table in Base.metadata.sorted_tables
            }
    return {
        "format": 1,
        "revision": version,
        "created_at": datetime.now(UTC).isoformat(),
        "tables": records,
    }


def backup(database, media_directory: Path, output: Path):
    snapshot = capture(database)
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
    hashes = {"database.json": hashlib.sha256(payload).hexdigest()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        archive.writestr("database.json", payload)
        for path in sorted(media_directory.glob("*")):
            name = path.name.removesuffix(".json")
            if path.is_file() and ASSET_NAME.fullmatch(name):
                data = path.read_bytes()
                relative = f"media/{path.name}"
                archive.writestr(relative, data)
                hashes[relative] = hashlib.sha256(data).hexdigest()
        archive.writestr("checksums.json", json.dumps(hashes, sort_keys=True))
    return {
        "tables": len(snapshot["tables"]),
        "rows": sum(map(len, snapshot["tables"].values())),
        "media_files": len(hashes) - 1,
    }


def restore(database, media_directory: Path, source: Path):
    if database.engine.dialect.name != "mysql":
        raise ValueError("Restore requires MySQL")
    with ZipFile(source) as archive:
        hashes = json.loads(archive.read("checksums.json"))
        if set(archive.namelist()) != {*hashes, "checksums.json"}:
            raise ValueError("Unexpected backup archive entries")
        files = {}
        for name, checksum in hashes.items():
            if name != "database.json":
                filename = name.removeprefix("media/")
                if not name.startswith("media/") or not ASSET_NAME.fullmatch(
                    filename.removesuffix(".json")
                ):
                    raise ValueError("Invalid media path in archive")
            content = archive.read(name)
            if hashlib.sha256(content).hexdigest() != checksum:
                raise ValueError("Backup checksum mismatch")
            files[name] = content
    snapshot = json.loads(files.pop("database.json"))
    tables = Base.metadata.sorted_tables
    if snapshot.get("format") != 1 or set(snapshot["tables"]) != {table.name for table in tables}:
        raise ValueError("Incompatible backup format")
    if media_directory.exists() and any(media_directory.iterdir()):
        raise ValueError("Restore media directory must be empty")
    with database.engine.begin() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if revision != snapshot["revision"]:
            raise ValueError("Migrate empty target to the backup revision before restore")
        for table in tables:
            rows = connection.execute(select(table).limit(2)).mappings().all()
            if table.name == "settings":
                rows = [
                    row
                    for row in rows
                    if row["key"] != "setup" or row["value"] != {"complete": False}
                ]
            if rows:
                raise ValueError("Refusing to overwrite a non-empty database")
        connection.execute(delete(Setting))
        for table in tables:
            records = snapshot["tables"][table.name]
            if records:
                connection.execute(table.insert(), records)
        media_directory.mkdir(parents=True, exist_ok=True)
        try:
            for name, data in files.items():
                (media_directory / name.removeprefix("media/")).write_bytes(data)
        except OSError:
            for name in files:
                (media_directory / name.removeprefix("media/")).unlink(missing_ok=True)
            raise
    return {
        "tables": len(tables),
        "rows": sum(map(len, snapshot["tables"].values())),
        "media_files": len(files),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backup", "restore"))
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    settings = Settings()
    database = Database(settings.database_url)
    try:
        operation = backup if args.action == "backup" else restore
        print(json.dumps(operation(database, settings.media_directory, args.archive)))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    finally:
        database.engine.dispose()
