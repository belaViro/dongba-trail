"""Create an auditable thread-only checkpoint migration without overwriting source."""

import argparse
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import atomic_json, code_fingerprint, read_json, sha_file  # noqa: E402
from train import run_lock  # noqa: E402


def migrate(source, target, config_path):
    source, target = source.resolve(), target.resolve()
    config = read_json(config_path)
    with run_lock(source):
        if not (source / "STOP").exists():
            raise ValueError("Source run must be explicitly stopped")
        if read_json(source / "status.json")["phase"] != "stopped_resumable":
            raise ValueError("Source run is not stopped_resumable")
        if target.exists():
            raise FileExistsError("Migration target already exists")
        raw = (source / "last.pt").read_bytes()
        # This is our local checkpoint. Never use this utility with an untrusted pickle.
        checkpoint = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
        old_identity = checkpoint["identity"]
        changed = {
            key: (old_identity["config"].get(key), config.get(key))
            for key in set(old_identity["config"]) | set(config)
            if old_identity["config"].get(key) != config.get(key)
        }
        if changed != {"threads": (2, 8)}:
            raise ValueError(f"Only the approved threads 2->8 migration is allowed: {changed}")
        if old_identity["code_fingerprint"] != code_fingerprint():
            raise ValueError("Frozen src fingerprint changed")
        new_identity = {**old_identity, "config": config}
        checkpoint["identity"] = new_identity
        target.mkdir(parents=True)
        temporary = target / "last.pt.tmp"
        torch.save(checkpoint, temporary)
        os.replace(temporary, target / "last.pt")
        atomic_json(target / "identity.json", new_identity)
        atomic_json(target / "labels.json", checkpoint["labels"])
        atomic_json(
            target / "status.json",
            {
                "phase": "stopped_resumable",
                "epoch": checkpoint["progress"]["epoch"],
                "next_batch": checkpoint["progress"]["batch"],
                "migrated_from": str(source),
                "updated_at": datetime.now().astimezone().isoformat(),
            },
        )
        (target / "STOP").touch()
        report = {
            "created_at": datetime.now().astimezone().isoformat(),
            "source_run": str(source),
            "target_run": str(target),
            "source_checkpoint_sha256": sha_file(source / "last.pt"),
            "target_checkpoint_sha256": sha_file(target / "last.pt"),
            "source_identity": old_identity,
            "target_identity": new_identity,
            "changed_config": changed,
            "progress": checkpoint["progress"],
            "weights_optimizer_scheduler_rng_preserved": True,
            "warning": "Thread-only execution migration; no accuracy claim.",
        }
        atomic_json(target / "migration.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    migrate(args.source, args.target, args.config)
