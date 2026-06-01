"""Benchmark migrated SBM row, Arrow handoff, and package batch paths."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import tracemalloc
from collections.abc import Callable, Sequence
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
    SbmSensitivity,
    SbmSensitivityBatch,
    SbmSignConvention,
    SbmSourceLineage,
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

DEFAULT_OUTPUT = Path("dist/benchmarks/frtb-sbm-batch-arrow.json")
DEFAULT_ROW_COUNT = 720

TimedValue = tuple[Any, float]


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
        "cases": cases,
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

    tracemalloc.start()
    rows, row_build_seconds = _timed(
        lambda: tuple(spec.row_factory(index) for index in range(row_count))
    )
    row_result, row_compute_seconds = _timed(lambda: calculate_sbm_capital(rows, context=context))
    _row_payload, row_audit_seconds = _timed(lambda: serialize_sbm_result(row_result))
    _row_current, row_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    table, table_seconds = _timed(lambda: spec.table_factory(row_count))
    handoff, normalize_seconds = _timed(lambda: spec.normalize(table))
    batch, batch_seconds = _timed(lambda: spec.build_batch(handoff))
    batch_result, batch_compute_seconds = _timed(
        lambda: spec.calculate_batch(batch, context=context)
    )
    _batch_payload, batch_audit_seconds = _timed(lambda: serialize_sbm_result(batch_result))
    _batch_current, batch_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    capital_delta = abs(row_result.total_capital - batch_result.total_capital)
    if capital_delta > 1e-9:
        raise RuntimeError(f"{spec.label}: row and batch capital diverged by {capital_delta}")

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
            "handoff_hash_present": bool(batch.handoff_hash),
            "pairwise_evidence": _pairwise_evidence_counts(batch_result),
            "tracemalloc_peak_bytes": batch_peak,
        },
    }


def _run_curvature_validation_case(*, row_count: int) -> dict[str, object]:
    profile_id = SbmRegulatoryProfile.BASEL_MAR21.value

    tracemalloc.start()
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
    _row_current, row_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    table, table_seconds = _timed(lambda: _girr_curvature_table(row_count))
    handoff, normalize_seconds = _timed(lambda: normalize_girr_curvature_arrow_table(table))
    batch, batch_seconds = _timed(lambda: build_girr_curvature_batch_from_handoff(handoff))
    branch_records, batch_branch_seconds = _timed(
        lambda: select_girr_curvature_branches_from_batch(batch, profile_id=profile_id)
    )
    _batch_current, batch_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    batch_branches = tuple(record.selected_branch for record in branch_records)
    if row_branches != batch_branches:
        raise RuntimeError("GIRR curvature row and batch branch selection diverged")

    return {
        "label": "girr_curvature_validation",
        "risk_class": SbmRiskClass.GIRR.value,
        "risk_measure": SbmRiskMeasure.CURVATURE.value,
        "status": "validation_only_capital_unsupported",
        "raw_row_count": row_count,
        "regulatory_factor_count": _factor_count(batch, ("buckets", "risk_factors", "tenors")),
        "row_compatibility_path": {
            "materialized_dataclass_count": row_count,
            "timings_seconds": {
                "row_dataclass_construction": row_build_seconds,
                "curvature_contract_validation": row_validate_seconds,
                "branch_selection": row_branch_seconds,
            },
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
