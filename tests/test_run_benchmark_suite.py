"""Tests for benchmark suite command dispatch."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_runner() -> ModuleType:
    if "run_benchmark_suite" in sys.modules:
        return sys.modules["run_benchmark_suite"]
    script_path = REPO_ROOT / "scripts" / "ci" / "run_benchmark_suite.py"
    spec = importlib.util.spec_from_file_location("run_benchmark_suite", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_benchmark_suite"] = module
    spec.loader.exec_module(module)
    return module


def test_default_benchmark_order_matches_budget_artifact_set() -> None:
    runner = load_runner()

    assert runner.DEFAULT_BENCHMARKS == (
        "ima-target-scale",
        "ima-arrow-batch",
        "sbm",
        "drc",
        "rrao",
        "cva",
    )


def test_main_runs_selected_benchmarks_with_environment(monkeypatch) -> None:
    runner = load_runner()
    calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def fake_run(args: tuple[str, ...], *, check: bool, env: dict[str, str]) -> None:
        calls.append((args, env))
        assert check is True

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.main(["ima-target-scale", "rrao"]) == 0

    assert calls[0][0] == (
        "uv",
        "run",
        "python",
        "scripts/benchmark_target_scale.py",
        "--output",
        "dist/benchmarks/frtb-ima-target-scale.json",
    )
    assert calls[1][0] == (
        "uv",
        "run",
        "python",
        "packages/frtb-rrao/scripts/benchmark_rrao_target_scale.py",
        "--output",
        "dist/benchmarks/frtb-rrao-target-scale.json",
    )
    assert calls[1][1]["PYTHONPATH"] == runner.os.pathsep.join(
        ("packages/frtb-common/src", "packages/frtb-rrao/src")
    )


def test_main_without_targets_runs_full_suite(monkeypatch) -> None:
    runner = load_runner()
    calls: list[tuple[str, ...]] = []

    def fake_run(args: tuple[str, ...], *, check: bool, env: dict[str, str]) -> None:
        calls.append(args)
        assert check is True
        assert env

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.main([]) == 0
    assert len(calls) == len(runner.DEFAULT_BENCHMARKS)
