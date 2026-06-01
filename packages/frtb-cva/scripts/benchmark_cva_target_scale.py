"""Synthetic large-scale CVA benchmark without dataframe dependencies."""

from __future__ import annotations

import hashlib
import json
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
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
    calculate_cva_capital,
    calculate_cva_capital_from_batches,
    normalize_cva_counterparty_arrow_table,
    normalize_cva_netting_set_arrow_table,
    serialize_cva_result,
)

T = TypeVar("T")


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


def run_benchmark(config: CvaBenchmarkConfig) -> dict[str, object]:
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
    counterparty_table = pa.table(_counterparty_handoff_columns(counterparties))
    netting_set_table = pa.table(_netting_set_handoff_columns(netting_sets))
    arrow_ba_build = _measure(
        lambda: (
            build_cva_counterparty_batch_from_handoff(
                normalize_cva_counterparty_arrow_table(counterparty_table)
            ),
            build_cva_netting_set_batch_from_handoff(
                normalize_cva_netting_set_arrow_table(netting_set_table)
            ),
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

    return {
        "parameters": {
            "counterparties": config.counterparties,
            "netting_sets": config.netting_sets,
            "sensitivities": config.sensitivities,
        },
        "timings": {
            "ba_row_calculate_seconds": row_ba.seconds,
            "ba_column_build_seconds": column_ba_build.seconds,
            "ba_column_calculate_seconds": column_ba.seconds,
            "ba_arrow_build_seconds": arrow_ba_build.seconds,
            "ba_arrow_calculate_seconds": arrow_ba.seconds,
            "sa_row_calculate_seconds": row_sa.seconds,
            "sa_column_build_seconds": column_sa_build.seconds,
            "sa_column_calculate_seconds": column_sa.seconds,
        },
        "memory": {
            "ba_row_peak_bytes": row_ba.peak_bytes,
            "ba_column_build_peak_bytes": column_ba_build.peak_bytes,
            "ba_column_calculate_peak_bytes": column_ba.peak_bytes,
            "ba_arrow_build_peak_bytes": arrow_ba_build.peak_bytes,
            "ba_arrow_calculate_peak_bytes": arrow_ba.peak_bytes,
            "sa_row_peak_bytes": row_sa.peak_bytes,
            "sa_column_build_peak_bytes": column_sa_build.peak_bytes,
            "sa_column_calculate_peak_bytes": column_sa.peak_bytes,
        },
        "dataclasses_materialized": _dataclass_counts(column_ba, arrow_ba, column_sa),
        "result": {
            "ba_total_cva_capital": row_ba.value.total_cva_capital,
            "ba_row_payload_hash": _payload_hash(row_ba.value),
            "ba_column_payload_hash": _payload_hash(column_ba.value.result),
            "ba_arrow_payload_hash": _payload_hash(arrow_ba.value.result),
            "ba_column_capital_delta": abs(
                column_ba.value.result.total_cva_capital - row_ba.value.total_cva_capital
            ),
            "ba_arrow_capital_delta": abs(
                arrow_ba.value.result.total_cva_capital - row_ba.value.total_cva_capital
            ),
            "sa_total_cva_capital": row_sa.value.total_cva_capital,
            "sa_row_payload_hash": _payload_hash(row_sa.value),
            "sa_column_payload_hash": _payload_hash(column_sa.value.result),
            "sa_column_capital_delta": abs(
                column_sa.value.result.total_cva_capital - row_sa.value.total_cva_capital
            ),
        },
    }


def _measure(fn: Callable[[], T]) -> TimedResult[T]:
    tracemalloc.start()
    started = time.perf_counter()
    value = fn()
    seconds = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return TimedResult(value=value, seconds=seconds, peak_bytes=peak_bytes)


def _dataclass_counts(
    column_ba: Any,
    arrow_ba: Any,
    column_sa: Any,
) -> dict[str, int]:
    column_ba_value = column_ba.value
    arrow_ba_value = arrow_ba.value
    column_sa_value = column_sa.value
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


if __name__ == "__main__":
    print(json.dumps(run_benchmark(CvaBenchmarkConfig(netting_sets=1_000)), indent=2))
