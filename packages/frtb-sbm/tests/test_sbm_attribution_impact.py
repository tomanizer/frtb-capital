from __future__ import annotations

from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmCalculationContext,
    SbmCapitalResult,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
)
from frtb_sbm.attribution import (
    attribution_placeholder_for_result,
    ensure_sbm_attribution_unsupported,
)
from frtb_sbm.impact import ensure_sbm_impact_unsupported, impact_placeholder_for_results


def test_attribution_status_is_structured_and_non_capital_producing() -> None:
    result = _sample_result()

    status = attribution_placeholder_for_result(result)

    assert status.status == "unsupported"
    assert status.requirement_id == "SBM-FUNC-022"
    assert "Analytical Euler contribution" in status.reason


def test_attribution_request_fails_closed() -> None:
    with pytest.raises(
        UnsupportedRegulatoryFeatureError,
        match=r"analytical Euler attribution is unsupported \(SBM-FUNC-022\)",
    ):
        ensure_sbm_attribution_unsupported(_sample_result())


def test_impact_status_is_structured_and_non_capital_producing() -> None:
    baseline = _sample_result(run_id="sbm-baseline")
    candidate = _sample_result(run_id="sbm-candidate", amount=1_500_000.0)

    status = impact_placeholder_for_results(baseline, candidate)

    assert status.status == "unsupported"
    assert status.requirement_id == "SBM-FUNC-022"
    assert "Finite-difference capital impact" in status.reason


def test_impact_request_fails_closed() -> None:
    baseline = _sample_result(run_id="sbm-baseline")
    candidate = _sample_result(run_id="sbm-candidate", amount=1_500_000.0)

    with pytest.raises(
        UnsupportedRegulatoryFeatureError,
        match=r"capital impact analysis is unsupported \(SBM-FUNC-022\)",
    ):
        ensure_sbm_impact_unsupported(baseline, candidate)


def _sample_result(*, run_id: str = "sbm-run", amount: float = 1_000_000.0) -> SbmCapitalResult:
    sensitivity = SbmSensitivity(
        sensitivity_id=f"{run_id}-eur-1y",
        source_row_id=f"{run_id}-row-001",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="1",
        risk_factor="EUR",
        tenor="1y",
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=SbmSourceLineage(
            source_system="synthetic-risk",
            source_file="sbm.csv",
            source_row_id=f"{run_id}-row-001",
            source_column_map=(("DeltaUSD", "amount"),),
        ),
    )
    context = SbmCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id="BASEL_MAR21",
    )
    return calculate_sbm_capital((sensitivity,), context=context)
