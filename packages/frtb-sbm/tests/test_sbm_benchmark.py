from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date

import pyarrow as pa
from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    WeightedSensitivity,
    calculate_sbm_capital,
)
from frtb_sbm.aggregation import adjust_correlation_matrix_for_scenario
from frtb_sbm.arrow_handoff import (
    calculate_sbm_capital_from_commodity_delta_handoff,
    calculate_sbm_capital_from_csr_nonsec_delta_handoff,
    calculate_sbm_capital_from_equity_delta_handoff,
    calculate_sbm_capital_from_fx_delta_handoff,
    calculate_sbm_capital_from_girr_vega_handoff,
    normalize_commodity_delta_arrow_table,
    normalize_csr_nonsec_delta_arrow_table,
    normalize_equity_delta_arrow_table,
    normalize_fx_delta_arrow_table,
    normalize_girr_vega_arrow_table,
)
from frtb_sbm.capital import _build_girr_delta_intra_bucket_correlation_matrix


def _large_girr_delta_portfolio(size: int) -> tuple[SbmSensitivity, ...]:
    sensitivities: list[SbmSensitivity] = []
    for index in range(size):
        sensitivities.append(
            SbmSensitivity(
                sensitivity_id=f"girr-{index:05d}",
                source_row_id=f"row-{index:05d}",
                desk_id="rates-desk",
                legal_entity="LE-001",
                risk_class=SbmRiskClass.GIRR,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=str((index % 3) + 1),
                risk_factor="USD" if index % 2 == 0 else "EUR",
                amount=100_000.0 + index,
                amount_currency="USD",
                tenor="5y" if index % 2 == 0 else "1y",
                sign_convention=SbmSignConvention.RECEIVE,
                lineage=SbmSourceLineage(
                    source_system="benchmark",
                    source_file="synthetic.json",
                    source_row_id=f"row-{index:05d}",
                ),
            )
        )
    return tuple(sensitivities)


def test_large_synthetic_girr_delta_portfolio_benchmark() -> None:
    """Documented synthetic benchmark: 500 GIRR delta rows should finish quickly."""

    context = SbmCalculationContext(
        run_id="run-benchmark-001",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    sensitivities = _large_girr_delta_portfolio(500)
    started = time.perf_counter()
    result = calculate_sbm_capital(sensitivities, context=context)
    elapsed = time.perf_counter() - started

    assert result.total_capital > 0.0
    assert elapsed < 5.0


def test_girr_delta_matrix_and_scenario_phase_benchmark(
    record_property: Callable[[str, object], None],
) -> None:
    """Report matrix/scenario timings separately from ingestion and audit serialization."""

    factor_count = 240
    weighted, tenor_by_id, risk_factor_by_id = _girr_delta_factor_grid(factor_count)

    matrix_started = time.perf_counter()
    matrix = _build_girr_delta_intra_bucket_correlation_matrix(
        weighted,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        tenor_by_id=tenor_by_id,
        risk_factor_by_id=risk_factor_by_id,
    )
    matrix_elapsed = time.perf_counter() - matrix_started

    scenario_started = time.perf_counter()
    adjusted = tuple(
        adjust_correlation_matrix_for_scenario(matrix, scenario)
        for scenario in (
            SbmScenarioLabel.LOW,
            SbmScenarioLabel.MEDIUM,
            SbmScenarioLabel.HIGH,
        )
    )
    scenario_elapsed = time.perf_counter() - scenario_started

    record_property("girr_delta_factor_count", factor_count)
    record_property("girr_delta_matrix_seconds", matrix_elapsed)
    record_property("girr_delta_scenario_seconds", scenario_elapsed)
    assert matrix.shape == (factor_count, factor_count)
    assert len(adjusted) == 3
    assert matrix_elapsed < 1.0
    assert scenario_elapsed < 1.0


def test_girr_vega_arrow_batch_phase_benchmark(
    record_property: Callable[[str, object], None],
) -> None:
    """Report GIRR vega Arrow handoff timing without accepted-row dataclasses."""

    context = SbmCalculationContext(
        run_id="run-benchmark-vega-001",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    row_count = 300
    table = _large_girr_vega_arrow_table(row_count)

    ingestion_started = time.perf_counter()
    handoff = normalize_girr_vega_arrow_table(table)
    ingestion_elapsed = time.perf_counter() - ingestion_started

    compute_started = time.perf_counter()
    result = calculate_sbm_capital_from_girr_vega_handoff(handoff, context=context)
    compute_elapsed = time.perf_counter() - compute_started

    record_property("girr_vega_raw_row_count", row_count)
    record_property("girr_vega_ingestion_seconds", ingestion_elapsed)
    record_property("girr_vega_compute_seconds", compute_elapsed)
    record_property("girr_vega_materialized_dataclass_count", 0)
    assert handoff.accepted.num_rows == row_count
    assert result.total_capital > 0.0
    assert ingestion_elapsed < 1.0
    assert compute_elapsed < 5.0


def test_non_credit_delta_arrow_batch_phase_benchmark(
    record_property: Callable[[str, object], None],
) -> None:
    """Report FX, equity, and commodity Arrow handoff timings without row dataclasses."""

    cases = (
        (
            "fx",
            _large_fx_delta_arrow_table(240),
            normalize_fx_delta_arrow_table,
            calculate_sbm_capital_from_fx_delta_handoff,
        ),
        (
            "equity",
            _large_equity_delta_arrow_table(240),
            normalize_equity_delta_arrow_table,
            calculate_sbm_capital_from_equity_delta_handoff,
        ),
        (
            "commodity",
            _large_commodity_delta_arrow_table(240),
            normalize_commodity_delta_arrow_table,
            calculate_sbm_capital_from_commodity_delta_handoff,
        ),
    )
    for label, table, normalizer, calculator in cases:
        context = SbmCalculationContext(
            run_id=f"run-benchmark-{label}-delta-001",
            calculation_date=date(2026, 5, 30),
            base_currency="USD",
            reporting_currency="USD",
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        )
        ingestion_started = time.perf_counter()
        handoff = normalizer(table)
        ingestion_elapsed = time.perf_counter() - ingestion_started

        compute_started = time.perf_counter()
        result = calculator(handoff, context=context)
        compute_elapsed = time.perf_counter() - compute_started

        record_property(f"{label}_delta_raw_row_count", table.num_rows)
        record_property(f"{label}_delta_ingestion_seconds", ingestion_elapsed)
        record_property(f"{label}_delta_compute_seconds", compute_elapsed)
        record_property(f"{label}_delta_materialized_dataclass_count", 0)
        assert handoff.accepted.num_rows == table.num_rows
        assert result.total_capital > 0.0
        assert ingestion_elapsed < 1.0
        assert compute_elapsed < 5.0


def test_csr_delta_arrow_batch_phase_benchmark(
    record_property: Callable[[str, object], None],
) -> None:
    """Report CSR Arrow handoff timing without accepted-row dataclasses."""

    context = SbmCalculationContext(
        run_id="run-benchmark-csr-nonsec-delta-001",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    row_count = 240
    table = _large_csr_nonsec_delta_arrow_table(row_count)

    ingestion_started = time.perf_counter()
    handoff = normalize_csr_nonsec_delta_arrow_table(table)
    ingestion_elapsed = time.perf_counter() - ingestion_started

    compute_started = time.perf_counter()
    result = calculate_sbm_capital_from_csr_nonsec_delta_handoff(handoff, context=context)
    compute_elapsed = time.perf_counter() - compute_started

    record_property("csr_nonsec_delta_raw_row_count", row_count)
    record_property("csr_nonsec_delta_ingestion_seconds", ingestion_elapsed)
    record_property("csr_nonsec_delta_compute_seconds", compute_elapsed)
    record_property("csr_nonsec_delta_materialized_dataclass_count", 0)
    assert handoff.accepted.num_rows == row_count
    assert result.total_capital > 0.0
    assert ingestion_elapsed < 1.0
    assert compute_elapsed < 5.0


def _large_girr_vega_arrow_table(size: int) -> pa.Table:
    option_tenors = ("1y", "2y", "5y", "10y")
    tenors = ("1y", "2y", "5y", "10y", "30y")
    return pa.table(
        {
            "sensitivity_id": [f"vega-{index:05d}" for index in range(size)],
            "source_row_id": [f"row-vega-{index:05d}" for index in range(size)],
            "desk_id": ["rates-desk"] * size,
            "legal_entity": ["LE-001"] * size,
            "risk_class": ["GIRR"] * size,
            "risk_measure": ["VEGA"] * size,
            "bucket": [str((index % 3) + 1) for index in range(size)],
            "risk_factor": ["USD"] * size,
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "amount_currency": ["USD"] * size,
            "sign_convention": ["RECEIVE"] * size,
            "tenor": [tenors[index % len(tenors)] for index in range(size)],
            "option_tenor": [option_tenors[index % len(option_tenors)] for index in range(size)],
            "lineage_source_system": ["benchmark"] * size,
            "lineage_source_file": ["synthetic-vega.arrow"] * size,
        }
    )


def _large_fx_delta_arrow_table(size: int) -> pa.Table:
    currencies = ("EUR", "GBP", "JPY", "AUD", "CAD", "CHF")
    return pa.table(
        {
            "sensitivity_id": [f"fx-{index:05d}" for index in range(size)],
            "source_row_id": [f"row-fx-{index:05d}" for index in range(size)],
            "desk_id": ["fx-desk"] * size,
            "legal_entity": ["LE-001"] * size,
            "risk_class": ["FX"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [currencies[index % len(currencies)] for index in range(size)],
            "risk_factor": [currencies[index % len(currencies)] for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "amount_currency": ["USD"] * size,
            "sign_convention": ["LONG"] * size,
            "lineage_source_system": ["benchmark"] * size,
            "lineage_source_file": ["synthetic-fx.arrow"] * size,
        }
    )


def _large_equity_delta_arrow_table(size: int) -> pa.Table:
    buckets = ("5", "6", "7", "8", "11")
    factors = ("SPOT", "REPO")
    return pa.table(
        {
            "sensitivity_id": [f"eq-{index:05d}" for index in range(size)],
            "source_row_id": [f"row-eq-{index:05d}" for index in range(size)],
            "desk_id": ["eq-desk"] * size,
            "legal_entity": ["LE-001"] * size,
            "risk_class": ["EQUITY"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [buckets[index % len(buckets)] for index in range(size)],
            "risk_factor": [factors[index % len(factors)] for index in range(size)],
            "qualifier": [f"ISS-{index % 37:02d}" for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "amount_currency": ["USD"] * size,
            "sign_convention": ["LONG"] * size,
            "lineage_source_system": ["benchmark"] * size,
            "lineage_source_file": ["synthetic-equity.arrow"] * size,
        }
    )


def _large_commodity_delta_arrow_table(size: int) -> pa.Table:
    buckets = ("2", "3", "5", "6", "10")
    commodities = ("WTI", "BRENT", "ALU", "GOLD", "POWER")
    locations = ("NYMEX", "ICE", "LME")
    tenors = ("3m", "6m", "1y", "2y")
    return pa.table(
        {
            "sensitivity_id": [f"com-{index:05d}" for index in range(size)],
            "source_row_id": [f"row-com-{index:05d}" for index in range(size)],
            "desk_id": ["com-desk"] * size,
            "legal_entity": ["LE-001"] * size,
            "risk_class": ["COMMODITY"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [buckets[index % len(buckets)] for index in range(size)],
            "risk_factor": [commodities[index % len(commodities)] for index in range(size)],
            "qualifier": [locations[index % len(locations)] for index in range(size)],
            "tenor": [tenors[index % len(tenors)] for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "amount_currency": ["USD"] * size,
            "sign_convention": ["LONG"] * size,
            "lineage_source_system": ["benchmark"] * size,
            "lineage_source_file": ["synthetic-commodity.arrow"] * size,
        }
    )


def _large_csr_nonsec_delta_arrow_table(size: int) -> pa.Table:
    buckets = ("4", "5", "6", "12", "17")
    risk_factors = ("BOND", "CDS")
    tenors = ("6m", "1y", "3y", "5y", "10y")
    return pa.table(
        {
            "sensitivity_id": [f"csr-ns-{index:05d}" for index in range(size)],
            "source_row_id": [f"row-csr-ns-{index:05d}" for index in range(size)],
            "desk_id": ["credit-desk"] * size,
            "legal_entity": ["LE-001"] * size,
            "risk_class": ["CSR_NONSEC"] * size,
            "risk_measure": ["DELTA"] * size,
            "bucket": [buckets[index % len(buckets)] for index in range(size)],
            "risk_factor": [risk_factors[index % len(risk_factors)] for index in range(size)],
            "qualifier": [f"ISS-{index % 43:02d}" for index in range(size)],
            "tenor": [tenors[index % len(tenors)] for index in range(size)],
            "amount": pa.array([100_000.0 + index for index in range(size)], type=pa.float64()),
            "amount_currency": ["USD"] * size,
            "sign_convention": ["LONG"] * size,
            "lineage_source_system": ["benchmark"] * size,
            "lineage_source_file": ["synthetic-csr-nonsec.arrow"] * size,
        }
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
