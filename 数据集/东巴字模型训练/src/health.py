"""Training-only collapse diagnostics; never a generalization accuracy claim (AI-02)."""

import random

import torch


def probe_batch(dataset, seed, count=128):
    indices = random.Random(seed).sample(range(len(dataset)), min(count, len(dataset)))
    rows = [dataset[index] for index in indices]
    return torch.stack([row[0] for row in rows]), torch.tensor([row[1] for row in rows])


def inspect_model(model, images, targets):
    """No dropout/RNG or BatchNorm updates; restore the caller's training mode."""
    was_training = model.training
    model.eval()
    try:
        with torch.inference_mode():
            hidden = model.classifier[:-2](model.features(images))
            logits = model.classifier[-1](hidden)
            finite = bool(torch.isfinite(logits).all() and torch.isfinite(hidden).all())
            spread = float((logits.max(0).values - logits.min(0).values).max())
            return {
                "samples": len(targets),
                "finite": finite,
                "hidden_zero_fraction": float((hidden == 0).float().mean()),
                "max_logit_sample_range": spread,
                "unique_predictions": int(logits.argmax(1).unique().numel()),
                "training_probe_top1": float((logits.argmax(1) == targets).float().mean()),
                "collapsed": not finite or spread <= 1e-8,
                "warning": "Training-split diagnostic only, not validation/test accuracy.",
            }
    finally:
        model.train(was_training)
