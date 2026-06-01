from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import check_benchmark_budgets as budgets


def test_benchmark_budget_check_passes_within_thresholds(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    artifact_dir = repo_root / "dist" / "benchmarks"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "frtb-ima-target-scale.json").write_text(
        json.dumps(
            {
                "totals": {"wall_clock_seconds": 70.0},
                "phase_timings": {"imcc_decomposition": {"seconds": 50.0}},
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "frtb-sbm-batch-arrow.json").write_text(
        json.dumps(
            {
                "summary": {
                    "timings_seconds": {"wall_clock_proxy": 3.0},
                    "materialized_dataclass_count": {"arrow_batch_path": 0},
                },
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "frtb-rrao-target-scale.json").write_text(
        json.dumps(
            {
                "timings": {"wall_seconds": 40.0, "positions_per_second": 2500.0},
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "docs" / "quality").mkdir(parents=True)
    (repo_root / "docs" / "performance").mkdir(parents=True)
    (repo_root / "docs/performance/frtb-ima-target-scale-baseline.json").write_text(
        json.dumps({"totals": {"wall_clock_seconds": 80.0}}),
        encoding="utf-8",
    )
    (repo_root / "docs/performance/frtb-sbm-batch-arrow-baseline.json").write_text(
        json.dumps({"summary": {"timings_seconds": {"wall_clock_proxy": 1.0}}}),
        encoding="utf-8",
    )
    (repo_root / "docs/quality/benchmark_budgets.toml").write_text(
        (Path(__file__).resolve().parents[2] / "docs/quality/benchmark_budgets.toml").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(budgets, "ROOT", repo_root)
    monkeypatch.chdir(repo_root)

    assert budgets.main([]) == 0


def test_benchmark_budget_check_reports_missing_artifact(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "docs" / "quality").mkdir(parents=True)
    (repo_root / "docs/quality/benchmark_budgets.toml").write_text(
        """
schema_version = 1
[[benchmarks]]
name = "missing"
artifact = "dist/benchmarks/missing.json"
wall_clock_seconds_max = 1.0
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(budgets, "ROOT", repo_root)
    monkeypatch.chdir(repo_root)

    assert budgets.main([]) == 1


def test_benchmark_budget_check_reports_baseline_tolerance_breach(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    artifact_dir = repo_root / "dist" / "benchmarks"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "benchmark.json").write_text(
        json.dumps({"summary": {"seconds": 11.0}}),
        encoding="utf-8",
    )
    (repo_root / "docs" / "performance").mkdir(parents=True)
    (repo_root / "docs/performance/baseline.json").write_text(
        json.dumps({"summary": {"seconds": 5.0}}),
        encoding="utf-8",
    )
    (repo_root / "docs" / "quality").mkdir(parents=True)
    (repo_root / "docs/quality/benchmark_budgets.toml").write_text(
        """
schema_version = 1
[[benchmarks]]
name = "baseline-relative"
artifact = "dist/benchmarks/benchmark.json"
baseline_artifact = "docs/performance/baseline.json"
wall_clock_path = ["summary", "seconds"]
wall_clock_tolerance_multiplier = 2.0
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(budgets, "ROOT", repo_root)
    monkeypatch.chdir(repo_root)

    assert budgets.main([]) == 1
