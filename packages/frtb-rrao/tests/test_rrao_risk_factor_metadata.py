"""Tests for RRAO residual-risk metadata drilldown rows."""

from __future__ import annotations

from datetime import date

from frtb_rrao.data_models import (
    RraoCapitalLine,
    RraoCapitalResult,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
)
from frtb_rrao.risk_factor_metadata import build_rrao_risk_factor_metadata_rows


def test_rrao_risk_factor_metadata_rows_preserve_category_and_source_ids() -> None:
    included = RraoCapitalLine(
        position_id="pos-1",
        classification=RraoClassification.EXOTIC,
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        gross_effective_notional=100.0,
        risk_weight=0.01,
        add_on=1.0,
        currency="USD",
        is_excluded=False,
        reason_code="EXOTIC_UNDERLYING",
        citations=(),
        source_row_id="src-1",
    )
    excluded = RraoCapitalLine(
        position_id="pos-2",
        classification=RraoClassification.EXCLUDED,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        gross_effective_notional=50.0,
        risk_weight=0.0,
        add_on=0.0,
        currency="USD",
        is_excluded=True,
        reason_code="LISTED_EXCLUSION",
        citations=(),
        source_row_id="src-2",
        exclusion_reason=RraoExclusionReason.LISTED,
    )
    result = RraoCapitalResult(
        run_id="run-1",
        calculation_date=date(2025, 1, 2),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        profile_hash="profile",
        input_hash="input",
        lines=(included,),
        excluded_lines=(excluded,),
        subtotals=(),
        total_rrao=1.0,
        citations=(),
    )

    rows = build_rrao_risk_factor_metadata_rows(result)

    assert [row.position_id for row in rows] == ["pos-1", "pos-2"]
    assert rows[0].source_row_id == "src-1"
    assert rows[0].residual_risk_category == "EXOTIC"
    assert rows[1].is_excluded is True
    assert rows[1].exclusion_reason == "LISTED"

    object.__setattr__(result, "lines", None)
    object.__setattr__(result, "excluded_lines", None)
    assert build_rrao_risk_factor_metadata_rows(result) == ()
