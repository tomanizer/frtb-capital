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
    (artifact_dir / "frtb-rrao-target-scale.json").write_text(
        json.dumps(
            {
                "timings": {"wall_seconds": 40.0, "positions_per_second": 2500.0},
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "docs" / "quality").mkdir(parents=True)
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
