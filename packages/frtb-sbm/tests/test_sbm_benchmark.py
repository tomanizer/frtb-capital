from __future__ import annotations

import time
from datetime import date

from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
)


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
