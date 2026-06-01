"""Synthetic large-scale CVA benchmark without dataframe dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_cva import (
    CreditQuality,
    CvaCalculationContext,
    CvaCapitalResult,
    CvaCounterparty,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    build_cva_counterparty_batch_from_columns,
    build_cva_counterparty_batch_from_handoff,
    build_cva_netting_set_batch_from_columns,
    build_cva_netting_set_batch_from_handoff,
    build_sa_cva_sensitivity_batch_from_columns,
    build_sa_cva_sensitivity_batch_from_handoff,
    calculate_cva_capital,
    calculate_cva_capital_from_batches,
    normalize_cva_counterparty_arrow_table,
    normalize_cva_netting_set_arrow_table,
    normalize_sa_cva_sensitivity_arrow_table,
    serialize_cva_result,
)

T = TypeVar("T")
DEFAULT_OUTPUT = Path("dist/benchmarks/frtb-cva-target-scale.json")


@dataclass(frozen=True)
class CvaBenchmarkConfig:
    counterparties: int = 100
    netting_sets: int = 10_000
    sensitivities: int = 100_000


@dataclass(frozen=True)
class TimedResult(Generic[T]):
    value: T
    seconds: float
    peak_bytes: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counterparties", type=int, default=100)
    parser.add_argument("--netting-sets", type=int, default=10_000)
    parser.add_argument("--sensitivities", type=int, default=100_000)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def run_benchmark(config: CvaBenchmarkConfig) -> dict[str, object]:
    if config.counterparties <= 0:
        raise ValueError("counterparties must be positive")
    if config.netting_sets <= 0:
        raise ValueError("netting_sets must be positive")
    if config.sensitivities <= 0:
        raise ValueError("sensitivities must be positive")

    wall_started = time.perf_counter()
    counterparties = _synthetic_counterparties(config.counterparties)
    netting_sets = _synthetic_netting_sets(
        config.netting_sets,
        counterparty_count=config.counterparties,
    )
    ba_context = _ba_context()

    row_ba = _measure(lambda: calculate_cva_capital(ba_context, counterparties, netting_sets))
    counterparty_columns = _counterparty_columns(counterparties)
    netting_set_columns = _netting_set_columns(netting_sets)
    column_ba_build = _measure(
        lambda: (
            build_cva_counterparty_batch_from_columns(**counterparty_columns),
            build_cva_netting_set_batch_from_columns(**netting_set_columns),
        )
    )
    column_counterparties, column_netting_sets = column_ba_build.value
    column_ba = _measure(
        lambda: calculate_cva_capital_from_batches(
            ba_context,
            column_counterparties,
            column_netting_sets,
        )
    )
    ba_arrow_table = _measure(
        lambda: (
            pa.table(_counterparty_handoff_columns(counterparties)),
            pa.table(_netting_set_handoff_columns(netting_sets)),
        )
    )
    counterparty_table, netting_set_table = ba_arrow_table.value
    ba_arrow_handoff = _measure(
        lambda: (
            normalize_cva_counterparty_arrow_table(counterparty_table),
            normalize_cva_netting_set_arrow_table(netting_set_table),
        )
    )
    counterparty_handoff, netting_set_handoff = ba_arrow_handoff.value
    arrow_ba_build = _measure(
        lambda: (
            build_cva_counterparty_batch_from_handoff(counterparty_handoff),
            build_cva_netting_set_batch_from_handoff(netting_set_handoff),
        )
    )
    arrow_counterparties, arrow_netting_sets = arrow_ba_build.value
    arrow_ba = _measure(
        lambda: calculate_cva_capital_from_batches(
            ba_context,
            arrow_counterparties,
            arrow_netting_sets,
        )
    )

    sensitivities = _synthetic_sensitivities(config.sensitivities)
    sa_context = _sa_context()
    row_sa = _measure(
        lambda: calculate_cva_capital(
            sa_context,
            (),
            (),
            sensitivities=sensitivities,
        )
    )
    sensitivity_columns = _sensitivity_columns(sensitivities)
    column_sa_build = _measure(
        lambda: build_sa_cva_sensitivity_batch_from_columns(**sensitivity_columns)
    )
    column_sa = _measure(
        lambda: calculate_cva_capital_from_batches(
            sa_context,
            sensitivities=column_sa_build.value,
        )
    )
    sensitivity_table = _measure(lambda: pa.table(_sensitivity_handoff_columns(sensitivities)))
    sensitivity_handoff = _measure(
        lambda: normalize_sa_cva_sensitivity_arrow_table(sensitivity_table.value)
    )
    arrow_sa_build = _measure(
        lambda: build_sa_cva_sensitivity_batch_from_handoff(sensitivity_handoff.value)
    )
    arrow_sa = _measure(
        lambda: calculate_cva_capital_from_batches(
            sa_context,
            sensitivities=arrow_sa_build.value,
        )
    )
    ba_arrow_parse_seconds = ba_arrow_table.seconds
    ba_arrow_adapt_seconds = ba_arrow_handoff.seconds
    ba_arrow_build_seconds = arrow_ba_build.seconds
    ba_arrow_calculate_seconds = arrow_ba.seconds
    sa_arrow_parse_seconds = sensitivity_table.seconds
    sa_arrow_adapt_seconds = sensitivity_handoff.seconds
    sa_arrow_build_seconds = arrow_sa_build.seconds
    sa_arrow_calculate_seconds = arrow_sa.seconds
    parse_seconds = ba_arrow_parse_seconds + sa_arrow_parse_seconds
    adapt_seconds = ba_arrow_adapt_seconds + sa_arrow_adapt_seconds
    build_seconds = ba_arrow_build_seconds + sa_arrow_build_seconds
    calculate_seconds = ba_arrow_calculate_seconds + sa_arrow_calculate_seconds
    ba_column_delta = abs(column_ba.value.result.total_cva_capital - row_ba.value.total_cva_capital)
    ba_arrow_delta = abs(arrow_ba.value.result.total_cva_capital - row_ba.value.total_cva_capital)
    sa_column_delta = abs(column_sa.value.result.total_cva_capital - row_sa.value.total_cva_capital)
    sa_arrow_delta = abs(arrow_sa.value.result.total_cva_capital - row_sa.value.total_cva_capital)
    dataclasses_materialized = _dataclass_counts(column_ba, arrow_ba, column_sa, arrow_sa)
    arrow_dataclasses_materialized = (
        dataclasses_materialized["ba_arrow_counterparties"]
        + dataclasses_materialized["ba_arrow_netting_sets"]
        + dataclasses_materialized["sa_arrow_sensitivities"]
    )

    return {
        "schema_version": "frtb_cva_target_scale_benchmark_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "parameters": {
            "counterparties": config.counterparties,
            "netting_sets": config.netting_sets,
            "sensitivities": config.sensitivities,
        },
        "summary": {
            "timings_seconds": {
                "parse": parse_seconds,
                "adapt": adapt_seconds,
                "build": build_seconds,
                "calculate": calculate_seconds,
                "wall_clock": time.perf_counter() - wall_started,
                "wall_clock_proxy": parse_seconds
                + adapt_seconds
                + build_seconds
                + calculate_seconds,
            },
            "materialized_dataclass_count": {
                "arrow_batch_path": arrow_dataclasses_materialized,
                "column_batch_path": dataclasses_materialized["ba_column_counterparties"]
                + dataclasses_materialized["ba_column_netting_sets"]
                + dataclasses_materialized["sa_column_sensitivities"],
            },
            "accepted_row_dataclasses_materialized": arrow_dataclasses_materialized,
            "capital_delta_abs_max": max(
                ba_column_delta,
                ba_arrow_delta,
                sa_column_delta,
                sa_arrow_delta,
            ),
            "tracemalloc_peak_bytes": max(
                ba_arrow_table.peak_bytes,
                ba_arrow_handoff.peak_bytes,
                arrow_ba_build.peak_bytes,
                arrow_ba.peak_bytes,
                sensitivity_table.peak_bytes,
                sensitivity_handoff.peak_bytes,
                arrow_sa_build.peak_bytes,
                arrow_sa.peak_bytes,
            ),
        },
        "timings": {
            "ba_row_calculate_seconds": row_ba.seconds,
            "ba_column_build_seconds": column_ba_build.seconds,
            "ba_column_calculate_seconds": column_ba.seconds,
            "ba_arrow_table_seconds": ba_arrow_table.seconds,
            "ba_arrow_handoff_seconds": ba_arrow_handoff.seconds,
            "ba_arrow_build_seconds": arrow_ba_build.seconds,
            "ba_arrow_calculate_seconds": arrow_ba.seconds,
            "sa_row_calculate_seconds": row_sa.seconds,
            "sa_column_build_seconds": column_sa_build.seconds,
            "sa_column_calculate_seconds": column_sa.seconds,
            "sa_arrow_table_seconds": sensitivity_table.seconds,
            "sa_arrow_handoff_seconds": sensitivity_handoff.seconds,
            "sa_arrow_build_seconds": arrow_sa_build.seconds,
            "sa_arrow_calculate_seconds": arrow_sa.seconds,
        },
        "memory": {
            "ba_row_peak_bytes": row_ba.peak_bytes,
            "ba_column_build_peak_bytes": column_ba_build.peak_bytes,
            "ba_column_calculate_peak_bytes": column_ba.peak_bytes,
            "ba_arrow_table_peak_bytes": ba_arrow_table.peak_bytes,
            "ba_arrow_handoff_peak_bytes": ba_arrow_handoff.peak_bytes,
            "ba_arrow_build_peak_bytes": arrow_ba_build.peak_bytes,
            "ba_arrow_calculate_peak_bytes": arrow_ba.peak_bytes,
            "sa_row_peak_bytes": row_sa.peak_bytes,
            "sa_column_build_peak_bytes": column_sa_build.peak_bytes,
            "sa_column_calculate_peak_bytes": column_sa.peak_bytes,
            "sa_arrow_table_peak_bytes": sensitivity_table.peak_bytes,
            "sa_arrow_handoff_peak_bytes": sensitivity_handoff.peak_bytes,
            "sa_arrow_build_peak_bytes": arrow_sa_build.peak_bytes,
            "sa_arrow_calculate_peak_bytes": arrow_sa.peak_bytes,
        },
        "dataclasses_materialized": dataclasses_materialized,
        "result": {
            "ba_total_cva_capital": row_ba.value.total_cva_capital,
            "ba_row_payload_hash": _payload_hash(row_ba.value),
            "ba_column_payload_hash": _payload_hash(column_ba.value.result),
            "ba_arrow_payload_hash": _payload_hash(arrow_ba.value.result),
            "ba_column_capital_delta": ba_column_delta,
            "ba_arrow_capital_delta": ba_arrow_delta,
            "sa_total_cva_capital": row_sa.value.total_cva_capital,
            "sa_row_payload_hash": _payload_hash(row_sa.value),
            "sa_column_payload_hash": _payload_hash(column_sa.value.result),
            "sa_arrow_payload_hash": _payload_hash(arrow_sa.value.result),
            "sa_column_capital_delta": sa_column_delta,
            "sa_arrow_capital_delta": sa_arrow_delta,
        },
    }


def _measure(fn: Callable[[], T]) -> TimedResult[T]:
    tracemalloc.start()
    try:
        started = time.perf_counter()
        value = fn()
        seconds = time.perf_counter() - started
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return TimedResult(value=value, seconds=seconds, peak_bytes=peak_bytes)


def _dataclass_counts(
    column_ba: Any,
    arrow_ba: Any,
    column_sa: Any,
    arrow_sa: Any,
) -> dict[str, int]:
    column_ba_value = column_ba.value
    arrow_ba_value = arrow_ba.value
    column_sa_value = column_sa.value
    arrow_sa_value = arrow_sa.value
    return {
        "ba_column_counterparties": getattr(
            column_ba_value,
            "accepted_counterparty_dataclasses_materialized",
        ),
        "ba_column_netting_sets": getattr(
            column_ba_value,
            "accepted_netting_set_dataclasses_materialized",
        ),
        "ba_arrow_counterparties": getattr(
            arrow_ba_value,
            "accepted_counterparty_dataclasses_materialized",
        ),
        "ba_arrow_netting_sets": getattr(
            arrow_ba_value,
            "accepted_netting_set_dataclasses_materialized",
        ),
        "sa_column_sensitivities": getattr(
            column_sa_value,
            "accepted_sensitivity_dataclasses_materialized",
        ),
        "sa_arrow_sensitivities": getattr(
            arrow_sa_value,
            "accepted_sensitivity_dataclasses_materialized",
        ),
    }


def _ba_context() -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id="cva-ba-benchmark",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
    )


def _sa_context() -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id="cva-sa-benchmark",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )


def _synthetic_counterparties(count: int) -> tuple[CvaCounterparty, ...]:
    return tuple(
        CvaCounterparty(
            counterparty_id=f"ctp-{index}",
            desk_id="desk-a",
            legal_entity="LE-001",
            sector=CvaSector.SOVEREIGN,
            credit_quality=CreditQuality.INVESTMENT_GRADE,
            region="EMEA",
            source_row_id=f"row-ctp-{index}",
            lineage=_lineage("counterparties.csv", f"row-ctp-{index}"),
        )
        for index in range(count)
    )


def _synthetic_netting_sets(
    count: int,
    *,
    counterparty_count: int,
) -> tuple[CvaNettingSet, ...]:
    return tuple(
        CvaNettingSet(
            netting_set_id=f"ns-{index}",
            counterparty_id=f"ctp-{index % counterparty_count}",
            ead=10_000.0 + float(index % 17),
            effective_maturity=1.0 + float(index % 5) * 0.25,
            discount_factor=1.0,
            currency="USD",
            sign_convention="non_negative",
            uses_imm_ead=True,
            source_row_id=f"row-ns-{index}",
            lineage=_lineage("netting-sets.csv", f"row-ns-{index}"),
        )
        for index in range(count)
    )


def _synthetic_sensitivities(count: int) -> tuple[SaCvaSensitivity, ...]:
    currencies = ("USD", "EUR", "GBP", "JPY")
    tenors = ("1y", "2y", "5y", "10y", "30y")
    return tuple(
        SaCvaSensitivity(
            sensitivity_id=f"sens-{index}",
            risk_class=SaCvaRiskClass.GIRR,
            risk_measure=SaCvaRiskMeasure.DELTA,
            sensitivity_tag=SensitivityTag.CVA,
            bucket_id=currencies[index % len(currencies)],
            risk_factor_key=f"{currencies[index % len(currencies)]}-ois",
            tenor=tenors[index % len(tenors)],
            amount=100.0 + float(index % 23),
            amount_currency="USD",
            sign_convention="positive_loss",
            source_row_id=f"row-sens-{index}",
            lineage=_lineage("sensitivities.csv", f"row-sens-{index}"),
        )
        for index in range(count)
    )


def _lineage(source_file: str, source_row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic-cva-benchmark",
        source_file=source_file,
        source_row_id=source_row_id,
        source_column_map=(),
    )


def _counterparty_columns(counterparties: tuple[CvaCounterparty, ...]) -> dict[str, Any]:
    payload = _counterparty_handoff_columns(counterparties)
    return {
        "counterparty_ids": payload["counterparty_id"],
        "desk_ids": payload["desk_id"],
        "legal_entities": payload["legal_entity"],
        "sectors": payload["sector"],
        "credit_qualities": payload["credit_quality"],
        "regions": payload["region"],
        "source_row_ids": payload["source_row_id"],
        "lineage_source_systems": payload["lineage_source_system"],
        "lineage_source_files": payload["lineage_source_file"],
        "lineage_source_row_ids": payload["lineage_source_row_id"],
    }


def _netting_set_columns(netting_sets: tuple[CvaNettingSet, ...]) -> dict[str, Any]:
    payload = _netting_set_handoff_columns(netting_sets)
    return {
        "netting_set_ids": payload["netting_set_id"],
        "counterparty_ids": payload["counterparty_id"],
        "eads": payload["ead"],
        "effective_maturities": payload["effective_maturity"],
        "discount_factors": payload["discount_factor"],
        "currencies": payload["currency"],
        "sign_conventions": payload["sign_convention"],
        "uses_imm_eads": payload["uses_imm_ead"],
        "source_row_ids": payload["source_row_id"],
        "carved_out_to_ba_cva": payload["carved_out_to_ba_cva"],
        "discount_factor_explicit": payload["discount_factor_explicit"],
        "lineage_source_systems": payload["lineage_source_system"],
        "lineage_source_files": payload["lineage_source_file"],
        "lineage_source_row_ids": payload["lineage_source_row_id"],
    }


def _sensitivity_columns(sensitivities: tuple[SaCvaSensitivity, ...]) -> dict[str, Any]:
    return {
        "sensitivity_ids": [item.sensitivity_id for item in sensitivities],
        "risk_classes": [item.risk_class.value for item in sensitivities],
        "risk_measures": [item.risk_measure.value for item in sensitivities],
        "sensitivity_tags": [item.sensitivity_tag.value for item in sensitivities],
        "bucket_ids": [item.bucket_id for item in sensitivities],
        "risk_factor_keys": [item.risk_factor_key for item in sensitivities],
        "amounts": [item.amount for item in sensitivities],
        "amount_currencies": [item.amount_currency for item in sensitivities],
        "sign_conventions": [item.sign_convention for item in sensitivities],
        "source_row_ids": [item.source_row_id for item in sensitivities],
        "tenors": [item.tenor for item in sensitivities],
        "volatility_inputs": [item.volatility_input for item in sensitivities],
        "hedge_ids": [item.hedge_id for item in sensitivities],
        "lineage_source_systems": [
            "" if item.lineage is None else item.lineage.source_system for item in sensitivities
        ],
        "lineage_source_files": [
            "" if item.lineage is None else item.lineage.source_file for item in sensitivities
        ],
        "lineage_source_row_ids": [
            item.source_row_id if item.lineage is None else item.lineage.source_row_id
            for item in sensitivities
        ],
    }


def _sensitivity_handoff_columns(
    sensitivities: tuple[SaCvaSensitivity, ...],
) -> dict[str, object]:
    return {
        "sensitivity_id": [item.sensitivity_id for item in sensitivities],
        "risk_class": [item.risk_class.value for item in sensitivities],
        "risk_measure": [item.risk_measure.value for item in sensitivities],
        "sensitivity_tag": [item.sensitivity_tag.value for item in sensitivities],
        "bucket_id": [item.bucket_id for item in sensitivities],
        "risk_factor_key": [item.risk_factor_key for item in sensitivities],
        "amount": [item.amount for item in sensitivities],
        "amount_currency": [item.amount_currency for item in sensitivities],
        "sign_convention": [item.sign_convention for item in sensitivities],
        "source_row_id": [item.source_row_id for item in sensitivities],
        "tenor": [item.tenor for item in sensitivities],
        "volatility_input": [item.volatility_input for item in sensitivities],
        "hedge_id": [item.hedge_id for item in sensitivities],
        "lineage_source_system": [
            "" if item.lineage is None else item.lineage.source_system for item in sensitivities
        ],
        "lineage_source_file": [
            "" if item.lineage is None else item.lineage.source_file for item in sensitivities
        ],
        "lineage_source_row_id": [
            item.source_row_id if item.lineage is None else item.lineage.source_row_id
            for item in sensitivities
        ],
    }


def _counterparty_handoff_columns(
    counterparties: tuple[CvaCounterparty, ...],
) -> dict[str, object]:
    return {
        "counterparty_id": [item.counterparty_id for item in counterparties],
        "desk_id": [item.desk_id for item in counterparties],
        "legal_entity": [item.legal_entity for item in counterparties],
        "sector": [item.sector.value for item in counterparties],
        "credit_quality": [item.credit_quality.value for item in counterparties],
        "region": [item.region for item in counterparties],
        "source_row_id": [item.source_row_id for item in counterparties],
        "lineage_source_system": [
            "" if item.lineage is None else item.lineage.source_system for item in counterparties
        ],
        "lineage_source_file": [
            "" if item.lineage is None else item.lineage.source_file for item in counterparties
        ],
        "lineage_source_row_id": [
            item.source_row_id if item.lineage is None else item.lineage.source_row_id
            for item in counterparties
        ],
    }


def _netting_set_handoff_columns(netting_sets: tuple[CvaNettingSet, ...]) -> dict[str, object]:
    return {
        "netting_set_id": [item.netting_set_id for item in netting_sets],
        "counterparty_id": [item.counterparty_id for item in netting_sets],
        "ead": [item.ead for item in netting_sets],
        "effective_maturity": [item.effective_maturity for item in netting_sets],
        "discount_factor": [item.discount_factor for item in netting_sets],
        "currency": [item.currency for item in netting_sets],
        "sign_convention": [item.sign_convention for item in netting_sets],
        "uses_imm_ead": [item.uses_imm_ead for item in netting_sets],
        "source_row_id": [item.source_row_id for item in netting_sets],
        "carved_out_to_ba_cva": [item.carved_out_to_ba_cva for item in netting_sets],
        "discount_factor_explicit": [item.discount_factor_explicit for item in netting_sets],
        "lineage_source_system": [
            "" if item.lineage is None else item.lineage.source_system for item in netting_sets
        ],
        "lineage_source_file": [
            "" if item.lineage is None else item.lineage.source_file for item in netting_sets
        ],
        "lineage_source_row_id": [
            item.source_row_id if item.lineage is None else item.lineage.source_row_id
            for item in netting_sets
        ],
    }


def _payload_hash(result: CvaCapitalResult) -> str:
    payload = serialize_cva_result(result)
    return hashlib.sha256(
        bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8")
    ).hexdigest()


def write_report(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    report = run_benchmark(
        CvaBenchmarkConfig(
            counterparties=args.counterparties,
            netting_sets=args.netting_sets,
            sensitivities=args.sensitivities,
        )
    )
    write_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
