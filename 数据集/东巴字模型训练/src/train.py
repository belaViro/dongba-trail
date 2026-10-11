"""Resumable CPU training. Only validation data selects best.pt (AI-02)."""

import argparse
import json
import math
import os
import random
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import torch
from common import HOME, atomic_json, code_fingerprint, read_json, verified_manifest
from health import inspect_model, probe_batch
from model import GlyphCNN
from torch import nn
from torch.utils.data import DataLoader

from data import GlyphDataset, epoch_batches


@contextmanager
def run_lock(directory):
    """OS lock releases on crash; an old file alone does not block resume."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "run.lock").open("a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def save_checkpoint(path, state):
    temporary = path.with_suffix(".pt.tmp")
    torch.save(state, temporary)
    os.replace(temporary, path)


def set_seed(seed, threads):
    torch.set_num_threads(threads)
    torch.use_deterministic_algorithms(True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def validation(model, dataset, batch_size, max_batches=None):
    model.eval()
    loss, top1, top5, count = 0.0, 0, 0, 0
    with torch.inference_mode():
        for step, (images, labels) in enumerate(DataLoader(dataset, batch_size=batch_size)):
            if max_batches is not None and step >= max_batches:
                break
            logits = model(images)
            loss += nn.functional.cross_entropy(logits, labels, reduction="sum").item()
            candidates = logits.topk(min(5, logits.shape[1]), dim=1).indices
            top1 += (candidates[:, 0] == labels).sum().item()
            top5 += (candidates == labels[:, None]).any(dim=1).sum().item()
            count += len(labels)
    if not count:
        raise ValueError("Empty validation dataset")
    return {"loss": loss / count, "top1": top1 / count, "top5": top5 / count, "count": count}


def benchmark(splits, config, steps, output):
    manifest = verified_manifest(splits)
    labels = read_json(splits / "labels.json")
    set_seed(config["seed"], config["threads"])
    dataset = GlyphDataset(manifest["dataset_root"], splits / "train.csv", True, config["seed"])
    model = GlyphCNN(len(labels))
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    loader = DataLoader(
        dataset, batch_sampler=epoch_batches(len(dataset), config["batch_size"], config["seed"], 0)
    )
    samples, measured_steps, start = 0, 0, None
    for index, (images, targets) in enumerate(loader):
        if index == 10:
            start = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        loss = nn.functional.cross_entropy(
            model(images), targets, label_smoothing=config["label_smoothing"]
        )
        loss.backward()
        if config.get("gradient_clip_norm"):
            nn.utils.clip_grad_norm_(
                model.parameters(), config["gradient_clip_norm"], error_if_nonfinite=True
            )
        optimizer.step()
        if index >= 10:
            samples += len(targets)
            measured_steps += 1
        if measured_steps >= steps:
            break
    if start is None or not samples:
        raise ValueError("Benchmark needs >10 batches")
    seconds = time.perf_counter() - start
    val = GlyphDataset(manifest["dataset_root"], splits / "val.csv")
    val_start = time.perf_counter()
    val_metrics = validation(model, val, config["batch_size"], 50)
    val_seconds = time.perf_counter() - val_start
    estimate = len(dataset) / (samples / seconds) + len(val) / (val_metrics["count"] / val_seconds)
    report = {
        "device": "cpu",
        "torch": torch.__version__,
        "threads": config["threads"],
        "batch_size": config["batch_size"],
        "parameters": sum(p.numel() for p in model.parameters()),
        "measured_steps": measured_steps,
        "seconds": seconds,
        "samples_per_second": samples / seconds,
        "estimated_epoch_seconds": estimate,
        "estimated_40_epochs_hours": estimate * 40 / 3600,
        "warning": (
            "Short pilot estimate; thermal throttling, checkpoint IO and other apps "
            "can slow full training. Not accuracy evidence."
        ),
        "split_fingerprint": manifest["split_fingerprint"],
        "code_fingerprint": code_fingerprint(),
    }
    atomic_json(output, report)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


def train(splits, config, run, resume=False, stop_after_steps=None):
    splits, run = Path(splits), Path(run)
    with run_lock(run):
        return train_locked(splits, config, run, resume, stop_after_steps)


def train_locked(splits, config, run, resume, stop_after_steps):
    if (run / "STOP").exists():
        raise RuntimeError("Remove STOP file before starting/resuming")
    manifest = verified_manifest(splits)
    labels = read_json(splits / "labels.json")
    set_seed(config["seed"], config["threads"])
    identity = {
        "config": config,
        "split_fingerprint": manifest["split_fingerprint"],
        "code_fingerprint": code_fingerprint(),
        "torch": str(torch.__version__),
    }
    model = GlyphCNN(len(labels))
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, config["epochs"])
    state = {
        "epoch": 0,
        "batch": 0,
        "best_top1": -1.0,
        "bad_epochs": 0,
        "train_loss_sum": 0.0,
        "train_count": 0,
        "history": [],
        "complete": False,
    }
    if resume:
        # Only load locally generated trusted checkpoints; pickle can execute code.
        checkpoint = torch.load(run / "last.pt", map_location="cpu", weights_only=False)
        if checkpoint["identity"] != identity:
            raise ValueError("Resume refused: code/config/split/PyTorch changed")
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scheduler.load_state_dict(checkpoint["scheduler"])
        state = checkpoint["progress"]
        random.setstate(checkpoint["python_rng"])
        np.random.set_state(checkpoint["numpy_rng"])
        torch.set_rng_state(checkpoint["torch_rng"])
    elif (run / "last.pt").exists() or (run / "identity.json").exists():
        raise FileExistsError("Existing run; use --resume or a new --run directory")
    atomic_json(run / "identity.json", identity)
    atomic_json(run / "labels.json", labels)
    training = GlyphDataset(manifest["dataset_root"], splits / "train.csv", True, config["seed"])
    val = GlyphDataset(manifest["dataset_root"], splits / "val.csv")
    loss_function = nn.CrossEntropyLoss(label_smoothing=config["label_smoothing"])
    health_interval = config.get("health_check_batches", 0)
    probe = None
    if health_interval:
        plain = GlyphDataset(manifest["dataset_root"], splits / "train.csv")
        probe = probe_batch(plain, config["seed"])
        del plain
    total_batches = math.ceil(len(training) / config["batch_size"])
    start, last_save, last_log, steps_this_run = time.monotonic(), 0.0, 0.0, 0

    def status(phase):
        atomic_json(
            run / "status.json",
            {
                "phase": phase,
                "pid": os.getpid(),
                "epoch": state["epoch"],
                "next_batch": state["batch"],
                "batches_per_epoch": total_batches,
                "best_validation_top1": (state["best_top1"] if state["best_top1"] >= 0 else None),
                "train_loss": (
                    state["train_loss_sum"] / state["train_count"] if state["train_count"] else None
                ),
                "elapsed_this_process_seconds": round(time.monotonic() - start, 1),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    def checkpoint(path):
        save_checkpoint(
            path,
            {
                "identity": identity,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "progress": state,
                "labels": labels,
                "python_rng": random.getstate(),
                "numpy_rng": np.random.get_state(),
                "torch_rng": torch.get_rng_state(),
            },
        )

    if not resume:
        checkpoint(run / "last.pt")
    while state["epoch"] < config["epochs"] and not state["complete"]:
        if (run / "STOP").exists():
            checkpoint(run / "last.pt")
            status("stopped_resumable")
            return state
        training.epoch = state["epoch"]
        model.train()
        # Dedicated generator prevents DataLoader initialization consuming dropout RNG on resume.
        loader = DataLoader(
            training,
            batch_sampler=epoch_batches(
                len(training), config["batch_size"], config["seed"], state["epoch"], state["batch"]
            ),
            generator=torch.Generator().manual_seed(0),
            num_workers=0,
        )
        for images, targets in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = loss_function(model(images), targets)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite loss; stopped without replacing last good checkpoint")
            loss.backward()
            if config.get("gradient_clip_norm"):
                nn.utils.clip_grad_norm_(
                    model.parameters(), config["gradient_clip_norm"], error_if_nonfinite=True
                )
            optimizer.step()
            state["batch"] += 1
            state["train_loss_sum"] += loss.item() * len(targets)
            state["train_count"] += len(targets)
            steps_this_run += 1
            if health_interval and state["batch"] % health_interval == 0:
                health = inspect_model(model, *probe)
                atomic_json(
                    run / "health.json",
                    {"epoch": state["epoch"] + 1, "batch": state["batch"], **health},
                )
                if health["collapsed"]:
                    checkpoint(run / "collapse.pt")
                    status("health_check_failed")
                    raise RuntimeError(
                        "Constant/non-finite model outputs on training probe; stopped"
                    )
            now = time.monotonic()
            if now - last_log >= config["log_seconds"]:
                status("training")
                print(
                    f"epoch={state['epoch'] + 1} batch={state['batch']}/{total_batches} "
                    f"loss={state['train_loss_sum'] / state['train_count']:.5f}",
                    flush=True,
                )
                last_log = now
            if now - last_save >= config["checkpoint_seconds"]:
                checkpoint(run / "last.pt")
                last_save = now
            if (run / "STOP").exists() or (stop_after_steps and steps_this_run >= stop_after_steps):
                checkpoint(run / "last.pt")
                status("stopped_resumable")
                return state
        status("validating")
        scores = validation(model, val, config["batch_size"])
        improved = scores["top1"] > state["best_top1"]
        if improved:
            state["best_top1"], state["bad_epochs"] = scores["top1"], 0
        else:
            state["bad_epochs"] += 1
        record = {
            "epoch": state["epoch"] + 1,
            "validation": scores,
            "train_loss": state["train_loss_sum"] / state["train_count"],
        }
        state["history"].append(record)
        state["epoch"] += 1
        state["batch"], state["train_loss_sum"], state["train_count"] = 0, 0.0, 0
        state["complete"] = (
            state["epoch"] >= config["epochs"] or state["bad_epochs"] >= config["patience"]
        )
        scheduler.step()
        if improved:
            checkpoint(run / "best.pt")
        checkpoint(run / "last.pt")
        atomic_json(run / "history.json", state["history"])
        print(json.dumps(record), flush=True)
    status("training_complete_evaluation_pending")
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", type=Path, default=HOME / "splits")
    parser.add_argument("--config", type=Path, default=HOME / "configs/cpu_v2.json")
    parser.add_argument("--run", type=Path, default=HOME / "checkpoints/cpu_v2")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--steps", type=int, default=100)
    args = parser.parse_args()
    config = read_json(args.config)
    if args.benchmark:
        benchmark(args.splits, config, args.steps, HOME / "reports/cpu_v2_benchmark.json")
    else:
        train(args.splits, config, args.run, args.resume)
