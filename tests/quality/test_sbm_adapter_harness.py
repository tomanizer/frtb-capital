from __future__ import annotations

import importlib.util
import math
import sys
import tracemalloc
from pathlib import Path
from types import ModuleType

import pytest


def _load_harness() -> ModuleType:
    module_name = "sbm_adapter_harness_for_test"
    module_path = Path(__file__).parents[2] / "benchmarks" / "sbm_adapter_harness.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_traced_peak_bytes_stops_tracing_on_exception() -> None:
    harness = _load_harness()

    def fail() -> None:
        raise RuntimeError("boom")

    was_tracing = tracemalloc.is_tracing()
    with pytest.raises(RuntimeError, match="boom"):
        harness._traced_peak_bytes(fail)

    if not was_tracing:
        assert not tracemalloc.is_tracing()


@pytest.mark.parametrize(
    ("row_total", "batch_total"),
    ((math.nan, 1.0), (1.0, math.nan), (math.inf, 1.0), (1.0, -math.inf)),
)
def test_matching_capital_delta_rejects_non_finite_totals(
    row_total: float,
    batch_total: float,
) -> None:
    harness = _load_harness()

    with pytest.raises(RuntimeError, match="must be finite"):
        harness._matching_capital_delta(
            label="case",
            row_total=row_total,
            batch_total=batch_total,
        )


def test_matching_capital_delta_rejects_divergent_finite_totals() -> None:
    harness = _load_harness()

    assert harness._matching_capital_delta(
        label="case",
        row_total=10.0,
        batch_total=10.0 + 5e-10,
    ) == pytest.approx(5e-10)
    with pytest.raises(RuntimeError, match="diverged"):
        harness._matching_capital_delta(
            label="case",
            row_total=10.0,
            batch_total=10.0 + 2e-9,
        )


def test_summary_exposes_budgetable_split_metrics_and_hashes() -> None:
    harness = _load_harness()
    cases = (
        {
            "label": "case",
            "raw_row_count": 10,
            "regulatory_factor_count": 4,
            "row_compatibility_path": {
                "materialized_dataclass_count": 10,
                "timings_seconds": {"row_dataclass_construction": 0.1},
                "result_hash": "r" * 64,
                "audit_hash": "a" * 64,
                "pairwise_evidence": {
                    "total_count": 6,
                    "materialized_count": 0,
                    "omitted_count": 6,
                },
                "tracemalloc_peak_bytes": 100,
            },
            "arrow_batch_path": {
                "accepted_row_dataclasses_materialized": 0,
                "timings_seconds": {
                    "synthetic_arrow_table_construction": 0.1,
                    "handoff_normalization": 0.2,
                    "batch_construction": 0.3,
                    "weighting_factor_grid_aggregation_and_result": 0.4,
                    "audit_result_materialization": 0.5,
                },
                "result_hash": "b" * 64,
                "audit_hash": "c" * 64,
                "pairwise_evidence": {
                    "total_count": 6,
                    "materialized_count": 0,
                    "omitted_count": 6,
                },
                "tracemalloc_peak_bytes": 80,
            },
        },
    )
    phase_probes = (
        {
            "timings_seconds": {
                "netting_factor_grid_and_correlation_matrix": 0.6,
                "correlation_scenario_aggregation": 0.7,
            }
        },
    )

    summary = harness._summary(cases, phase_probes)

    assert summary["raw_row_count"] == 10
    assert summary["netted_factor_count"] == 4
    assert summary["pairwise_evidence_count"] == 6
    assert summary["pairwise_evidence_materialized_count"] == 0
    assert summary["accepted_row_dataclasses_materialized"] == 0
    assert summary["accepted_row_dataclasses_avoided"] is True
    assert summary["materialized_dataclass_count"]["row_compatibility_path"] == 10
    assert summary["timings_seconds"]["ingestion"] == pytest.approx(0.1)
    assert summary["timings_seconds"]["validation"] == pytest.approx(0.5)
    assert summary["timings_seconds"]["weighting"] == pytest.approx(0.4)
    assert summary["timings_seconds"]["netting_factor_grid"] == pytest.approx(0.6)
    assert summary["timings_seconds"]["correlation_scenario_aggregation"] == pytest.approx(0.7)
    assert summary["timings_seconds"]["audit_serialization"] == pytest.approx(0.5)
    assert summary["timings_seconds"]["wall_clock_proxy"] == pytest.approx(2.8)
    assert len(summary["result_hash"]) == 64
    assert len(summary["audit_hash"]) == 64


def test_summary_validation_reports_missing_mapping_key() -> None:
    harness = _load_harness()

    with pytest.raises(ValueError, match="missing required benchmark key"):
        harness._required_mapping({}, "timings_seconds")


def test_phase_probe_timings_reports_missing_timing_key() -> None:
    harness = _load_harness()

    with pytest.raises(ValueError, match="missing required phase-probe timing key"):
        harness._phase_probe_timings(({"timings_seconds": {}},))


def test_result_hash_reports_missing_required_key() -> None:
    harness = _load_harness()

    with pytest.raises(ValueError, match="missing required result-hash key"):
        harness._result_hash({"total_capital": 1.0})
