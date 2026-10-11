"""Selection mechanics only, not CPU speed or recognition evidence (AI-02)."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "thread_benchmark", Path(__file__).resolve().parents[1] / "tools/benchmark_threads.py"
)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def rows(threads, rate, healthy=True):
    return [{"threads": threads, "samples_per_second": rate, "healthy": healthy}] * 2


def test_keeps_baseline_without_material_gain():
    assert benchmark.choose_threads(rows(2, 100) + rows(4, 104))["selected_threads"] == 2


def test_chooses_healthy_measurably_faster_setting():
    result = benchmark.choose_threads(rows(2, 100) + rows(4, 120) + rows(8, 150, False))
    assert result["selected_threads"] == 4
    assert result["gain_over_2_threads"] == pytest.approx(1.2)


def test_requires_two_healthy_baselines_and_rejects_nan():
    with pytest.raises(ValueError, match="baseline"):
        benchmark.choose_threads(rows(2, 100, False))
    result = benchmark.choose_threads(rows(2, 100) + rows(4, float("nan")))
    assert result["selected_threads"] == 2
