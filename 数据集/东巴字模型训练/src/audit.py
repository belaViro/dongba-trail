"""Stream DB1404; quarantine conflicting duplicates; split before augmentation."""

import argparse
import csv
import hashlib
import io
import random
import sqlite3
import time
from collections import Counter
from pathlib import Path

from common import HOME, PROJECT, atomic_json, fingerprint, normalized, read_json, sha_file
from PIL import Image


def image_hashes(path):
    content = path.read_bytes()
    with Image.open(io.BytesIO(content)) as image:
        image.load()
        size, mode = image.size, image.mode
        gray = image.convert("L")
        raw = hashlib.sha256(str(gray.size).encode() + gray.tobytes()).hexdigest()
        small = normalized(image)
        group = hashlib.sha256(small.tobytes()).hexdigest()
        coarse = hashlib.sha256(
            small.resize((16, 16), Image.Resampling.BILINEAR).tobytes()
        ).hexdigest()
    return hashlib.sha256(content).hexdigest(), raw, group, coarse, size, mode


def split_unique(rows, seed):
    """Rows are unique retained groups within ONE class, not writer identities."""
    rows = sorted(rows)
    if len(rows) < 10:
        raise ValueError("Fewer than 10 retained groups in a class; manual audit required")
    random.Random(seed).shuffle(rows)
    count = max(1, round(len(rows) * 0.1))
    return {"test": rows[:count], "val": rows[count : 2 * count], "train": rows[2 * count :]}


def audit(dataset, catalog, historical, output, seed=20261008):
    dataset, historical, output = Path(dataset).resolve(), Path(historical).resolve(), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        raise FileExistsError("Completed split already exists; use a new output directory")
    entries = read_json(catalog)["entries"]
    labels = [
        {
            "class_id": f"{entry['source_no']:04d}",
            "label": i,
            "name": entry["name"],
            "aliases": entry.get("aliases", []),
        }
        for i, entry in enumerate(sorted(entries, key=lambda x: x["source_no"]))
    ]
    folders = sorted(p.name for p in dataset.iterdir() if p.is_dir())
    if folders != [item["class_id"] for item in labels]:
        raise ValueError("Dataset directories and catalog IDs differ")
    images = sorted(p for p in historical.iterdir() if p.suffix.lower() in {".jpg", ".png"})
    if not images:
        raise ValueError("Historical holdout directory is empty")
    held = {p.name: image_hashes(p) for p in images}
    config = {
        "dataset_root": str(dataset),
        "catalog_sha256": sha_file(catalog),
        "historical": {k: v[0] for k, v in held.items()},
        "seed": seed,
        "audit_version": 1,
    }
    config_path = output / "audit_config.json"
    if config_path.exists() and read_json(config_path) != config:
        raise ValueError("Partial audit configuration differs; choose a new output directory")
    atomic_json(config_path, config)
    db = sqlite3.connect(output / "audit.sqlite3")
    db.execute("CREATE TABLE IF NOT EXISTS done (class_id TEXT PRIMARY KEY, signature TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS images (
        path TEXT PRIMARY KEY, label INTEGER, file_sha TEXT, pixel_sha TEXT,
        group_sha TEXT, coarse_sha TEXT, width INTEGER, height INTEGER, mode TEXT)""")
    db.execute("CREATE TABLE IF NOT EXISTS errors (path TEXT, error TEXT)")
    started = time.monotonic()
    for item in labels:
        paths = sorted((dataset / item["class_id"]).glob("*.jpg"))
        if not paths:
            raise ValueError(f"No JPEGs: {item['class_id']}")
        signature = fingerprint([(p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in paths])
        old = db.execute(
            "SELECT signature FROM done WHERE class_id=?", (item["class_id"],)
        ).fetchone()
        if old:
            if old[0] != signature:
                raise ValueError("Source images changed during partial audit")
            continue
        with db:
            for path in paths:
                relative = path.relative_to(dataset).as_posix()
                try:
                    file_sha, pixel_sha, group_sha, coarse_sha, size, mode = image_hashes(path)
                    db.execute(
                        "INSERT INTO images VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            relative,
                            item["label"],
                            file_sha,
                            pixel_sha,
                            group_sha,
                            coarse_sha,
                            *size,
                            mode,
                        ),
                    )
                except (OSError, ValueError) as exc:
                    db.execute("INSERT INTO errors VALUES (?,?)", (relative, type(exc).__name__))
            db.execute("INSERT INTO done VALUES (?,?)", (item["class_id"], signature))
        if (item["label"] + 1) % 25 == 0:
            progress = {
                "classes_done": item["label"] + 1,
                "classes_total": len(labels),
                "elapsed_seconds": round(time.monotonic() - started, 1),
            }
            atomic_json(output / "audit_progress.json", progress)
            print(progress, flush=True)
    for column in ("group_sha", "coarse_sha", "label"):
        db.execute(f"CREATE INDEX IF NOT EXISTS ix_{column} ON images ({column})")
    db.execute("CREATE TABLE IF NOT EXISTS excluded (group_sha TEXT PRIMARY KEY, reason TEXT)")
    db.execute("DELETE FROM excluded")
    db.execute("""INSERT INTO excluded SELECT group_sha, 'conflicting_labels' FROM images
        GROUP BY group_sha HAVING count(DISTINCT label)>1""")
    db.execute("""INSERT OR IGNORE INTO excluded
        SELECT group_sha, 'coarse_conflicting_labels' FROM images WHERE coarse_sha IN
        (SELECT coarse_sha FROM images GROUP BY coarse_sha HAVING count(DISTINCT label)>1)""")
    for hashes in held.values():
        db.execute(
            """INSERT OR IGNORE INTO excluded SELECT group_sha, 'historical_overlap'
            FROM images WHERE group_sha=? OR coarse_sha=?""",
            (hashes[2], hashes[3]),
        )
    db.commit()
    fields = ["path", "label", "pixel_sha256", "file_sha256"]
    streams = {
        s: (output / f"{s}.csv").open("w", newline="", encoding="utf-8")
        for s in ("train", "val", "test")
    }
    writers = {s: csv.writer(f) for s, f in streams.items()}
    for writer in writers.values():
        writer.writerow(fields)
    counts = Counter()
    class_counts = []
    try:
        for item in labels:
            rows = db.execute(
                """SELECT min(path), label, pixel_sha, file_sha FROM images
                WHERE label=? AND group_sha NOT IN (SELECT group_sha FROM excluded)
                GROUP BY coarse_sha""",
                (item["label"],),
            ).fetchall()
            portions = split_unique(rows, seed + item["label"])
            per_class = {"class_id": item["class_id"]}
            for split, values in portions.items():
                writers[split].writerows(values)
                counts[split] += len(values)
                per_class[split] = len(values)
            class_counts.append(per_class)
    finally:
        for stream in streams.values():
            stream.close()
    with (output / "excluded.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["path", "label", "reason"])
        writer.writerows(
            db.execute("""SELECT path,label,reason FROM images
            JOIN excluded USING(group_sha) ORDER BY path""")
        )
    with (output / "unreadable.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["path", "error"])
        writer.writerows(db.execute("SELECT * FROM errors"))
    suspicious = db.execute("""SELECT coarse_sha, min(path), max(path), count(*) FROM images
        GROUP BY coarse_sha HAVING count(DISTINCT group_sha)>1 LIMIT 1000""").fetchall()
    stats = {
        "classes": len(labels),
        "readable_images": db.execute("SELECT count(*) FROM images").fetchone()[0],
        "unreadable_images": db.execute("SELECT count(*) FROM errors").fetchone()[0],
        "unique_file_hashes": db.execute("SELECT count(DISTINCT file_sha) FROM images").fetchone()[
            0
        ],
        "unique_pixel_hashes": db.execute(
            "SELECT count(DISTINCT pixel_sha) FROM images"
        ).fetchone()[0],
        "unique_normalized_hashes": db.execute(
            "SELECT count(DISTINCT group_sha) FROM images"
        ).fetchone()[0],
        "excluded_groups": dict(db.execute("SELECT reason,count(*) FROM excluded GROUP BY reason")),
        "sizes_modes": list(
            db.execute("SELECT width,height,mode,count(*) FROM images GROUP BY width,height,mode")
        ),
        "split_counts": dict(counts),
        "historical_count": len(held),
        "suspicious_coarse_collisions_first_1000": suspicious,
        "writer_independent": False,
        "limitations": (
            "No verified writer metadata. Suffix is not a writer ID. "
            "Exact pixel and identical 16x16 thumbnail grouping; other near-duplicates may remain."
        ),
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
    atomic_json(output / "labels.json", labels)
    atomic_json(output / "class_counts.json", class_counts)
    atomic_json(output / "audit_report.json", stats)
    atomic_json(
        output / "split_algorithm.json",
        {
            "version": 2,
            "retained_group": "identical_16x16_bilinear_grayscale_thumbnail",
            "policy": "one representative per group; conflicting labels quarantined, not relabeled",
        },
    )
    digests = {
        name: sha_file(output / name)
        for name in (
            "train.csv",
            "val.csv",
            "test.csv",
            "labels.json",
            "audit_config.json",
            "split_algorithm.json",
        )
    }
    atomic_json(
        output / "manifest.json",
        {
            **config,
            "fingerprints": digests,
            "split_fingerprint": fingerprint(digests),
            "counts": dict(counts),
            "writer_independent": False,
            "historical_directory": str(historical),
        },
    )
    db.close()
    print(
        {k: v for k, v in stats.items() if k != "suspicious_coarse_collisions_first_1000"},
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=HOME.parent / "DB1404")
    parser.add_argument("--catalog", type=Path, default=PROJECT / "data/db1404_full.json")
    parser.add_argument("--historical", type=Path, default=PROJECT / "东巴字图片_按中文含义命名")
    parser.add_argument("--output", type=Path, default=HOME / "splits")
    args = parser.parse_args()
    audit(args.dataset, args.catalog, args.historical, args.output)
