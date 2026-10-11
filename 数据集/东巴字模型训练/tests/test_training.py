"""Synthetic fixtures verify mechanics, never real recognition accuracy."""

import csv
import json
import shutil

import numpy as np
import pytest
import torch
from audit import audit, image_hashes, split_unique
from common import atomic_json, normalized, read_json, verified_manifest
from evaluate import evaluate
from health import inspect_model
from model import GlyphCNN
from PIL import Image
from predict import predict
from train import run_lock, train

from data import GlyphDataset, epoch_batches, tensor_image


@pytest.fixture
def tiny_dataset(tmp_path):
    dataset, historical, splits = tmp_path / "DB1404", tmp_path / "historical", tmp_path / "splits"
    historical.mkdir()
    rng = np.random.default_rng(10)
    for number in range(1, 4):
        folder = dataset / f"{number:04d}"
        folder.mkdir(parents=True)
        for i in range(20):
            Image.fromarray(rng.integers(0, 256, (64, 64), dtype=np.uint8)).save(
                folder / f"{i}.jpg"
            )
    # Within-label duplicates removed; cross-label conflict quarantined globally.
    shutil.copyfile(dataset / "0001/0.jpg", dataset / "0001/duplicate.jpg")
    shutil.copyfile(dataset / "0001/1.jpg", dataset / "0002/conflict.jpg")
    shutil.copyfile(dataset / "0001/2.jpg", historical / "meaning1.jpg")
    (dataset / "0003/broken.jpg").write_bytes(b"not-an-image")
    catalog = tmp_path / "catalog.json"
    atomic_json(
        catalog,
        {"entries": [{"source_no": i, "name": f"meaning{i}", "aliases": []} for i in range(1, 4)]},
    )
    audit(dataset, catalog, historical, splits, seed=77)
    config = {
        "seed": 123,
        "threads": 1,
        "batch_size": 8,
        "epochs": 2,
        "patience": 8,
        "learning_rate": 0.001,
        "weight_decay": 0.0001,
        "label_smoothing": 0.05,
        "gradient_clip_norm": 5.0,
        "health_check_batches": 2,
        "checkpoint_seconds": 999999,
        "log_seconds": 999999,
    }
    return dataset, splits, config


def test_dedup_holdout_and_split(tiny_dataset):
    dataset, splits, _ = tiny_dataset
    groups = []
    for split in ("train", "val", "test"):
        with (splits / f"{split}.csv").open(encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert set(int(x["label"]) for x in rows) == {0, 1, 2}
        for row in rows:
            assert image_hashes(dataset / row["path"])[0] == row["file_sha256"]
        hashes = {image_hashes(dataset / row["path"])[3] for row in rows}
        assert len(rows) == len(hashes)
        groups.append(hashes)
    assert not groups[0] & groups[1] and not groups[0] & groups[2] and not groups[1] & groups[2]
    retained = set.union(*groups)
    assert image_hashes(dataset / "0001/1.jpg")[3] not in retained
    assert image_hashes(dataset / "0001/2.jpg")[3] not in retained
    report = read_json(splits / "audit_report.json")
    assert report["unreadable_images"] == 1
    assert report["excluded_groups"] == {"conflicting_labels": 1, "historical_overlap": 1}
    assert report["writer_independent"] is False


def test_split_is_reproducible():
    rows = [(str(i), 0, str(i), str(i)) for i in range(20)]
    assert split_unique(rows, 123) == split_unique(list(reversed(rows)), 123)
    with pytest.raises(ValueError):
        split_unique(rows[:2], 1)


def test_normalization_and_model():
    image = Image.new("L", (20, 40), 0)
    normalized_image = normalized(image)
    assert normalized_image.size == (64, 64)
    assert normalized_image.getpixel((0, 0)) == 255
    assert tensor_image(image).shape == (1, 64, 64)
    model = GlyphCNN(1404)
    assert sum(p.numel() for p in model.parameters()) < 1000000
    assert model(torch.zeros(2, 1, 64, 64)).shape == (2, 1404)


def test_batch_resume():
    full = list(epoch_batches(37, 8, 7, 2))
    resumed = list(epoch_batches(37, 8, 7, 2, start=2))
    assert resumed == full[2:]
    assert sorted(sum(full, [])) == list(range(37))


def test_concurrent_run_lock(tmp_path):
    with run_lock(tmp_path):
        with pytest.raises(OSError), run_lock(tmp_path):
            pass
    with run_lock(tmp_path):
        pass


def test_manifest_tampering_rejected(tiny_dataset):
    _, splits, _ = tiny_dataset
    verified_manifest(splits)
    with (splits / "train.csv").open("a", encoding="utf-8") as stream:
        stream.write("altered")
    with pytest.raises(ValueError, match="changed"):
        verified_manifest(splits)


def test_source_tampering_rejected(tiny_dataset):
    root, splits, _ = tiny_dataset
    dataset = GlyphDataset(root, splits / "train.csv")
    (root / dataset.rows[0]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed after audit"):
        dataset[0]


def test_resume_is_exact_and_evaluation_runs(tiny_dataset, tmp_path):
    _, splits, config = tiny_dataset
    uninterrupted, resumed = tmp_path / "full", tmp_path / "resumed"
    train(splits, config, uninterrupted)
    partial = train(splits, config, resumed, stop_after_steps=2)
    assert partial["batch"] == 2 and not partial["complete"]
    with pytest.raises(ValueError, match="incomplete"):
        evaluate(splits, resumed, tmp_path / "premature")
    train(splits, config, resumed, resume=True)
    full = torch.load(uninterrupted / "last.pt", weights_only=False)
    restored = torch.load(resumed / "last.pt", weights_only=False)
    assert full["progress"] == restored["progress"]
    for key in full["model"]:
        assert torch.equal(full["model"][key], restored["model"][key]), key
    report = evaluate(splits, resumed, tmp_path / "reports")
    assert report["test"]["count"] > 0
    assert report["historical_comparison"]["total"] == 1
    assert (tmp_path / "reports/东巴字模型评测.xlsx").exists()
    sample = next((tmp_path / "historical").glob("*.jpg"))
    assert len(predict(tmp_path / "reports/inference.pt", sample)) == 3


def test_no_overwrite_and_resume_identity(tiny_dataset, tmp_path):
    _, splits, config = tiny_dataset
    run = tmp_path / "run"
    train(splits, config, run, stop_after_steps=1)
    with pytest.raises(FileExistsError):
        train(splits, config, run)
    with pytest.raises(ValueError, match="Resume refused"):
        train(splits, {**config, "seed": 999}, run, resume=True)
    (run / "STOP").touch()
    with pytest.raises(RuntimeError, match="STOP"):
        train(splits, config, run, resume=True)
    assert json.loads((run / "status.json").read_text())["phase"] == "stopped_resumable"


def test_head_negative_inputs_keep_gradients():
    model = GlyphCNN(3)
    activation = model.classifier[3]
    inputs = torch.full((4, 128), -10.0, requires_grad=True)
    activation(inputs).sum().backward()
    assert torch.all(inputs.grad > 0)
    assert isinstance(model.classifier[2], torch.nn.LayerNorm)


def test_health_probe_detects_constant_logits_and_preserves_rng():
    model = GlyphCNN(3)
    images, targets = torch.rand(8, 1, 64, 64), torch.arange(8) % 3
    rng = torch.get_rng_state().clone()
    before = {key: value.clone() for key, value in model.state_dict().items()}
    stats = inspect_model(model, images, targets)
    assert not stats["collapsed"] and model.training
    assert torch.equal(rng, torch.get_rng_state())
    assert all(torch.equal(before[key], value) for key, value in model.state_dict().items())
    with torch.no_grad():
        model.classifier[-1].weight.zero_()
    assert inspect_model(model, images, targets)["collapsed"]


def test_health_guard_stops_training(tiny_dataset, tmp_path, monkeypatch):
    import train as trainer

    _, splits, config = tiny_dataset
    monkeypatch.setattr(trainer, "inspect_model", lambda *args: {"collapsed": True})
    run = tmp_path / "guard"
    with pytest.raises(RuntimeError, match="Constant"):
        train(splits, {**config, "health_check_batches": 1}, run)
    assert read_json(run / "status.json")["phase"] == "health_check_failed"
    assert (run / "collapse.pt").exists()


def test_learning_gate_rejects_failed_or_stale_reports(tmp_path, monkeypatch):
    import pipeline

    monkeypatch.setattr(pipeline, "HOME", tmp_path)
    monkeypatch.setattr(pipeline, "verified_manifest", lambda _: {"split_fingerprint": "split"})
    monkeypatch.setattr(pipeline, "code_fingerprint", lambda: "code")
    identity = {
        "config": {},
        "split_fingerprint": "split",
        "code_fingerprint": "code",
        "torch": str(torch.__version__),
    }
    path = tmp_path / "reports/cpu_v2_sanity.json"
    atomic_json(path, {"passed": False, "identity": identity})
    with pytest.raises(ValueError, match="gate"):
        pipeline.verify_learning_gate({})
    atomic_json(path, {"passed": True, "identity": identity})
    pipeline.verify_learning_gate({})
    with pytest.raises(ValueError, match="gate"):
        pipeline.verify_learning_gate({"changed": True})
