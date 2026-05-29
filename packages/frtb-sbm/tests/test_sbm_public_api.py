from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmCalculationContext,
    SbmCapitalResult,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
)


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=row_id,
        source_column_map=(("DeltaUSD", "amount"),),
    )


def sample_sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    bucket: str,
    risk_factor: str,
    tenor: str,
    amount: float,
    desk_id: str = "rates-desk",
    legal_entity: str = "LE-001",
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id=desk_id,
        legal_entity=legal_entity,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=amount,
        amount_currency="USD",
        tenor=tenor,
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage(source_row_id),
    )


def sample_context(
    profile: SbmRegulatoryProfile = SbmRegulatoryProfile.BASEL_MAR21,
) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-run-001",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=profile.value,
    )


def test_calculate_sbm_capital_returns_public_result_for_supported_inputs() -> None:
    result = calculate_sbm_capital(
        (
            sample_sensitivity(
                sensitivity_id="eur-1y",
                source_row_id="row-001",
                bucket="1",
                risk_factor="EUR",
                tenor="1y",
                amount=1_000_000.0,
            ),
            sample_sensitivity(
                sensitivity_id="eur-5y",
                source_row_id="row-002",
                bucket="1",
                risk_factor="EUR",
                tenor="5y",
                amount=500_000.0,
            ),
            sample_sensitivity(
                sensitivity_id="usd-5y",
                source_row_id="row-003",
                bucket="2",
                risk_factor="USD",
                tenor="5y",
                amount=800_000.0,
            ),
        ),
        context=sample_context(),
    )

    assert isinstance(result, SbmCapitalResult)
    assert result.profile_id == "BASEL_MAR21"
    assert re.fullmatch(r"[0-9a-f]{64}", result.profile_hash)
    assert re.fullmatch(r"[0-9a-f]{64}", result.input_hash)
    assert len(result.risk_classes) == 1
    girr = result.risk_classes[0]
    assert girr.risk_class is SbmRiskClass.GIRR
    assert girr.risk_measure is SbmRiskMeasure.DELTA
    assert girr.selected_scenario is not None
    assert girr.scenario_totals is not None
    assert len(girr.buckets) == 2
    assert result.total_capital == girr.selected_capital
    assert result.total_capital == pytest.approx(max(girr.scenario_totals.values()))
    assert result.reconciliation is not None
    assert result.reconciliation.input_count == 3
    assert "SBM-AUDIT-001" in result.reconciliation.requirement_ids

    payload = result.as_dict()
    assert payload["total_capital"] == result.total_capital
    assert payload["profile_id"] == "BASEL_MAR21"
    with pytest.raises(FrozenInstanceError):
        setattr(result, "total_capital", 0.0)


def test_calculate_sbm_capital_requires_context() -> None:
    with pytest.raises(SbmInputError, match="calculation context is required"):
        calculate_sbm_capital(())


def test_calculate_sbm_capital_requires_sensitivities() -> None:
    with pytest.raises(SbmInputError, match="sensitivities are required"):
        calculate_sbm_capital(context=sample_context())


def test_calculate_sbm_capital_validates_context_shape() -> None:
    sensitivity = sample_sensitivity(
        sensitivity_id="eur-1y",
        source_row_id="row-001",
        bucket="1",
        risk_factor="EUR",
        tenor="1y",
        amount=1_000_000.0,
    )

    with pytest.raises(SbmInputError, match="calculation context must be SbmCalculationContext"):
        calculate_sbm_capital((sensitivity,), context=object())  # type: ignore[arg-type]


def test_calculate_sbm_capital_fails_closed_for_unsupported_profiles() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        calculate_sbm_capital(
            (
                sample_sensitivity(
                    sensitivity_id="eur-1y",
                    source_row_id="row-001",
                    bucket="1",
                    risk_factor="EUR",
                    tenor="1y",
                    amount=1_000_000.0,
                ),
            ),
            context=sample_context(SbmRegulatoryProfile.US_NPR_2_0),
        )


@pytest.mark.parametrize(
    ("risk_measure", "risk_class"),
    [
        (SbmRiskMeasure.VEGA, SbmRiskClass.GIRR),
        (SbmRiskMeasure.DELTA, SbmRiskClass.FX),
    ],
)
def test_calculate_sbm_capital_fails_closed_for_unsupported_paths(
    risk_measure: SbmRiskMeasure,
    risk_class: SbmRiskClass,
) -> None:
    sensitivity = SbmSensitivity(
        sensitivity_id="unsupported-001",
        source_row_id="row-001",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=risk_class,
        risk_measure=risk_measure,
        bucket="1",
        risk_factor="EUR",
        amount=1_000_000.0,
        amount_currency="USD",
        tenor="1y",
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage("row-001"),
    )

    with pytest.raises(UnsupportedRegulatoryFeatureError):
        calculate_sbm_capital((sensitivity,), context=sample_context())


def test_calculate_sbm_capital_selects_max_correlation_scenario() -> None:
    result = calculate_sbm_capital(
        (
            sample_sensitivity(
                sensitivity_id="eur-1y",
                source_row_id="row-001",
                bucket="1",
                risk_factor="EUR",
                tenor="1y",
                amount=1_000_000.0,
            ),
            sample_sensitivity(
                sensitivity_id="usd-5y",
                source_row_id="row-002",
                bucket="2",
                risk_factor="USD",
                tenor="5y",
                amount=800_000.0,
            ),
        ),
        context=sample_context(),
    )
    girr = result.risk_classes[0]
    assert girr.selected_scenario is not None
    assert girr.scenario_totals is not None
    assert girr.selected_scenario == max(
        girr.scenario_totals,
        key=lambda label: girr.scenario_totals[label],
    )
    assert girr.selected_scenario in {
        SbmScenarioLabel.LOW,
        SbmScenarioLabel.MEDIUM,
        SbmScenarioLabel.HIGH,
    }
