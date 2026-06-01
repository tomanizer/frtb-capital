from __future__ import annotations

import math
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
    compute_weighted_sensitivities,
    non_girr_vega_intra_bucket_correlation,
    weight_non_girr_vega_sensitivities,
)


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm-vega.csv",
        source_row_id=row_id,
        source_column_map=(("amount", "amount"),),
    )


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-non-girr-vega-run",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def sample_vega_sensitivity(
    *,
    sensitivity_id: str,
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factor: str,
    qualifier: str | None = None,
    option_tenor: str | None = "1y",
    amount: float = 100_000.0,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=f"row-{sensitivity_id}",
        desk_id="vega-desk",
        legal_entity="LE-001",
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.VEGA,
        bucket=bucket,
        risk_factor=risk_factor,
        qualifier=qualifier,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=sample_lineage(f"row-{sensitivity_id}"),
        option_tenor=option_tenor,
    )


@pytest.mark.parametrize(
    ("risk_class", "bucket", "risk_factor", "qualifier", "expected_horizon"),
    [
        (SbmRiskClass.FX, "EUR", "EUR", None, 40),
        (SbmRiskClass.EQUITY, "5", "SPOT", "ISS-A", 20),
        (SbmRiskClass.COMMODITY, "2", "WTI", None, 120),
        (SbmRiskClass.CSR_NONSEC, "4", "BOND", "ISS-A", 120),
        (SbmRiskClass.CSR_SEC_NONCTP, "1", "BOND", "TR-A", 120),
        (SbmRiskClass.CSR_SEC_CTP, "4", "BOND", "UND-A", 120),
    ],
)
def test_calculate_sbm_capital_supports_each_non_girr_vega_risk_class(
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factor: str,
    qualifier: str | None,
    expected_horizon: int,
) -> None:
    sensitivity = sample_vega_sensitivity(
        sensitivity_id=f"{risk_class.value.lower()}-vega",
        risk_class=risk_class,
        bucket=bucket,
        risk_factor=risk_factor,
        qualifier=qualifier,
    )

    result = calculate_sbm_capital((sensitivity,), context=sample_context())
    risk_class_result = result.risk_classes[0]
    weighted = risk_class_result.buckets[0].weighted_sensitivities[0]

    assert risk_class_result.risk_class is risk_class
    assert risk_class_result.risk_measure is SbmRiskMeasure.VEGA
    assert risk_class_result.selected_capital == pytest.approx(
        max(result.risk_classes[0].scenario_totals.values())
    )
    assert set(risk_class_result.scenario_totals) == {
        SbmScenarioLabel.LOW,
        SbmScenarioLabel.MEDIUM,
        SbmScenarioLabel.HIGH,
    }
    assert len(risk_class_result.scenario_details) == 3
    assert weighted.liquidity_horizon_days == expected_horizon
    assert "basel_mar21_90" in weighted.citation_ids
    assert "basel_mar21_92" in weighted.citation_ids
    assert "basel_mar21_94" in risk_class_result.citation_ids
    assert "basel_mar21_95" in risk_class_result.citation_ids


def test_non_girr_vega_weighting_routes_through_generic_entrypoint() -> None:
    sensitivity = sample_vega_sensitivity(
        sensitivity_id="eq-vega-large",
        risk_class=SbmRiskClass.EQUITY,
        bucket="5",
        risk_factor="SPOT",
        qualifier="ISS-A",
    )

    direct = weight_non_girr_vega_sensitivities(
        (sensitivity,),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    routed = compute_weighted_sensitivities(
        (sensitivity,),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    assert routed == direct
    assert routed[0].risk_weight == pytest.approx(0.55 * math.sqrt(20.0 / 10.0))
    assert routed[0].factor_key == ("5", "ISS-A", "SPOT", "1y")


@pytest.mark.parametrize(
    (
        "risk_class",
        "bucket",
        "risk_factor_a",
        "risk_factor_b",
        "qualifier_a",
        "qualifier_b",
        "expected_delta_correlation",
    ),
    [
        (SbmRiskClass.FX, "EUR", "EUR", "EUR", "", "", 1.0),
        (SbmRiskClass.EQUITY, "5", "SPOT", "SPOT", "ISS-A", "ISS-B", 0.25),
        (SbmRiskClass.COMMODITY, "2", "WTI", "BRENT", "", "", 0.95),
        (SbmRiskClass.CSR_NONSEC, "4", "BOND", "CDS", "ISS-A", "ISS-B", 0.35 * 0.999),
        (SbmRiskClass.CSR_SEC_NONCTP, "1", "BOND", "CDS", "TR-A", "TR-B", 0.40 * 0.999),
        (SbmRiskClass.CSR_SEC_CTP, "4", "BOND", "CDS", "UND-A", "UND-B", 0.35 * 0.99),
    ],
)
def test_non_girr_vega_intra_bucket_correlation_is_delta_rho_times_option_rho(
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factor_a: str,
    risk_factor_b: str,
    qualifier_a: str,
    qualifier_b: str,
    expected_delta_correlation: float,
) -> None:
    correlation, citation_ids = non_girr_vega_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        risk_class=risk_class,
        bucket_id=bucket,
        risk_factor_a=risk_factor_a,
        risk_factor_b=risk_factor_b,
        qualifier_a=qualifier_a,
        qualifier_b=qualifier_b,
        option_tenor_a="1y",
        option_tenor_b="5y",
    )

    option_correlation = math.exp(-0.01 * abs(1.0 - 5.0) / 1.0)
    assert correlation == pytest.approx(expected_delta_correlation * option_correlation)
    assert "basel_mar21_94" in citation_ids


def test_non_girr_vega_intra_bucket_correlation_is_capped_at_one() -> None:
    correlation, _ = non_girr_vega_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        risk_class=SbmRiskClass.EQUITY,
        bucket_id="5",
        risk_factor_a="SPOT",
        risk_factor_b="SPOT",
        qualifier_a="ISS-A",
        qualifier_b="ISS-A",
        option_tenor_a="1y",
        option_tenor_b="1y",
    )

    assert correlation == pytest.approx(1.0)


def test_equity_repo_vega_fails_closed() -> None:
    sensitivity = sample_vega_sensitivity(
        sensitivity_id="eq-repo-vega",
        risk_class=SbmRiskClass.EQUITY,
        bucket="5",
        risk_factor="REPO",
        qualifier="ISS-A",
    )

    with pytest.raises(UnsupportedRegulatoryFeatureError, match="repo rates"):
        calculate_sbm_capital((sensitivity,), context=sample_context())


def test_non_girr_vega_requires_option_tenor() -> None:
    sensitivity = sample_vega_sensitivity(
        sensitivity_id="fx-missing-option",
        risk_class=SbmRiskClass.FX,
        bucket="EUR",
        risk_factor="EUR",
        option_tenor=None,
    )

    with pytest.raises(SbmInputError, match="option_tenor"):
        calculate_sbm_capital((sensitivity,), context=sample_context())
