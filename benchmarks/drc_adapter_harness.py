#!/usr/bin/env python3
"""Benchmark DRC row, Arrow handoff, and package batch paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Generic, TypeVar

import pyarrow as pa
from frtb_common import source_content_hash
from frtb_drc import (
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcCapitalResult,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    build_drc_nonsec_batch_from_handoff,
    calculate_drc_capital,
    calculate_drc_capital_from_batch,
    normalize_drc_nonsec_arrow_table,
    serialize_result,
)

DEFAULT_OUTPUT = Path("dist/benchmarks/frtb-drc-batch-arrow.json")
DEFAULT_ROW_COUNT = 5_000
T = TypeVar("T")


@dataclass(frozen=True)
class TimedResult(Generic[T]):
    value: T
    seconds: float


@dataclass(frozen=True)
class DrcBenchmarkConfig:
    row_count: int = DEFAULT_ROW_COUNT
    issuer_count: int = 1_000
    run_id: str = "frtb-drc-batch-arrow-benchmark"
    calculation_date: date = date(2026, 3, 31)
    base_currency: str = "USD"
    profile_id: str = "US_NPR_2_0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row-count", type=int, default=DEFAULT_ROW_COUNT)
    parser.add_argument("--issuer-count", type=int, default=1_000)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def run_benchmark(config: DrcBenchmarkConfig) -> dict[str, object]:
    if config.row_count <= 0:
        raise ValueError("row-count must be positive")
    if config.issuer_count <= 0:
        raise ValueError("issuer-count must be positive")

    tracemalloc.start()
    wall_started = time.perf_counter()

    row_positions = _timed(lambda: build_positions(config))
    row_result = _timed(
        lambda: calculate_drc_capital(row_positions.value, context=_context(config))
    )
    row_payload = _timed(lambda: serialize_result(row_result.value))

    arrow_table = _timed(lambda: build_arrow_table(config))
    handoff = _timed(
        lambda: normalize_drc_nonsec_arrow_table(
            arrow_table.value,
            source_hash=source_content_hash("synthetic drc batch benchmark"),
        )
    )
    batch = _timed(lambda: build_drc_nonsec_batch_from_handoff(handoff.value))
    batch_result = _timed(
        lambda: calculate_drc_capital_from_batch(batch.value, context=_context(config))
    )
    batch_payload = _timed(lambda: serialize_result(batch_result.value.result))

    _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    wall_seconds = time.perf_counter() - wall_started

    _require_matching_capital(row_result.value, batch_result.value.result)
    return {
        "schema_version": "frtb_drc_batch_arrow_benchmark_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "parameters": {
            "row_count": config.row_count,
            "issuer_count": config.issuer_count,
            "profile_id": config.profile_id,
        },
        "summary": {
            "timings_seconds": {
                "wall_clock": wall_seconds,
                "row_dataclass_construction": row_positions.seconds,
                "row_calculation": row_result.seconds,
                "row_audit_serialization": row_payload.seconds,
                "arrow_table_construction": arrow_table.seconds,
                "handoff_normalization": handoff.seconds,
                "batch_construction": batch.seconds,
                "batch_calculation": batch_result.seconds,
                "batch_audit_serialization": batch_payload.seconds,
            },
            "materialized_dataclass_count": {
                "row_compatibility_path": config.row_count,
                "arrow_batch_path": batch_result.value.accepted_row_dataclasses_materialized,
            },
            "accepted_row_dataclasses_avoided": (
                batch_result.value.accepted_row_dataclasses_materialized == 0
            ),
            "tracemalloc_peak_bytes": peak_bytes,
            "capital": {
                "row_total": row_result.value.total_drc,
                "batch_total": batch_result.value.result.total_drc,
                "absolute_delta": abs(
                    row_result.value.total_drc - batch_result.value.result.total_drc
                ),
            },
            "result_hashes": {
                "row_payload": _hash_json(row_payload.value),
                "batch_payload": _hash_json(batch_payload.value),
                "batch_input_hash": batch.value.input_hash,
                "batch_handoff_hash_present": bool(batch.value.handoff_hash),
            },
            "net_jtd_count": len(batch_result.value.result.net_jtds),
            "bucket_count": len(batch_result.value.result.categories[0].bucket_results),
        },
    }


def write_report(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    report = run_benchmark(
        DrcBenchmarkConfig(row_count=args.row_count, issuer_count=args.issuer_count)
    )
    write_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))  # noqa: T201
    return 0


def _timed(callback: Callable[[], T]) -> TimedResult[T]:
    started = time.perf_counter()
    value = callback()
    return TimedResult(value=value, seconds=time.perf_counter() - started)


def _context(config: DrcBenchmarkConfig) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id=config.run_id,
        calculation_date=config.calculation_date,
        base_currency=config.base_currency,
        profile_id=config.profile_id,
    )


def build_positions(config: DrcBenchmarkConfig) -> tuple[DrcPosition, ...]:
    return tuple(_position_for_index(index, config) for index in range(config.row_count))


def build_arrow_table(config: DrcBenchmarkConfig) -> pa.Table:
    rows = [_row_values(index, config) for index in range(config.row_count)]
    return pa.table(
        {
            "position_id": [row["position_id"] for row in rows],
            "source_row_id": [row["source_row_id"] for row in rows],
            "desk_id": [row["desk_id"] for row in rows],
            "legal_entity": [row["legal_entity"] for row in rows],
            "risk_class": _dictionary([row["risk_class"] for row in rows]),
            "instrument_type": _dictionary([row["instrument_type"] for row in rows]),
            "default_direction": _dictionary([row["default_direction"] for row in rows]),
            "issuer_id": [row["issuer_id"] for row in rows],
            "tranche_id": pa.nulls(config.row_count, type=pa.string()),
            "index_series_id": pa.nulls(config.row_count, type=pa.string()),
            "bucket_key": _dictionary([row["bucket_key"] for row in rows]),
            "seniority": _dictionary([row["seniority"] for row in rows]),
            "credit_quality": _dictionary([row["credit_quality"] for row in rows]),
            "notional": pa.array([row["notional"] for row in rows], type=pa.float64()),
            "market_value": pa.nulls(config.row_count, type=pa.float64()),
            "cumulative_pnl": pa.array([row["cumulative_pnl"] for row in rows], type=pa.float64()),
            "maturity_years": pa.array([row["maturity_years"] for row in rows], type=pa.float64()),
            "currency": _dictionary([row["currency"] for row in rows]),
            "lgd_override": pa.nulls(config.row_count, type=pa.float64()),
            "is_defaulted": pa.array([row["is_defaulted"] for row in rows], type=pa.bool_()),
            "is_gse": pa.array([False] * config.row_count, type=pa.bool_()),
            "is_pse": pa.array([False] * config.row_count, type=pa.bool_()),
            "is_covered_bond": pa.array([False] * config.row_count, type=pa.bool_()),
            "lineage_source_system": ["synthetic-drc-benchmark"] * config.row_count,
            "lineage_source_file": ["generated"] * config.row_count,
            "citation_ids": ["US_NPR_210_SCOPE"] * config.row_count,
        }
    )


def _position_for_index(index: int, config: DrcBenchmarkConfig) -> DrcPosition:
    row = _row_values(index, config)
    return DrcPosition(
        position_id=str(row["position_id"]),
        source_row_id=str(row["source_row_id"]),
        desk_id=str(row["desk_id"]),
        legal_entity=str(row["legal_entity"]),
        risk_class=str(row["risk_class"]),
        instrument_type=str(row["instrument_type"]),
        default_direction=str(row["default_direction"]),
        issuer_id=str(row["issuer_id"]),
        tranche_id=None,
        index_series_id=None,
        bucket_key=str(row["bucket_key"]),
        seniority=str(row["seniority"]),
        credit_quality=str(row["credit_quality"]),
        notional=float(row["notional"]),
        market_value=None,
        cumulative_pnl=float(row["cumulative_pnl"]),
        maturity_years=float(row["maturity_years"]),
        currency=str(row["currency"]),
        is_defaulted=bool(row["is_defaulted"]),
        lineage=DrcSourceLineage(
            source_system="synthetic-drc-benchmark",
            source_file="generated",
            source_row_id=str(row["source_row_id"]),
            source_column_map={
                "notional": "notional",
                "cumulative_pnl": "cumulative_pnl",
                "maturity_years": "maturity_years",
            },
        ),
        citation_ids=("US_NPR_210_SCOPE",),
    )


def _row_values(index: int, config: DrcBenchmarkConfig) -> dict[str, object]:
    issuer_index = index % config.issuer_count
    bucket = _bucket_for_issuer(issuer_index)
    return {
        "position_id": f"drc-pos-{index:07d}",
        "source_row_id": f"row-{index:07d}",
        "desk_id": f"desk-{index % 25:03d}",
        "legal_entity": f"LE-{index % 8:03d}",
        "risk_class": DrcRiskClass.NON_SECURITISATION.value,
        "instrument_type": DrcInstrumentType.BOND.value,
        "default_direction": (
            DefaultDirection.LONG.value if index % 3 else DefaultDirection.SHORT.value
        ),
        "issuer_id": f"issuer-{issuer_index:06d}",
        "bucket_key": bucket,
        "seniority": _seniority_for_issuer(issuer_index),
        "credit_quality": _credit_quality_for_bucket(bucket, issuer_index),
        "notional": 250_000.0 + float(index % 1_000) * 100.0,
        "cumulative_pnl": float((index % 17) - 8) * 1_000.0,
        "maturity_years": 0.25 + float(index % 12) / 12.0,
        "currency": config.base_currency,
        "is_defaulted": bucket == "DEFAULTED",
    }


def _bucket_for_issuer(issuer_index: int) -> str:
    buckets = ("CORPORATE", "PSE_GSE", "NON_US_SOVEREIGN", "DEFAULTED")
    return buckets[issuer_index % len(buckets)]


def _seniority_for_issuer(issuer_index: int) -> str:
    seniorities = (
        DrcSeniority.SENIOR_DEBT.value,
        DrcSeniority.NON_SENIOR_DEBT.value,
        DrcSeniority.PSE.value,
        DrcSeniority.COVERED_BOND.value,
    )
    return seniorities[issuer_index % len(seniorities)]


def _credit_quality_for_bucket(bucket: str, issuer_index: int) -> str:
    if bucket == "DEFAULTED":
        return CreditQuality.DEFAULTED.value
    qualities = (
        CreditQuality.INVESTMENT_GRADE.value,
        CreditQuality.SPECULATIVE_GRADE.value,
        CreditQuality.SUB_SPECULATIVE_GRADE.value,
    )
    return qualities[issuer_index % len(qualities)]


def _dictionary(values: list[object]) -> pa.Array:
    return pa.array(values).dictionary_encode()


def _hash_json(payload: dict[str, object]) -> str:
    encoded = bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_matching_capital(row_result: DrcCapitalResult, batch_result: DrcCapitalResult) -> None:
    if abs(row_result.total_drc - batch_result.total_drc) > 1e-9:
        raise RuntimeError(
            f"row and batch DRC totals diverged: {row_result.total_drc} != {batch_result.total_drc}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
