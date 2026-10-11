"""Train-only learning gates before full CPU v2 training; no test/val inference (AI-02)."""

import argparse
import math
import random
import time
from collections import defaultdict

import torch
from common import HOME, atomic_json, code_fingerprint, read_json, verified_manifest
from health import inspect_model, probe_batch
from model import GlyphCNN
from torch import nn
from torch.utils.data import DataLoader
from train import set_seed

from data import GlyphDataset, epoch_batches


def run(splits, config, output, overfit_steps=1200, stream_steps=2000):
    if output.exists():
        raise FileExistsError("Keep prior evidence; use a new --output")
    manifest = verified_manifest(splits)
    labels = read_json(splits / "labels.json")
    set_seed(config["seed"], config["threads"])
    plain = GlyphDataset(manifest["dataset_root"], splits / "train.csv")
    groups = defaultdict(list)
    for i, row in enumerate(plain.rows):
        groups[int(row["label"])].append(i)
    rng = random.Random(config["seed"])
    chosen = rng.sample(sorted(groups), min(32, len(groups)))
    indices = [i for label in chosen for i in rng.sample(groups[label], min(8, len(groups[label])))]
    samples = [plain[i] for i in indices]
    images = torch.stack([row[0] for row in samples])
    targets = torch.tensor([row[1] for row in samples])
    report = {
        "identity": {
            "code_fingerprint": code_fingerprint(),
            "split_fingerprint": manifest["split_fingerprint"],
            "config": config,
            "torch": str(torch.__version__),
        },
        "warning": "Both gates use train only. Memorization is NOT generalization accuracy.",
        "selected_train_paths": [plain.rows[i]["path"] for i in indices],
        "passed": False,
    }
    start = time.perf_counter()
    model = GlyphCNN(len(labels))
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    loss_fn = nn.CrossEntropyLoss(label_smoothing=config["label_smoothing"])
    history = []
    for step in range(overfit_steps):
        model.train()
        batch = torch.randperm(len(targets))[: config["batch_size"]]
        optimizer.zero_grad(set_to_none=True)
        loss = loss_fn(model(images[batch]), targets[batch])
        loss.backward()
        nn.utils.clip_grad_norm_(
            model.parameters(), config["gradient_clip_norm"], error_if_nonfinite=True
        )
        optimizer.step()
        if (step + 1) % 200 == 0 or step + 1 == overfit_steps:
            stats = inspect_model(model, images, targets)
            history.append({"step": step + 1, "loss": loss.item(), **stats})
            print({"gate": "memorization", **history[-1]}, flush=True)
    stats = inspect_model(model, images, targets)
    report["memorization"] = {
        "history": history,
        **stats,
        "passed": stats["training_probe_top1"] >= 0.95 and not stats["collapsed"],
    }
    atomic_json(output, report)
    if not report["memorization"]["passed"]:
        raise RuntimeError("Small-train memorization gate failed; do not launch full training")

    # Fresh initialization: do not carry the memorization model into this or the real run.
    set_seed(config["seed"], config["threads"])
    model = GlyphCNN(len(labels))
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    augmented = GlyphDataset(manifest["dataset_root"], splits / "train.csv", True, config["seed"])
    probe = probe_batch(plain, config["seed"])
    loader = DataLoader(
        augmented,
        batch_sampler=epoch_batches(len(augmented), config["batch_size"], config["seed"], 0),
        generator=torch.Generator().manual_seed(0),
    )
    losses, history = [], []
    for step, (x, y) in enumerate(loader, 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss = loss_fn(model(x), y)
        loss.backward()
        nn.utils.clip_grad_norm_(
            model.parameters(), config["gradient_clip_norm"], error_if_nonfinite=True
        )
        optimizer.step()
        losses.append(loss.item())
        if step % 200 == 0:
            stats = inspect_model(model, *probe)
            history.append(
                {"step": step, "mean_recent_loss": sum(losses[-200:]) / len(losses[-200:]), **stats}
            )
            print({"gate": "full_class_stream", **history[-1]}, flush=True)
        if step >= stream_steps:
            break
    stats = inspect_model(model, *probe)
    first, last = sum(losses[:200]) / len(losses[:200]), sum(losses[-200:]) / len(losses[-200:])
    report["full_class_stream"] = {
        "steps": len(losses),
        "history": history,
        "first_loss": first,
        "last_loss": last,
        **stats,
        "passed": math.isfinite(last)
        and last < first - 0.1
        and not stats["collapsed"]
        and stats["unique_predictions"] >= 2,
    }
    report["passed"] = report["memorization"]["passed"] and report["full_class_stream"]["passed"]
    report["seconds"] = time.perf_counter() - start
    atomic_json(output, report)
    if not report["passed"]:
        raise RuntimeError("Full-class streaming gate failed; do not launch full training")
    print({"passed": True, "seconds": report["seconds"], "report": str(output)}, flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=type(HOME), default=HOME / "reports/cpu_v2_sanity.json")
    args = parser.parse_args()
    run(HOME / "splits", read_json(HOME / "configs/cpu_v2.json"), args.output)
