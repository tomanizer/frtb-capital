"""Additional SBM analytical Euler attribution coverage for issue #607."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import date

import pytest
from frtb_common.attribution import AttributionMethod, CapitalContribution
from frtb_sbm import (
    SbmCalculationContext,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
)
from frtb_sbm.attribution import calculate_sbm_attribution


def test_multi_risk_class_delta_euler_records_reconcile_by_risk_class() -> None:
    sensitivities = (
        _girr_delta(
            "girr-eur-1y",
            bucket="1",
            risk_factor="EUR",
            tenor="1y",
            amount=1_000_000.0,
        ),
        _girr_delta(
            "girr-usd-5y",
            bucket="2",
            risk_factor="USD",
            tenor="5y",
            amount=700_000.0,
        ),
        _fx_delta("fx-eur", bucket="EUR", risk_factor="EUR", amount=350_000.0),
        _fx_delta("fx-usd", bucket="USD", risk_factor="USD", amount=450_000.0),
    )

    result = calculate_sbm_capital(sensitivities, context=_context("multi-risk"))
    records = calculate_sbm_attribution(result)

    categories = set()
    for record in records:
        categories.add(record.category)
        assert record.method == AttributionMethod.ANALYTICAL_EULER
    assert categories == {"FX", "GIRR"}
    assert _record_total(records) == pytest.approx(
        result.total_capital,
        rel=1e-6,
        abs=1e-6,
    )

    for risk_class in result.risk_classes:
        risk_class_records: list[CapitalContribution] = []
        for record in records:
            if record.category == str(risk_class.risk_class):
                risk_class_records.append(record)
        assert _record_total(tuple(risk_class_records)) == pytest.approx(
            risk_class.selected_capital,
            rel=1e-6,
            abs=1e-6,
        )


def test_selected_scenario_matches_maximum_scenario_total_for_girr_delta() -> None:
    sensitivities = (
        _girr_delta(
            "girr-eur-1y",
            bucket="1",
            risk_factor="EUR",
            tenor="1y",
            amount=1_000_000.0,
        ),
        _girr_delta(
            "girr-usd-5y",
            bucket="2",
            risk_factor="USD",
            tenor="5y",
            amount=700_000.0,
        ),
        _girr_delta(
            "girr-gbp-10y",
            bucket="3",
            risk_factor="GBP",
            tenor="10y",
            amount=500_000.0,
        ),
    )

    result = calculate_sbm_capital(sensitivities, context=_context("scenario-stability"))
    risk_class = result.risk_classes[0]
    assert risk_class.risk_class == SbmRiskClass.GIRR
    assert risk_class.selected_scenario is not None
    scenario_totals = risk_class.scenario_totals
    assert scenario_totals is not None

    selected_total = scenario_totals[risk_class.selected_scenario]
    maximum_total = max(scenario_totals.values())
    assert selected_total == pytest.approx(maximum_total, rel=1e-6, abs=1e-6)
    assert risk_class.selected_scenario in {
        SbmScenarioLabel.LOW,
        SbmScenarioLabel.MEDIUM,
        SbmScenarioLabel.HIGH,
    }

    records = calculate_sbm_attribution(result)
    assert _record_total(records) == pytest.approx(
        risk_class.selected_capital,
        rel=1e-6,
        abs=1e-6,
    )


def test_negative_girr_sensitivity_can_reduce_euler_capital_contribution() -> None:
    sensitivities = (
        _girr_delta(
            "girr-eur-1y-long",
            bucket="1",
            risk_factor="EUR",
            tenor="1y",
            amount=2_000_000.0,
        ),
        _girr_delta(
            "girr-eur-2y-short",
            bucket="1",
            risk_factor="EUR",
            tenor="2y",
            amount=-500_000.0,
        ),
    )

    result = calculate_sbm_capital(sensitivities, context=_context("negative-euler"))
    records = calculate_sbm_attribution(result)
    euler: list[CapitalContribution] = []
    for record in records:
        if record.method == AttributionMethod.ANALYTICAL_EULER:
            euler.append(record)

    negative_contribution_found = False
    for record in euler:
        if record.contribution is not None and record.contribution < 0.0:
            negative_contribution_found = True

    assert len(euler) == 2
    assert negative_contribution_found
    assert _record_total(records) == pytest.approx(
        result.total_capital,
        rel=1e-6,
        abs=1e-6,
    )


def test_multi_risk_class_finite_difference_matches_euler_derivatives() -> None:
    sensitivities = (
        _girr_delta(
            "girr-eur-1y",
            bucket="1",
            risk_factor="EUR",
            tenor="1y",
            amount=900_000.0,
        ),
        _girr_delta(
            "girr-usd-5y",
            bucket="2",
            risk_factor="USD",
            tenor="5y",
            amount=650_000.0,
        ),
        _fx_delta("fx-eur", bucket="EUR", risk_factor="EUR", amount=300_000.0),
    )

    result = calculate_sbm_capital(sensitivities, context=_context("finite-diff"))
    records: list[CapitalContribution] = []
    for record in calculate_sbm_attribution(result):
        if record.method == AttributionMethod.ANALYTICAL_EULER:
            records.append(record)

    raw_amount_by_id = {}
    for sensitivity in sensitivities:
        raw_amount_by_id[sensitivity.sensitivity_id] = sensitivity.amount
    bump = 100.0

    for record in records:
        assert record.contribution is not None
        assert record.marginal_multiplier is not None
        raw_amount = raw_amount_by_id[record.source_id]
        risk_weight = record.base_amount / raw_amount
        bumped_items = []
        for sensitivity in sensitivities:
            if sensitivity.sensitivity_id == record.source_id:
                bumped_items.append(replace(sensitivity, amount=sensitivity.amount + bump))
            else:
                bumped_items.append(sensitivity)
        bumped = tuple(bumped_items)
        bumped_result = calculate_sbm_capital(
            bumped,
            context=_context(f"bumped-{record.source_id}"),
        )
        finite_difference = (bumped_result.total_capital - result.total_capital) / bump
        analytical_raw_derivative = record.marginal_multiplier * risk_weight
        assert finite_difference == pytest.approx(
            analytical_raw_derivative,
            rel=1e-4,
            abs=1e-6,
        )


def _context(run_id: str) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 6, 10),
        base_currency="USD",
        reporting_currency="USD",
        profile_id="BASEL_MAR21",
        desk_id="rates-desk",
    )


def _lineage(sensitivity_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm-attribution.csv",
        source_row_id=f"row-{sensitivity_id}",
        source_column_map=(("amount_usd", "amount"),),
    )


def _girr_delta(
    sensitivity_id: str,
    *,
    bucket: str,
    risk_factor: str,
    tenor: str,
    amount: float,
) -> SbmSensitivity:
    sign_convention = SbmSignConvention.RECEIVE
    if amount < 0.0:
        sign_convention = SbmSignConvention.SHORT

    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=f"row-{sensitivity_id}",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        tenor=tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention=sign_convention,
        lineage=_lineage(sensitivity_id),
    )


def _fx_delta(
    sensitivity_id: str,
    *,
    bucket: str,
    risk_factor: str,
    amount: float,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=f"row-{sensitivity_id}",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=_lineage(sensitivity_id),
    )


def _record_total(records: tuple[CapitalContribution, ...]) -> float:
    total = 0.0
    for record in records:
        contribution = record.contribution
        if contribution is None:
            contribution = 0.0
        total = math.fsum((total, contribution, record.residual))
    return total
