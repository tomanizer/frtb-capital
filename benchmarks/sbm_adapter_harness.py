"""Benchmark migrated SBM row, Arrow handoff, and package batch paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
import tracemalloc
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
from frtb_common import NormalizedTabularHandoff
from frtb_sbm import (
    SbmCalculationContext,
    SbmCapitalResult,
    SbmPairwiseEvidenceMode,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRunControls,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmSensitivityBatch,
    SbmSignConvention,
    SbmSourceLineage,
    WeightedSensitivity,
    calculate_sbm_capital,
    calculate_sbm_capital_from_commodity_delta_batch,
    calculate_sbm_capital_from_csr_nonsec_delta_batch,
    calculate_sbm_capital_from_csr_sec_ctp_delta_batch,
    calculate_sbm_capital_from_csr_sec_nonctp_delta_batch,
    calculate_sbm_capital_from_equity_delta_batch,
    calculate_sbm_capital_from_fx_delta_batch,
    calculate_sbm_capital_from_girr_vega_batch,
    curvature_worst_branch,
    select_girr_curvature_branches_from_batch,
    serialize_sbm_result,
    validate_curvature_sensitivities,
)
from frtb_sbm.aggregation import adjust_correlation_matrix_for_scenario
from frtb_sbm.arrow_handoff import (
    build_commodity_delta_batch_from_handoff,
    build_csr_nonsec_delta_batch_from_handoff,
    build_csr_sec_ctp_delta_batch_from_handoff,
    build_csr_sec_nonctp_delta_batch_from_handoff,
    build_equity_delta_batch_from_handoff,
    build_fx_delta_batch_from_handoff,
    build_girr_curvature_batch_from_handoff,
    build_girr_vega_batch_from_handoff,
    normalize_commodity_delta_arrow_table,
    normalize_csr_nonsec_delta_arrow_table,
    normalize_csr_sec_ctp_delta_arrow_table,
    normalize_csr_sec_nonctp_delta_arrow_table,
    normalize_equity_delta_arrow_table,
    normalize_fx_delta_arrow_table,
    normalize_girr_curvature_arrow_table,
    normalize_girr_vega_arrow_table,
)
from frtb_sbm.capital import _build_girr_delta_intra_bucket_correlation_matrix

DEFAULT_OUTPUT = Path("dist/benchmarks/frtb-sbm-batch-arrow.json")
DEFAULT_ROW_COUNT = 720

TimedValue = tuple[Any, float]
TracedValue = tuple[Any, int]


@dataclass(frozen=True)
class CapitalPathSpec:
    label: str
    row_factory: Callable[[int], SbmSensitivity]
    table_factory: Callable[[int], pa.Table]
    normalize: Callable[[pa.Table], NormalizedTabularHandoff]
    build_batch: Callable[[NormalizedTabularHandoff], SbmSensitivityBatch]
    calculate_batch: Callable[..., SbmCapitalResult]
    factor_axes: tuple[str, ...]
    desk_id: str


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSON output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--row-count",
        type=int,
        default=DEFAULT_ROW_COUNT,
        help=f"Synthetic rows per path. Default: {DEFAULT_ROW_COUNT}",
    )
    args = parser.parse_args()
    if args.row_count <= 0:
        parser.error("--row-count must be positive")

    report = build_report(row_count=args.row_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    sys.stdout.write(f"wrote {args.output}\n")


def build_report(*, row_count: int) -> dict[str, object]:
    cases = [
        _run_capital_case(spec, row_count=row_count)
        for spec in (
            _girr_vega_spec(),
            _fx_delta_spec(),
            _equity_delta_spec(),
            _commodity_delta_spec(),
            _csr_nonsec_delta_spec(),
            _csr_sec_nonctp_delta_spec(),
            _csr_sec_ctp_delta_spec(),
        )
    ]
    cases.append(_run_curvature_validation_case(row_count=row_count))
    phase_probes = (_run_girr_delta_phase_probe(factor_count=min(row_count, 240)),)
    return {
        "schema_version": "frtb_sbm_batch_arrow_benchmark_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": _environment_payload(),
        "controls": {
            "row_count_per_path": row_count,
            "profile_id": SbmRegulatoryProfile.BASEL_MAR21.value,
            "pairwise_evidence_mode": SbmPairwiseEvidenceMode.SUMMARY.value,
            "memory_proxy": (
                "tracemalloc peak bytes for Python allocations; Arrow and NumPy "
                "native buffers may not be fully counted"
            ),
            "synthetic_data_only": True,
        },
        "summary": _summary(cases, phase_probes),
        "cases": cases,
        "phase_probes": phase_probes,
        "remaining_boundaries": {
            "curvature_capital": "unsupported and fail-closed until #166",
            "unmigrated_sbm_measures": (
                "FX/equity/commodity/CSR vega and non-GIRR curvature remain unsupported "
                "or out of the current phase; do not infer capital support from the "
                "GIRR curvature validation handoff"
            ),
            "parent_issue": "#270",
        },
    }


def _run_capital_case(spec: CapitalPathSpec, *, row_count: int) -> dict[str, object]:
    context = _context(f"bench-{spec.label}", desk_id=spec.desk_id)

    (
        (
            row_result,
            row_build_seconds,
            row_compute_seconds,
            row_audit_seconds,
            row_result_hash,
            row_audit_hash,
        ),
        row_peak,
    ) = _traced_peak_bytes(
        lambda: _measure_row_capital_path(spec=spec, row_count=row_count, context=context)
    )
    (
        (
            batch,
            batch_result,
            table_seconds,
            normalize_seconds,
            batch_seconds,
            batch_compute_seconds,
            batch_audit_seconds,
            batch_result_hash,
            batch_audit_hash,
        ),
        batch_peak,
    ) = _traced_peak_bytes(
        lambda: _measure_arrow_batch_capital_path(
            spec=spec,
            row_count=row_count,
            context=context,
        )
    )

    capital_delta = _matching_capital_delta(
        label=spec.label,
        row_total=row_result.total_capital,
        batch_total=batch_result.total_capital,
    )

    return {
        "label": spec.label,
        "risk_class": batch.risk_class.value,
        "risk_measure": batch.risk_measure.value,
        "status": "capital_supported",
        "raw_row_count": row_count,
        "regulatory_factor_count": _factor_count(batch, spec.factor_axes),
        "capital_delta_abs": capital_delta,
        "row_compatibility_path": {
            "materialized_dataclass_count": row_count,
            "timings_seconds": {
                "row_dataclass_construction": row_build_seconds,
                "capital_calculation": row_compute_seconds,
                "audit_result_materialization": row_audit_seconds,
            },
            "result_hash": row_result_hash,
            "audit_hash": row_audit_hash,
            "pairwise_evidence": _pairwise_evidence_counts(row_result),
            "tracemalloc_peak_bytes": row_peak,
        },
        "arrow_batch_path": {
            "accepted_row_dataclasses_materialized": 0,
            "accepted_row_dataclasses_avoided": True,
            "timings_seconds": {
                "synthetic_arrow_table_construction": table_seconds,
                "handoff_normalization": normalize_seconds,
                "batch_construction": batch_seconds,
                "weighting_factor_grid_aggregation_and_result": batch_compute_seconds,
                "audit_result_materialization": batch_audit_seconds,
            },
            "result_hash": batch_result_hash,
            "audit_hash": batch_audit_hash,
            "handoff_hash_present": bool(batch.handoff_hash),
            "pairwise_evidence": _pairwise_evidence_counts(batch_result),
            "tracemalloc_peak_bytes": batch_peak,
        },
    }


def _run_curvature_validation_case(*, row_count: int) -> dict[str, object]:
    profile_id = SbmRegulatoryProfile.BASEL_MAR21.value

    (
        (row_branches, row_build_seconds, row_validate_seconds, row_branch_seconds),
        row_peak,
    ) = _traced_peak_bytes(
        lambda: _measure_row_curvature_validation_path(
            row_count=row_count,
            profile_id=profile_id,
        )
    )
    (
        (
            batch,
            branch_records,
            table_seconds,
            normalize_seconds,
            batch_seconds,
            batch_branch_seconds,
        ),
        batch_peak,
    ) = _traced_peak_bytes(
        lambda: _measure_arrow_batch_curvature_validation_path(
            row_count=row_count,
            profile_id=profile_id,
        )
    )

    batch_branches = tuple(record.selected_branch for record in branch_records)
    if row_branches != batch_branches:
        raise RuntimeError("GIRR curvature row and batch branch selection diverged")
    branch_selection_hash = _hash_json({"selected_branches": batch_branches})

    return {
        "label": "girr_curvature_validation",
        "risk_class": SbmRiskClass.GIRR.value,
        "risk_measure": SbmRiskMeasure.CURVATURE.value,
        "status": "validation_only_capital_unsupported",
        "raw_row_count": row_count,
        "regulatory_factor_count": _factor_count(batch, ("buckets", "risk_factors", "tenors")),
        "branch_selection_hash": branch_selection_hash,
        "row_compatibility_path": {
            "materialized_dataclass_count": row_count,
            "timings_seconds": {
                "row_dataclass_construction": row_build_seconds,
                "curvature_contract_validation": row_validate_seconds,
                "branch_selection": row_branch_seconds,
            },
            "result_hash": branch_selection_hash,
            "audit_hash": branch_selection_hash,
            "pairwise_evidence": {
                "total_count": 0,
                "materialized_count": 0,
                "omitted_count": 0,
            },
            "tracemalloc_peak_bytes": row_peak,
        },
        "arrow_batch_path": {
            "accepted_row_dataclasses_materialized": 0,
            "accepted_row_dataclasses_avoided": True,
            "timings_seconds": {
                "synthetic_arrow_table_construction": table_seconds,
                "handoff_normalization": normalize_seconds,
                "batch_construction": batch_seconds,
                "curvature_branch_selection": batch_branch_seconds,
            },
            "result_hash": branch_selection_hash,
            "audit_hash": branch_selection_hash,
            "handoff_hash_present": bool(batch.handoff_hash),
            "pairwise_evidence": {
                "total_count": 0,
                "materialized_count": 0,
                "omitted_count": 0,
            },
            "tracemalloc_peak_bytes": batch_peak,
        },
    }


def _timed(callback: Callable[[], Any]) -> TimedValue:
    started = time.perf_counter()
    value = callback()
    return value, time.perf_counter() - started


def _traced_peak_bytes(callback: Callable[[], Any]) -> TracedValue:
    tracemalloc.start()
    try:
        value = callback()
        _current, peak = tracemalloc.get_traced_memory()
        return value, peak
    finally:
        tracemalloc.stop()


def _measure_row_capital_path(
    *,
    spec: CapitalPathSpec,
    row_count: int,
    context: SbmCalculationContext,
) -> tuple[SbmCapitalResult, float, float, float, str, str]:
    rows, row_build_seconds = _timed(
        lambda: tuple(spec.row_factory(index) for index in range(row_count))
    )
    row_result, row_compute_seconds = _timed(lambda: calculate_sbm_capital(rows, context=context))
    row_payload, row_audit_seconds = _timed(lambda: serialize_sbm_result(row_result))
    return (
        row_result,
        row_build_seconds,
        row_compute_seconds,
        row_audit_seconds,
        _result_hash(row_payload),
        _hash_json(row_payload),
    )


def _measure_arrow_batch_capital_path(
    *,
    spec: CapitalPathSpec,
    row_count: int,
    context: SbmCalculationContext,
) -> tuple[SbmSensitivityBatch, SbmCapitalResult, float, float, float, float, float, str, str]:
    table, table_seconds = _timed(lambda: spec.table_factory(row_count))
    handoff, normalize_seconds = _timed(lambda: spec.normalize(table))
    batch, batch_seconds = _timed(lambda: spec.build_batch(handoff))
    batch_result, batch_compute_seconds = _timed(
        lambda: spec.calculate_batch(batch, context=context)
    )
    batch_payload, batch_audit_seconds = _timed(lambda: serialize_sbm_result(batch_result))
    return (
        batch,
        batch_result,
        table_seconds,
        normalize_seconds,
        batch_seconds,
        batch_compute_seconds,
        batch_audit_seconds,
        _result_hash(batch_payload),
        _hash_json(batch_payload),
    )


def _run_girr_delta_phase_probe(*, factor_count: int) -> dict[str, object]:
    (payload, peak_bytes) = _traced_peak_bytes(
        lambda: _measure_girr_delta_phase_probe(factor_count=factor_count)
    )
    payload["tracemalloc_peak_bytes"] = peak_bytes
    payload["result_hash"] = _hash_json(
        {
            "factor_count": payload["factor_count"],
            "matrix_shape": payload["matrix_shape"],
            "scenario_count": payload["scenario_count"],
        }
    )
    return payload


def _measure_girr_delta_phase_probe(*, factor_count: int) -> dict[str, object]:
    (weighted, tenor_by_id, risk_factor_by_id), weighting_seconds = _timed(
        lambda: _girr_delta_factor_grid(factor_count)
    )
    matrix, factor_grid_seconds = _timed(
        lambda: _build_girr_delta_intra_bucket_correlation_matrix(
            weighted,
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
            tenor_by_id=tenor_by_id,
            risk_factor_by_id=risk_factor_by_id,
        )
    )
    adjusted, scenario_seconds = _timed(
        lambda: tuple(
            adjust_correlation_matrix_for_scenario(matrix, scenario)
            for scenario in (
                SbmScenarioLabel.LOW,
                SbmScenarioLabel.MEDIUM,
                SbmScenarioLabel.HIGH,
            )
        )
    )
    if len(adjusted) != 3:
        raise RuntimeError("GIRR delta phase probe did not produce three scenario matrices")
    return {
        "label": "girr_delta_matrix_scenario_probe",
        "risk_class": SbmRiskClass.GIRR.value,
        "risk_measure": SbmRiskMeasure.DELTA.value,
        "status": "phase_probe",
        "factor_count": factor_count,
        "matrix_shape": list(matrix.shape),
        "scenario_count": len(adjusted),
        "timings_seconds": {
            "weighting_input_construction": weighting_seconds,
            "netting_factor_grid_and_correlation_matrix": factor_grid_seconds,
            "correlation_scenario_aggregation": scenario_seconds,
        },
    }


def _measure_row_curvature_validation_path(
    *,
    row_count: int,
    profile_id: str,
) -> tuple[tuple[str, ...], float, float, float]:
    rows, row_build_seconds = _timed(
        lambda: tuple(_girr_curvature_row(index) for index in range(row_count))
    )
    validated, row_validate_seconds = _timed(
        lambda: validate_curvature_sensitivities(rows, profile_id=profile_id)
    )
    row_branches, row_branch_seconds = _timed(
        lambda: tuple(
            curvature_worst_branch(item.up_shock_amount, item.down_shock_amount)
            for item in validated
        )
    )
    return row_branches, row_build_seconds, row_validate_seconds, row_branch_seconds


def _measure_arrow_batch_curvature_validation_path(
    *,
    row_count: int,
    profile_id: str,
) -> tuple[SbmSensitivityBatch, tuple[Any, ...], float, float, float, float]:
    table, table_seconds = _timed(lambda: _girr_curvature_table(row_count))
    handoff, normalize_seconds = _timed(lambda: normalize_girr_curvature_arrow_table(table))
    batch, batch_seconds = _timed(lambda: build_girr_curvature_batch_from_handoff(handoff))
    branch_records, batch_branch_seconds = _timed(
        lambda: select_girr_curvature_branches_from_batch(batch, profile_id=profile_id)
    )
    return (
        batch,
        branch_records,
        table_seconds,
        normalize_seconds,
        batch_seconds,
        batch_branch_seconds,
    )


def _matching_capital_delta(*, label: str, row_total: float, batch_total: float) -> float:
    if not math.isfinite(row_total) or not math.isfinite(batch_total):
        raise RuntimeError(
            f"{label}: row and batch capital must be finite, "
            f"got row={row_total!r}, batch={batch_total!r}"
        )
    capital_delta = abs(row_total - batch_total)
    if capital_delta > 1e-9:
        raise RuntimeError(f"{label}: row and batch capital diverged by {capital_delta}")
    return capital_delta


def _context(run_id: str, *, desk_id: str) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        desk_id=desk_id,
        run_controls=SbmRunControls(pairwise_evidence_mode=SbmPairwiseEvidenceMode.SUMMARY),
    )


def _factor_count(batch: SbmSensitivityBatch, axes: Sequence[str]) -> int:
    keys: set[tuple[object, ...]] = set()
    for row_index in range(batch.row_count):
        values: list[object] = []
        for axis in axes:
            column = getattr(batch, axis)
            values.append(None if column is None else column[row_index])
        keys.add(tuple(values))
    return len(keys)


def _pairwise_evidence_counts(result: SbmCapitalResult) -> dict[str, int]:
    total_count = 0
    materialized_count = 0
    omitted_count = 0
    for risk_class in result.risk_classes:
        for detail in risk_class.scenario_details:
            for bucket in detail.intra_buckets:
                summary = bucket.pairwise_correlation_summary
                if summary is None:
                    materialized_count += len(bucket.pairwise_correlations)
                    total_count += len(bucket.pairwise_correlations)
                else:
                    total_count += summary.total_count
                    materialized_count += summary.materialized_count
                    omitted_count += summary.omitted_count
    return {
        "total_count": total_count,
        "materialized_count": materialized_count,
        "omitted_count": omitted_count,
    }


def _summary(
    cases: Sequence[dict[str, object]],
    phase_probes: Sequence[dict[str, object]],
) -> dict[str, object]:
    row_dataclasses = 0
    arrow_dataclasses = 0
    raw_rows = 0
    netted_factors = 0
    pairwise_total = 0
    pairwise_materialized = 0
    row_peak = 0
    arrow_peak = 0
    ingestion_seconds = 0.0
    validation_seconds = 0.0
    capital_compute_seconds = 0.0
    audit_seconds = 0.0
    result_hash_inputs: list[dict[str, object]] = []
    audit_hash_inputs: list[dict[str, object]] = []

    for case in cases:
        row_path = _required_mapping(case, "row_compatibility_path")
        arrow_path = _required_mapping(case, "arrow_batch_path")
        arrow_timings = _required_mapping(arrow_path, "timings_seconds")
        pairwise = _required_mapping(arrow_path, "pairwise_evidence")

        raw_rows += int(case["raw_row_count"])
        netted_factors += int(case["regulatory_factor_count"])
        row_dataclasses += int(row_path["materialized_dataclass_count"])
        arrow_dataclasses += int(arrow_path["accepted_row_dataclasses_materialized"])
        pairwise_total += int(pairwise["total_count"])
        pairwise_materialized += int(pairwise["materialized_count"])
        row_peak = max(row_peak, int(row_path["tracemalloc_peak_bytes"]))
        arrow_peak = max(arrow_peak, int(arrow_path["tracemalloc_peak_bytes"]))
        ingestion_seconds += _sum_timing(arrow_timings, ("synthetic_arrow_table_construction",))
        validation_seconds += _sum_timing(
            arrow_timings,
            ("handoff_normalization", "batch_construction"),
        )
        capital_compute_seconds += _sum_timing(
            arrow_timings,
            (
                "weighting_factor_grid_aggregation_and_result",
                "curvature_branch_selection",
            ),
        )
        audit_seconds += float(arrow_timings.get("audit_result_materialization", 0.0))
        result_hash_inputs.append(
            {
                "label": case["label"],
                "hash": arrow_path["result_hash"],
            }
        )
        audit_hash_inputs.append(
            {
                "label": case["label"],
                "hash": arrow_path["audit_hash"],
            }
        )

    probe_timings = _phase_probe_timings(phase_probes)
    return {
        "raw_row_count": raw_rows,
        "netted_factor_count": netted_factors,
        "pairwise_evidence_count": pairwise_total,
        "pairwise_evidence_materialized_count": pairwise_materialized,
        "materialized_dataclass_count": {
            "row_compatibility_path": row_dataclasses,
            "arrow_batch_path": arrow_dataclasses,
        },
        "accepted_row_dataclasses_materialized": arrow_dataclasses,
        "accepted_row_dataclasses_avoided": arrow_dataclasses == 0,
        "peak_tracemalloc_bytes": {
            "row_compatibility_path": row_peak,
            "arrow_batch_path": arrow_peak,
        },
        "timings_seconds": {
            "ingestion": ingestion_seconds,
            "validation": validation_seconds,
            "weighting": capital_compute_seconds,
            "netting_factor_grid": probe_timings["netting_factor_grid"],
            "correlation_scenario_aggregation": probe_timings["correlation_scenario_aggregation"],
            "audit_serialization": audit_seconds,
            "wall_clock_proxy": (
                ingestion_seconds
                + validation_seconds
                + capital_compute_seconds
                + audit_seconds
                + probe_timings["netting_factor_grid"]
                + probe_timings["correlation_scenario_aggregation"]
            ),
        },
        "result_hash": _hash_json(result_hash_inputs),
        "audit_hash": _hash_json(audit_hash_inputs),
    }


def _required_mapping(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload[key]
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{key} must be a mapping in benchmark case")
    return value


def _sum_timing(payload: Mapping[str, object], keys: Sequence[str]) -> float:
    return sum(float(payload[key]) for key in keys if key in payload)


def _phase_probe_timings(phase_probes: Sequence[dict[str, object]]) -> dict[str, float]:
    netting_factor_grid = 0.0
    correlation_scenario = 0.0
    for probe in phase_probes:
        timings = _required_mapping(probe, "timings_seconds")
        netting_factor_grid += float(timings["netting_factor_grid_and_correlation_matrix"])
        correlation_scenario += float(timings["correlation_scenario_aggregation"])
    return {
        "netting_factor_grid": netting_factor_grid,
        "correlation_scenario_aggregation": correlation_scenario,
    }


def _result_hash(payload: Mapping[str, object]) -> str:
    return _hash_json(
        {
            "total_capital": payload["total_capital"],
            "profile_hash": payload["profile_hash"],
            "input_hash": payload["input_hash"],
            "risk_classes": payload["risk_classes"],
        }
    )


def _hash_json(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _environment_payload() -> dict[str, str]:
    return {
        "machine": platform.machine(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
    }


def _lineage(row_id: str, source_file: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="benchmark",
        source_file=source_file,
        source_row_id=row_id,
    )


def _girr_delta_factor_grid(
    factor_count: int,
) -> tuple[tuple[WeightedSensitivity, ...], dict[str, str], dict[str, str]]:
    tenors = (
        "3m",
        "6m",
        "1y",
        "2y",
        "3y",
        "5y",
        "10y",
        "15y",
        "20y",
        "30y",
        "INFL",
        "XCCY",
    )
    weighted: list[WeightedSensitivity] = []
    tenor_by_id: dict[str, str] = {}
    risk_factor_by_id: dict[str, str] = {}
    for index in range(factor_count):
        sensitivity_id = f"factor-{index:05d}"
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity_id,
                risk_class=SbmRiskClass.GIRR,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket="1",
                raw_amount=100.0 + index,
                risk_weight=1.0,
                scaled_amount=100.0 + index,
                citation_ids=("basel_mar21_41",),
            )
        )
        tenor_by_id[sensitivity_id] = tenors[index % len(tenors)]
        risk_factor_by_id[sensitivity_id] = f"curve-{index % 37:02d}"
    return tuple(weighted), tenor_by_id, risk_factor_by_id


def _base_columns(size: int, *, prefix: str, desk_id: str, source_file: str) -> dict[str, object]:
    return {
        "sensitivity_id": [f"{prefix}-{index:06d}" for index in range(size)],
        "source_row_id": [f"row-{prefix}-{index:06d}" for index in range(size)],
        "desk_id": [desk_id] * size,
        "legal_entity": ["LE-001"] * size,
        "amount_currency": ["USD"] * size,
        "lineage_source_system": ["benchmark"] * size,
        "lineage_source_file": [source_file] * size,
    }


def _girr_vega_spec() -> CapitalPathSpec:
    return CapitalPathSpec(
        label="girr_vega",
        row_factory=_girr_vega_row,
        table_factory=_girr_vega_table,
        normalize=normalize_girr_vega_arrow_table,
        build_batch=build_girr_vega_batch_from_handoff,
        calculate_batch=calculate_sbm_capital_from_girr_vega_batch,
        factor_axes=("buckets", "risk_factors", "tenors", "option_tenors"),
        desk_id="rates-desk",
    )


def _fx_delta_spec() -> CapitalPathSpec:
    return CapitalPathSpec(
        label="fx_delta",
        row_factory=_fx_delta_row,
        table_factory=_fx_delta_table,
        normalize=normalize_fx_delta_arrow_table,
        build_batch=build_fx_delta_batch_from_handoff,
        calculate_batch=calculate_sbm_capital_from_fx_delta_batch,
        factor_axes=("buckets", "risk_factors"),
        desk_id="fx-desk",
    )


def _equity_delta_spec() -> CapitalPathSpec:
    return CapitalPathSpec(
        label="equity_delta",
        row_factory=_equity_delta_row,
        table_factory=_equity_delta_table,
        normalize=normalize_equity_delta_arrow_table,
        build_batch=build_equity_delta_batch_from_handoff,
        calculate_batch=calculate_sbm_capital_from_equity_delta_batch,
        factor_axes=("buckets", "qualifiers", "risk_factors"),
        desk_id="equity-desk",
    )


def _commodity_delta_spec() -> CapitalPathSpec:
    return CapitalPathSpec(
        label="commodity_delta",
        row_factory=_commodity_delta_row,
        table_factory=_commodity_delta_table,
        normalize=normalize_commodity_delta_arrow_table,
        build_batch=build_commodity_delta_batch_from_handoff,
        calculate_batch=calculate_sbm_capital_from_commodity_delta_batch,
        factor_axes=("buckets", "risk_factors", "qualifiers", "tenors"),
        desk_id="commodity-desk",
    )


def _csr_nonsec_delta_spec() -> CapitalPathSpec:
    return CapitalPathSpec(
        label="csr_nonsec_delta",
        row_factory=_csr_nonsec_delta_row,
        table_factory=_csr_nonsec_delta_table,
        normalize=normalize_csr_nonsec_delta_arrow_table,
        build_batch=build_csr_nonsec_delta_batch_from_handoff,
        calculate_batch=calculate_sbm_capital_from_csr_nonsec_delta_batch,
        factor_axes=("buckets", "qualifiers", "tenors", "risk_factors"),
        desk_id="credit-desk",
    )


def _csr_sec_nonctp_delta_spec() -> CapitalPathSpec:
    return CapitalPathSpec(
        label="csr_sec_nonctp_delta",
        row_factory=_csr_sec_nonctp_delta_row,
        table_factory=_csr_sec_nonctp_delta_table,
        normalize=normalize_csr_sec_nonctp_delta_arrow_table,
        build_batch=build_csr_sec_nonctp_delta_batch_from_handoff,
        calculate_batch=calculate_sbm_capital_from_csr_sec_nonctp_delta_batch,
        factor_axes=("buckets", "qualifiers", "tenors", "risk_factors"),
        desk_id="credit-securitisation-desk",
    )


def _csr_sec_ctp_delta_spec() -> CapitalPathSpec:
    return CapitalPathSpec(
        label="csr_sec_ctp_delta",
        row_factory=_csr_sec_ctp_delta_row,
        table_factory=_csr_sec_ctp_delta_table,
        normalize=normalize_csr_sec_ctp_delta_arrow_table,
        build_batch=build_csr_sec_ctp_delta_batch_from_handoff,
        calculate_batch=calculate_sbm_capital_from_csr_sec_ctp_delta_batch,
        factor_axes=("buckets", "qualifiers", "tenors", "risk_factors"),
        desk_id="credit-ctp-desk",
    )


def _girr_vega_row(index: int) -> SbmSensitivity:
    option_tenors = ("1y", "2y", "5y", "10y")
    tenors = ("1y", "2y", "5y", "10y", "30y")
    row_id = f"row-vega-{index:06d}"
    return SbmSensitivity(
        sensitivity_id=f"vega-{index:06d}",
        source_row_id=row_id,
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.VEGA,
        bucket=str((index % 3) + 1),
        risk_factor="USD",
        amount=100_000.0 + index,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        tenor=tenors[index % len(tenors)],
        option_tenor=option_tenors[index % len(option_tenors)],
        lineage=_lineage(row_id, "synthetic-vega.arrow"),
    )


def _girr_vega_table(size: int) -> pa.Table:
    option_tenors = ("1y", "2y", "5y", "10y")
    tenors = ("1y", "2y", "5y", "10y", "30y")
    columns = _base_columns(
        size,
        prefix="vega",
        desk_id="rates-desk",
        source_file="synthetic-vega.arrow",
    )
    columns.update(
        {
            "risk_class": ["GIRR"] * size,
            "risk_measure": ["VEGA"] * size,
            "bucket": [str((index % 3) + 1) for index in range(size)],
            "risk_factor": ["USD"] * size,
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "sign_convention": ["RECEIVE"] * size,
            "tenor": [tenors[index % len(tenors)] for index in range(size)],
            "option_tenor": [option_tenors[index % len(option_tenors)] for index in range(size)],
        }
    )
    return pa.table(columns)


def _fx_delta_row(index: int) -> SbmSensitivity:
    currencies = ("EUR", "GBP", "JPY", "AUD", "CAD", "CHF")
    currency = currencies[index % len(currencies)]
    row_id = f"row-fx-{index:06d}"
    return SbmSensitivity(
        sensitivity_id=f"fx-{index:06d}",
        source_row_id=row_id,
        desk_id="fx-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=currency,
        risk_factor=currency,
        amount=100_000.0 + index,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=_lineage(row_id, "synthetic-fx.arrow"),
    )


def _fx_delta_table(size: int) -> pa.Table:
    currencies = ("EUR", "GBP", "JPY", "AUD", "CAD", "CHF")
    columns = _base_columns(size, prefix="fx", desk_id="fx-desk", source_file="synthetic-fx.arrow")
    columns.update(
        {
            "risk_class": ["FX"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [currencies[index % len(currencies)] for index in range(size)],
            "risk_factor": [currencies[index % len(currencies)] for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "sign_convention": ["LONG"] * size,
        }
    )
    return pa.table(columns)


def _equity_delta_row(index: int) -> SbmSensitivity:
    buckets = ("5", "6", "7", "8", "11")
    risk_factors = ("SPOT", "REPO")
    row_id = f"row-equity-{index:06d}"
    return SbmSensitivity(
        sensitivity_id=f"equity-{index:06d}",
        source_row_id=row_id,
        desk_id="equity-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.EQUITY,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=buckets[index % len(buckets)],
        risk_factor=risk_factors[index % len(risk_factors)],
        qualifier=f"ISS-{index % 73:03d}",
        amount=100_000.0 + index,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=_lineage(row_id, "synthetic-equity.arrow"),
    )


def _equity_delta_table(size: int) -> pa.Table:
    buckets = ("5", "6", "7", "8", "11")
    risk_factors = ("SPOT", "REPO")
    columns = _base_columns(
        size,
        prefix="equity",
        desk_id="equity-desk",
        source_file="synthetic-equity.arrow",
    )
    columns.update(
        {
            "risk_class": ["EQUITY"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [buckets[index % len(buckets)] for index in range(size)],
            "risk_factor": [risk_factors[index % len(risk_factors)] for index in range(size)],
            "qualifier": [f"ISS-{index % 73:03d}" for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "sign_convention": ["LONG"] * size,
        }
    )
    return pa.table(columns)


def _commodity_delta_row(index: int) -> SbmSensitivity:
    buckets = ("2", "3", "5", "6", "10")
    commodities = ("WTI", "BRENT", "ALU", "GOLD", "POWER")
    locations = ("NYMEX", "ICE", "LME")
    tenors = ("3m", "6m", "1y", "2y")
    row_id = f"row-commodity-{index:06d}"
    return SbmSensitivity(
        sensitivity_id=f"commodity-{index:06d}",
        source_row_id=row_id,
        desk_id="commodity-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.COMMODITY,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=buckets[index % len(buckets)],
        risk_factor=commodities[index % len(commodities)],
        qualifier=locations[index % len(locations)],
        tenor=tenors[index % len(tenors)],
        amount=100_000.0 + index,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=_lineage(row_id, "synthetic-commodity.arrow"),
    )


def _commodity_delta_table(size: int) -> pa.Table:
    buckets = ("2", "3", "5", "6", "10")
    commodities = ("WTI", "BRENT", "ALU", "GOLD", "POWER")
    locations = ("NYMEX", "ICE", "LME")
    tenors = ("3m", "6m", "1y", "2y")
    columns = _base_columns(
        size,
        prefix="commodity",
        desk_id="commodity-desk",
        source_file="synthetic-commodity.arrow",
    )
    columns.update(
        {
            "risk_class": ["COMMODITY"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [buckets[index % len(buckets)] for index in range(size)],
            "risk_factor": [commodities[index % len(commodities)] for index in range(size)],
            "qualifier": [locations[index % len(locations)] for index in range(size)],
            "tenor": [tenors[index % len(tenors)] for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "sign_convention": ["LONG"] * size,
        }
    )
    return pa.table(columns)


def _csr_nonsec_delta_row(index: int) -> SbmSensitivity:
    buckets = ("4", "5", "6", "12", "17")
    risk_factors = ("BOND", "CDS")
    tenors = ("6m", "1y", "3y", "5y", "10y")
    row_id = f"row-csr-nonsec-{index:06d}"
    return SbmSensitivity(
        sensitivity_id=f"csr-nonsec-{index:06d}",
        source_row_id=row_id,
        desk_id="credit-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.CSR_NONSEC,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=buckets[index % len(buckets)],
        risk_factor=risk_factors[index % len(risk_factors)],
        qualifier=f"ISS-{index % 97:03d}",
        tenor=tenors[index % len(tenors)],
        amount=100_000.0 + index,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=_lineage(row_id, "synthetic-csr-nonsec.arrow"),
    )


def _csr_nonsec_delta_table(size: int) -> pa.Table:
    buckets = ("4", "5", "6", "12", "17")
    risk_factors = ("BOND", "CDS")
    tenors = ("6m", "1y", "3y", "5y", "10y")
    columns = _base_columns(
        size,
        prefix="csr-nonsec",
        desk_id="credit-desk",
        source_file="synthetic-csr-nonsec.arrow",
    )
    columns.update(
        {
            "risk_class": ["CSR_NONSEC"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [buckets[index % len(buckets)] for index in range(size)],
            "risk_factor": [risk_factors[index % len(risk_factors)] for index in range(size)],
            "qualifier": [f"ISS-{index % 97:03d}" for index in range(size)],
            "tenor": [tenors[index % len(tenors)] for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "sign_convention": ["LONG"] * size,
        }
    )
    return pa.table(columns)


def _csr_sec_nonctp_delta_row(index: int) -> SbmSensitivity:
    buckets = ("1", "2", "3", "10", "25")
    risk_factors = ("BOND", "CDS")
    tenors = ("6m", "1y", "3y", "5y", "10y")
    row_id = f"row-csr-sec-nonctp-{index:06d}"
    return SbmSensitivity(
        sensitivity_id=f"csr-sec-nonctp-{index:06d}",
        source_row_id=row_id,
        desk_id="credit-securitisation-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=buckets[index % len(buckets)],
        risk_factor=risk_factors[index % len(risk_factors)],
        qualifier=f"TR-{index % 89:03d}",
        tenor=tenors[index % len(tenors)],
        amount=100_000.0 + index,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=_lineage(row_id, "synthetic-csr-sec-nonctp.arrow"),
    )


def _csr_sec_nonctp_delta_table(size: int) -> pa.Table:
    buckets = ("1", "2", "3", "10", "25")
    risk_factors = ("BOND", "CDS")
    tenors = ("6m", "1y", "3y", "5y", "10y")
    columns = _base_columns(
        size,
        prefix="csr-sec-nonctp",
        desk_id="credit-securitisation-desk",
        source_file="synthetic-csr-sec-nonctp.arrow",
    )
    columns.update(
        {
            "risk_class": ["CSR_SEC_NONCTP"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [buckets[index % len(buckets)] for index in range(size)],
            "risk_factor": [risk_factors[index % len(risk_factors)] for index in range(size)],
            "qualifier": [f"TR-{index % 89:03d}" for index in range(size)],
            "tenor": [tenors[index % len(tenors)] for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "sign_convention": ["LONG"] * size,
        }
    )
    return pa.table(columns)


def _csr_sec_ctp_delta_row(index: int) -> SbmSensitivity:
    buckets = ("1", "3", "5", "10", "16")
    risk_factors = ("BOND", "CDS")
    tenors = ("6m", "1y", "3y", "5y", "10y")
    row_id = f"row-csr-sec-ctp-{index:06d}"
    return SbmSensitivity(
        sensitivity_id=f"csr-sec-ctp-{index:06d}",
        source_row_id=row_id,
        desk_id="credit-ctp-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.CSR_SEC_CTP,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=buckets[index % len(buckets)],
        risk_factor=risk_factors[index % len(risk_factors)],
        qualifier=f"UND-{index % 83:03d}",
        tenor=tenors[index % len(tenors)],
        amount=100_000.0 + index,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=_lineage(row_id, "synthetic-csr-sec-ctp.arrow"),
    )


def _csr_sec_ctp_delta_table(size: int) -> pa.Table:
    buckets = ("1", "3", "5", "10", "16")
    risk_factors = ("BOND", "CDS")
    tenors = ("6m", "1y", "3y", "5y", "10y")
    columns = _base_columns(
        size,
        prefix="csr-sec-ctp",
        desk_id="credit-ctp-desk",
        source_file="synthetic-csr-sec-ctp.arrow",
    )
    columns.update(
        {
            "risk_class": ["CSR_SEC_CTP"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [buckets[index % len(buckets)] for index in range(size)],
            "risk_factor": [risk_factors[index % len(risk_factors)] for index in range(size)],
            "qualifier": [f"UND-{index % 83:03d}" for index in range(size)],
            "tenor": [tenors[index % len(tenors)] for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "sign_convention": ["LONG"] * size,
        }
    )
    return pa.table(columns)


def _girr_curvature_row(index: int) -> SbmSensitivity:
    tenors = ("1y", "2y", "5y", "10y", "30y")
    currencies = ("USD", "EUR", "GBP")
    row_id = f"row-curvature-{index:06d}"
    up_shock = -100_000.0 - float(index % 29)
    down_shock = -100_050.0 - float(index % 31)
    return SbmSensitivity(
        sensitivity_id=f"curvature-{index:06d}",
        source_row_id=row_id,
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.CURVATURE,
        bucket=str((index % 3) + 1),
        risk_factor=currencies[index % len(currencies)],
        amount=0.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        tenor=tenors[index % len(tenors)],
        up_shock_amount=up_shock,
        down_shock_amount=down_shock,
        lineage=_lineage(row_id, "synthetic-curvature.arrow"),
    )


def _girr_curvature_table(size: int) -> pa.Table:
    tenors = ("1y", "2y", "5y", "10y", "30y")
    currencies = ("USD", "EUR", "GBP")
    columns = _base_columns(
        size,
        prefix="curvature",
        desk_id="rates-desk",
        source_file="synthetic-curvature.arrow",
    )
    columns.update(
        {
            "risk_class": ["GIRR"] * size,
            "risk_measure": ["CURVATURE"] * size,
            "bucket": [str((index % 3) + 1) for index in range(size)],
            "risk_factor": [currencies[index % len(currencies)] for index in range(size)],
            "amount": pa.array([0.0] * size, type=pa.float64()),
            "sign_convention": ["RECEIVE"] * size,
            "tenor": [tenors[index % len(tenors)] for index in range(size)],
            "up_shock_amount": pa.array(
                [-100_000.0 - float(index % 29) for index in range(size)],
                type=pa.float64(),
            ),
            "down_shock_amount": pa.array(
                [-100_050.0 - float(index % 31) for index in range(size)],
                type=pa.float64(),
            ),
        }
    )
    return pa.table(columns)


if __name__ == "__main__":
    main()
