"""Tests for suite-level risk-factor view composition."""

from __future__ import annotations

import pytest
from frtb_orchestration.risk_factor_views import (
    RiskFactorCapitalViewRow,
    RiskFactorEvidenceViewRow,
    RiskFactorViewStatus,
    build_risk_factor_aggregate_view,
)


def test_risk_factor_aggregate_view_composes_sbm_capital_and_ima_evidence() -> None:
    view = build_risk_factor_aggregate_view(
        "rf:girr:usd-swap:10y",
        mapping_version="map-v1",
        expected_capital_components=("SBM", "DRC"),
        capital_rows=(
            RiskFactorCapitalViewRow(
                component="SBM",
                risk_factor_id="rf:girr:usd-swap:10y",
                mapping_version="map-v1",
                amount=12.5,
                source_row_ids=("sbm-row-1",),
            ),
        ),
        evidence_rows=(
            RiskFactorEvidenceViewRow(
                component="IMA",
                risk_factor_id="rf:girr:usd-swap:10y",
                mapping_version="map-v1",
                evidence_type="RFET",
                evidence_ids=("rfet-evidence-1",),
            ),
        ),
    )

    assert view.total_available_amount == pytest.approx(12.5)
    assert [(row.component, row.status) for row in view.capital_rows] == [
        ("DRC", RiskFactorViewStatus.NO_DATA),
        ("SBM", RiskFactorViewStatus.AVAILABLE),
    ]
    assert view.capital_rows[0].reason == (
        "no resolved capital contribution rows for selected risk factor"
    )
    assert view.evidence_rows[0].component == "IMA"
    assert view.as_dict()["mapping_version"] == "map-v1"


def test_risk_factor_view_requires_reason_for_unavailable_states() -> None:
    with pytest.raises(ValueError, match="requires reason"):
        RiskFactorCapitalViewRow(
            component="IMA",
            risk_factor_id="rf:missing",
            mapping_version=None,
            amount=None,
            status=RiskFactorViewStatus.UNSUPPORTED,
        )


def test_risk_factor_aggregate_view_tolerates_nullable_input_collections() -> None:
    view = build_risk_factor_aggregate_view(
        "rf:girr:usd-swap:10y",
        mapping_version="map-v1",
        capital_rows=None,  # type: ignore[arg-type]
        evidence_rows=None,  # type: ignore[arg-type]
        expected_capital_components=None,  # type: ignore[arg-type]
    )

    assert view.capital_rows == ()
    assert view.evidence_rows == ()
