"""Train/resume then evaluate once, entirely offline."""

import argparse
import os
import time
import traceback

import torch
from common import HOME, atomic_json, code_fingerprint, read_json, verified_manifest
from evaluate import evaluate
from train import train


def verify_learning_gate(config):
    report = read_json(HOME / "reports/cpu_v2_sanity.json")
    expected = {
        "config": config,
        "code_fingerprint": code_fingerprint(),
        "split_fingerprint": verified_manifest(HOME / "splits")["split_fingerprint"],
        "torch": str(torch.__version__),
    }
    if not report.get("passed") or report["identity"] != expected:
        raise ValueError(
            "Learning gate missing/failed/stale; run sanity.py with this exact code/config"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    run = HOME / "checkpoints/cpu_v2"
    try:
        config = read_json(HOME / "configs/cpu_v2.json")
        verify_learning_gate(config)
        state = train(HOME / "splits", config, run, args.resume)
        if state["complete"] and not (run / "STOP").exists():
            evaluate(HOME / "splits", run, HOME / "reports/cpu_v2")
    except Exception as exc:
        # A duplicate process must not overwrite the status of the active trainer.
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
