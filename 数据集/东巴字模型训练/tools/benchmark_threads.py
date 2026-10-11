"""Read-only CPU thread sweep on identical train batches (AI-02 / D-085).

Kept outside src so the frozen trainer's identity does not change. Benchmark
weights are discarded; only the coordinator copies the paused source checkpoint.
"""

import argparse
import hashlib
import io
import json
import math
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import (  # noqa: E402
    atomic_json,
    code_fingerprint,
    read_json,
    sha_file,
    verified_manifest,
)
from health import inspect_model, probe_batch  # noqa: E402
from model import GlyphCNN  # noqa: E402
from train import run_lock, set_seed  # noqa: E402

from data import GlyphDataset, epoch_batches  # noqa: E402

HOME = Path(__file__).resolve().parents[1]


def choose_threads(trials, minimum_gain=1.05):
    """Require two healthy replicates and a material median throughput gain."""
    medians = {}
    for threads in (2, 4, 6, 8):
        rows = [row for row in trials if row["threads"] == threads]
        if len(rows) != 2 or not all(row["healthy"] for row in rows):
            continue
        rates = [row["samples_per_second"] for row in rows]
        if all(math.isfinite(rate) and rate > 0 for rate in rates):
            medians[threads] = statistics.median(rates)
    if 2 not in medians:
        raise ValueError("Two healthy baseline trials required")
    fastest = max(medians, key=medians.get)
    chosen = fastest if medians[fastest] >= medians[2] * minimum_gain else 2
    return {
        "selected_threads": chosen,
        "median_samples_per_second": medians,
        "gain_over_2_threads": medians[chosen] / medians[2],
        "minimum_gain": minimum_gain,
    }


def trial(snapshot, threads, warmup, steps, output):
    # Only load our own locally generated trusted snapshot; pickle is executable.
    raw = snapshot.read_bytes()
    checkpoint = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    identity = checkpoint["identity"]
    config = identity["config"]
    manifest = verified_manifest(HOME / "splits")
    if (
        identity["code_fingerprint"] != code_fingerprint()
        or identity["split_fingerprint"] != manifest["split_fingerprint"]
        or identity["torch"] != str(torch.__version__)
    ):
        raise ValueError("Frozen code/split/PyTorch identity changed")
    set_seed(config["seed"], threads)
    model = GlyphCNN(len(checkpoint["labels"]))
    model.load_state_dict(checkpoint["model"])
    model.train()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    optimizer.load_state_dict(checkpoint["optimizer"])
    dataset = GlyphDataset(
        manifest["dataset_root"], HOME / "splits/train.csv", True, config["seed"]
    )
    progress = checkpoint["progress"]
    dataset.epoch = progress["epoch"]
    batches = epoch_batches(
        len(dataset), config["batch_size"], config["seed"], dataset.epoch, progress["batch"]
    )
    loader = iter(
        torch.utils.data.DataLoader(
            dataset,
            batch_sampler=batches,
            num_workers=0,
            generator=torch.Generator().manual_seed(0),
        )
    )
    random.setstate(checkpoint["python_rng"])
    np.random.set_state(checkpoint["numpy_rng"])
    torch.set_rng_state(checkpoint["torch_rng"])
    samples, losses, data_seconds = 0, [], 0.0
    for step in range(warmup + steps):
        if step == warmup:
            start, cpu_start = time.perf_counter(), time.process_time()
        load_start = time.perf_counter()
        images, targets = next(loader)
        load_seconds = time.perf_counter() - load_start
        optimizer.zero_grad(set_to_none=True)
        loss = torch.nn.functional.cross_entropy(
            model(images), targets, label_smoothing=config["label_smoothing"]
        )
        if not torch.isfinite(loss):
            raise ValueError("Nonfinite benchmark loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            model.parameters(), config["gradient_clip_norm"], error_if_nonfinite=True
        )
        optimizer.step()
        if step >= warmup:
            samples += len(targets)
            losses.append(loss.item())
            data_seconds += load_seconds
    seconds, cpu_seconds = time.perf_counter() - start, time.process_time() - cpu_start
    plain = GlyphDataset(manifest["dataset_root"], HOME / "splits/train.csv")
    health = inspect_model(model, *probe_batch(plain, config["seed"]))
    report = {
        "threads": threads,
        "batch_size": config["batch_size"],
        "warmup_steps": warmup,
        "measured_steps": steps,
        "samples": samples,
        "seconds": seconds,
        "samples_per_second": samples / seconds,
        "data_seconds": data_seconds,
        "cpu_seconds": cpu_seconds,
        "average_cpu_cores_used": cpu_seconds / seconds,
        "mean_train_loss": statistics.mean(losses),
        "healthy": not health["collapsed"],
        "train_probe": health,
        "source_checkpoint_sha256": hashlib.sha256(raw).hexdigest(),
        "source_progress": progress,
        "source_identity": identity,
        "effective_threads": torch.get_num_threads(),
        "interop_threads": torch.get_num_interop_threads(),
        "benchmark_tool_sha256": sha_file(__file__),
        "warning": "Train speed only; no val/test/historical inference or saved weights.",
    }
    atomic_json(output, report)
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("threads", "samples_per_second", "average_cpu_cores_used", "healthy")
            }
        ),
        flush=True,
    )


def sweep(output, warmup, steps):
    output = output.resolve()
    if not output.is_relative_to((HOME / "reports").resolve()):
        raise ValueError("Output must stay inside training reports")
    run = HOME / "checkpoints/cpu_v2"
    with run_lock(run):
        if (
            not (run / "STOP").exists()
            or read_json(run / "status.json")["phase"] != "stopped_resumable"
        ):
            raise ValueError("Pause the full trainer first")
        identity = read_json(run / "identity.json")
        gate = read_json(HOME / "reports/cpu_v2_sanity.json")
        if not gate["passed"] or gate["identity"] != identity:
            raise ValueError("Original learning gate mismatch")
        output.mkdir(parents=True, exist_ok=False)
        snapshot = output / "source-last.pt"
        snapshot.write_bytes((run / "last.pt").read_bytes())
        for name in ("status.json", "identity.json", "health.json"):
            (output / ("source-" + name)).write_bytes((run / name).read_bytes())
        report = {
            "started_at": datetime.now().astimezone().isoformat(),
            "source_checkpoint_sha256": sha_file(snapshot),
            "trials": [],
            "order": [2, 4, 6, 8, 8, 6, 4, 2],
            "complete": False,
        }
        atomic_json(output / "summary.json", report)
        for number, threads in enumerate(report["order"]):
            destination = output / f"trial-{number + 1}-threads-{threads}.json"
            subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-u",
                    str(Path(__file__).resolve()),
                    "--snapshot",
                    str(snapshot),
                    "--threads",
                    str(threads),
                    "--warmup",
                    str(warmup),
                    "--steps",
                    str(steps),
                    "--output",
                    str(destination),
                ],
                check=True,
            )
            report["trials"].append(read_json(destination))
            atomic_json(output / "summary.json", report)
        if sha_file(run / "last.pt") != report["source_checkpoint_sha256"]:
            raise ValueError("Source checkpoint changed during sweep")
        report.update(choose_threads(report["trials"]))
        report.update(
            complete=True,
            finished_at=datetime.now().astimezone().isoformat(),
            source_checkpoint_unchanged=True,
        )
        atomic_json(output / "summary.json", report)
        print(json.dumps(choose_threads(report["trials"])), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--threads", type=int, choices=(2, 4, 6, 8))
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--steps", type=int, default=200)
    args = parser.parse_args()
    if args.warmup < 1 or args.steps < 1:
        parser.error("Positive warmup and steps required")
    if args.snapshot:
        if args.threads is None:
            parser.error("--snapshot requires --threads")
        trial(args.snapshot, args.threads, args.warmup, args.steps, args.output)
    else:
        sweep(args.output, args.warmup, args.steps)
