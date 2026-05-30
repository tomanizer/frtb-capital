from __future__ import annotations

import math

import pytest
from frtb_sbm import (
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    compute_weighted_sensitivities,
    weight_girr_delta_sensitivities,
    weight_girr_vega_sensitivities,
)


def sample_lineage() -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id="row-001",
    )


def sample_sensitivity(*, amount: float = 1_000_000.0, tenor: str = "5y") -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id="sens-001",
        source_row_id="row-001",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="2",
        risk_factor="USD",
        amount=amount,
        amount_currency="USD",
        tenor=tenor,
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage(),
    )


def test_weight_girr_delta_applies_cited_risk_weight() -> None:
    weighted = weight_girr_delta_sensitivities(
        (sample_sensitivity(),),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    assert len(weighted) == 1
    item = weighted[0]
    expected_weight = 0.011 / math.sqrt(2.0)
    assert item.risk_weight == pytest.approx(expected_weight)
    assert item.scaled_amount == pytest.approx(1_000_000.0 * expected_weight)
    assert "basel_mar21_39" in item.citation_ids
    assert "basel_mar21_40" in item.citation_ids


def sample_vega_sensitivity(
    *, amount: float = 100_000.0, option_tenor: str = "5y"
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id="vega-001",
        source_row_id="row-101",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.VEGA,
        bucket="2",
        risk_factor="USD",
        amount=amount,
        amount_currency="USD",
        tenor="5y",
        option_tenor=option_tenor,
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage(),
    )


def test_weight_girr_vega_applies_cited_liquidity_horizon_risk_weight() -> None:
    weighted = weight_girr_vega_sensitivities(
        (sample_vega_sensitivity(),),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert len(weighted) == 1
    item = weighted[0]
    assert item.risk_weight == 1.0
    assert item.liquidity_horizon_days == 60
    assert item.scaled_amount == pytest.approx(100_000.0)
    assert "basel_mar21_92" in item.citation_ids


def test_compute_weighted_sensitivities_routes_girr_vega() -> None:
    weighted = compute_weighted_sensitivities(
        (sample_vega_sensitivity(),),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    assert len(weighted) == 1
    assert weighted[0].risk_measure is SbmRiskMeasure.VEGA


def test_compute_weighted_sensitivities_routes_csr_nonsec_delta() -> None:
    csr_sensitivity = SbmSensitivity(
        sensitivity_id="csr-001",
        source_row_id="row-csr-001",
        desk_id="credit-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.CSR_NONSEC,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="4",
        risk_factor="BOND",
        qualifier="ISS-A",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=sample_lineage(),
    )
    weighted = compute_weighted_sensitivities(
        (csr_sensitivity,),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    assert len(weighted) == 1
    assert weighted[0].risk_class is SbmRiskClass.CSR_NONSEC
    assert weighted[0].risk_measure is SbmRiskMeasure.DELTA
    assert "basel_mar21_53" in weighted[0].citation_ids
