"""Resume an approved thread-only migration, then evaluate the selected best model."""

import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import HOME, atomic_json, code_fingerprint, read_json, verified_manifest  # noqa: E402
from evaluate import evaluate  # noqa: E402
from train import train  # noqa: E402


def verify(run, config):
    migration = read_json(run / "migration.json")
    identity = read_json(run / "identity.json")
    if migration["target_identity"] != identity:
        raise ValueError("Migration identity mismatch")
    if identity["config"] != config or identity["code_fingerprint"] != code_fingerprint():
        raise ValueError("Current config or source no longer matches migration")
    if identity["split_fingerprint"] != verified_manifest(HOME / "splits")["split_fingerprint"]:
        raise ValueError("Split identity no longer matches migration")
    if migration["changed_config"] != {"threads": [2, 8]}:
        raise ValueError("Migration was not the approved threads-only change")


if __name__ == "__main__":
    run = HOME / "checkpoints/cpu_v2_threads8"
    config = read_json(HOME / "configs/cpu_v2_threads8.json")
    try:
        verify(run, config)
        state = train(HOME / "splits", config, run, resume=True)
        if state["complete"] and not (run / "STOP").exists():
            evaluate(HOME / "splits", run, HOME / "reports/cpu_v2_threads8")
    except Exception as exc:
        atomic_json(
            HOME / "logs" / f"failure-{os.getpid()}.json",
            {
                "error_type": type(exc).__name__,
                "message": str(exc),
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        traceback.print_exc()
        raise SystemExit(1) from exc
