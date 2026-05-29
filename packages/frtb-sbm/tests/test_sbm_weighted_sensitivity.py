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
    weight_girr_delta_sensitivities,
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
