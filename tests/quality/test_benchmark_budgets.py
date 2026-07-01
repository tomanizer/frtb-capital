from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import check_benchmark_budgets as budgets


def test_benchmark_budget_check_passes_within_thresholds(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    artifact_dir = repo_root / "dist" / "benchmarks"
    artifact_dir.mkdir(parents=True)
    _write_suite_artifacts(artifact_dir)

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


def test_benchmark_budget_check_reports_multiple_metric_breaches(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    artifact_dir = repo_root / "dist" / "benchmarks"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "benchmark.json").write_text(
        json.dumps({"summary": {"wall": 1.0, "too_high": 2.0, "too_low": 1.0}}),
        encoding="utf-8",
    )
    (repo_root / "docs" / "quality").mkdir(parents=True)
    (repo_root / "docs/quality/benchmark_budgets.toml").write_text(
        """
schema_version = 2
[[benchmarks]]
name = "multi-metric"
artifact = "dist/benchmarks/benchmark.json"
wall_clock_path = ["summary", "wall"]
wall_clock_seconds_max = 2.0

[[benchmarks.metrics]]
name = "too high"
path = ["summary", "too_high"]
max = 1.0

[[benchmarks.metrics]]
name = "too low"
path = ["summary", "too_low"]
min = 2.0
""".strip(),
        encoding="utf-8",
    )

    budget = budgets.load_budgets(root=repo_root)[0]

    errors = budgets.check_budget(budget, root=repo_root)

    assert len(errors) == 2
    assert "too_high" in errors[0]
    assert "too_low" in errors[1]


def test_benchmark_budget_check_reports_missing_required_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    artifact_dir = repo_root / "dist" / "benchmarks"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "benchmark.json").write_text(
        json.dumps({"summary": {"wall": 1.0}}),
        encoding="utf-8",
    )
    (repo_root / "docs" / "quality").mkdir(parents=True)
    (repo_root / "docs/quality/benchmark_budgets.toml").write_text(
        """
schema_version = 2
[[benchmarks]]
name = "required-path"
artifact = "dist/benchmarks/benchmark.json"
wall_clock_path = ["summary", "wall"]
wall_clock_seconds_max = 2.0

[[benchmarks.required_paths]]
name = "calculate phase"
path = ["summary", "calculate"]
""".strip(),
        encoding="utf-8",
    )

    budget = budgets.load_budgets(root=repo_root)[0]

    assert "required path calculate phase" in budgets.check_budget(budget, root=repo_root)[0]


def test_benchmark_budget_check_reports_path_equality_failure(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    artifact_dir = repo_root / "dist" / "benchmarks"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "benchmark.json").write_text(
        json.dumps({"summary": {"wall": 1.0, "row_hash": "a", "batch_hash": "b"}}),
        encoding="utf-8",
    )
    (repo_root / "docs" / "quality").mkdir(parents=True)
    (repo_root / "docs/quality/benchmark_budgets.toml").write_text(
        """
schema_version = 2
[[benchmarks]]
name = "hash-equality"
artifact = "dist/benchmarks/benchmark.json"
wall_clock_path = ["summary", "wall"]
wall_clock_seconds_max = 2.0

[[benchmarks.path_equalities]]
name = "row/batch hash"
left_path = ["summary", "batch_hash"]
right_path = ["summary", "row_hash"]
""".strip(),
        encoding="utf-8",
    )

    budget = budgets.load_budgets(root=repo_root)[0]

    assert (
        "path equality row/batch hash failed"
        in budgets.check_budget(
            budget,
            root=repo_root,
        )[0]
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_suite_artifacts(artifact_dir: Path) -> None:
    _write_json(
        artifact_dir / "frtb-ima-target-scale.json",
        {
            "totals": {"wall_clock_seconds": 70.0},
            "phase_timings": {
                "synthetic_input_generation": {"seconds": 1.0},
                "imcc_decomposition": {"seconds": 50.0},
                "audit_ndjson_serialization": {"seconds": 1.0},
            },
        },
    )
    _write_json(
        artifact_dir / "frtb-ima-arrow-batch.json",
        {
            "summary": {
                "timings_seconds": {
                    "parse": 1.0,
                    "adapt": 1.0,
                    "build": 1.0,
                    "calculate": 1.0,
                    "wall_clock": 5.0,
                },
                "accepted_row_dataclasses_materialized": 0,
                "materialized_dataclass_count": {
                    "scenario_metadata_arrow_batch_path": 0,
                    "rfet_observation_arrow_batch_path": 0,
                },
                "rfet_assessment_hash_delta": 0.0,
                "tracemalloc_peak_bytes": 100,
                "result_hashes": {
                    "rfet_batch_assessment": "hash",
                    "rfet_row_assessment": "hash",
                },
            },
        },
    )
    _write_json(
        artifact_dir / "frtb-sbm-batch-arrow.json",
        {
            "summary": {
                "timings_seconds": {
                    "wall_clock_proxy": 3.0,
                    "ingestion": 0.5,
                    "validation": 0.5,
                    "weighting": 1.0,
                    "audit_serialization": 0.25,
                },
                "materialized_dataclass_count": {"arrow_batch_path": 0},
                "accepted_row_dataclasses_materialized": 0,
                "pairwise_evidence_materialized_count": 0,
                "capital_delta_abs_max": 0.0,
                "peak_tracemalloc_bytes": {"arrow_batch_path": 100},
            },
        },
    )
    _write_json(
        artifact_dir / "frtb-drc-batch-arrow.json",
        {
            "summary": {
                "timings_seconds": {
                    "wall_clock": 4.0,
                    "arrow_table_construction": 0.5,
                    "arrow_normalization": 0.5,
                    "batch_construction": 0.5,
                    "batch_calculation": 1.0,
                },
                "materialized_dataclass_count": {
                    "arrow_batch_path": 0,
                    "non_securitisation_arrow_batch_path": 0,
                    "securitisation_non_ctp_arrow_batch_path": 0,
                    "ctp_arrow_batch_path": 0,
                },
                "capital": {
                    "absolute_delta": 0.0,
                    "absolute_delta_by_risk_class": {
                        "NON_SECURITISATION": 0.0,
                        "SECURITISATION_NON_CTP": 0.0,
                        "CORRELATION_TRADING_PORTFOLIO": 0.0,
                    },
                },
                "tracemalloc_peak_bytes": 100,
            },
        },
    )
    _write_json(
        artifact_dir / "frtb-rrao-target-scale.json",
        {
            "timings": {
                "wall_seconds": 40.0,
                "positions_per_second": 2500.0,
                "batch_positions_per_second": 3000.0,
                "arrow_positions_per_second": 3000.0,
                "arrow_table_seconds": 0.5,
                "arrow_batch_seconds": 0.5,
                "arrow_calculate_seconds": 1.0,
            },
            "memory": {"peak_traced_bytes": 100},
            "result": {
                "batch_accepted_row_dataclasses_materialized": 0,
                "arrow_accepted_row_dataclasses_materialized": 0,
                "batch_absolute_delta": 0.0,
                "arrow_absolute_delta": 0.0,
            },
        },
    )
    _write_json(
        artifact_dir / "frtb-cva-target-scale.json",
        {
            "summary": {
                "timings_seconds": {
                    "wall_clock": 5.0,
                    "parse": 0.5,
                    "adapt": 0.5,
                    "build": 0.5,
                    "calculate": 1.0,
                },
                "materialized_dataclass_count": {"arrow_batch_path": 0},
                "capital_delta_abs_max": 0.0,
                "tracemalloc_peak_bytes": 100,
            },
            "result": {
                "ba_arrow_input_hash_algorithm": "arrow-columnar-v2",
                "ba_arrow_payload_hash": "ba",
                "ba_arrow_input_hash_algorithm": "arrow-columnar-v2",
                "ba_row_payload_hash": "ba",
                "sa_arrow_input_hash_algorithm": "arrow-columnar-v2",
                "sa_arrow_payload_hash": "sa",
                "sa_arrow_input_hash_algorithm": "arrow-columnar-v2",
                "sa_row_payload_hash": "sa",
            },
        },
    )
