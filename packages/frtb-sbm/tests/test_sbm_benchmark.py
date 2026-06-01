from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date

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
