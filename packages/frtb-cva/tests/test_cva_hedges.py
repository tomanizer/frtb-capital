from __future__ import annotations

import pytest
from frtb_cva import (
    BaCvaHedgeType,
    CreditQuality,
    CvaHedge,
    CvaSector,
    HedgeEligibility,
    HedgeReferenceRelation,
)
from frtb_cva.hedges import assess_hedge_eligibility
from frtb_cva.validation import CvaInputError


def _eligible_hedge(**overrides: object) -> CvaHedge:
    base = dict(
        hedge_id="hedge-1",
        source_row_id="row-hedge-1",
        counterparty_id="ctp-1",
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=100_000.0,
        remaining_maturity=2.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="evidence-1",
    )
    base.update(overrides)
    return CvaHedge(**base)  # type: ignore[arg-type]


def test_eligible_single_name_cds_passes_validation() -> None:
    decision = assess_hedge_eligibility(_eligible_hedge())
    assert decision.eligibility is HedgeEligibility.ELIGIBLE
    assert "basel_mar50_37" in decision.citations


def test_internal_hedge_without_evidence_is_ineligible() -> None:
    decision = assess_hedge_eligibility(
        _eligible_hedge(is_internal=True, eligibility_evidence_id=None)
    )
    assert decision.eligibility is HedgeEligibility.INELIGIBLE


def test_marked_ineligible_hedge_requires_no_capital_benefit() -> None:
    decision = assess_hedge_eligibility(
        _eligible_hedge(
            eligibility=HedgeEligibility.INELIGIBLE,
            rejection_reason="tranched_credit_derivative",
        )
    )
    assert decision.eligibility is HedgeEligibility.INELIGIBLE


def test_eligible_hedge_without_evidence_id_fails() -> None:
    with pytest.raises(CvaInputError, match="eligibility_evidence_id"):
        assess_hedge_eligibility(
            _eligible_hedge(eligibility=HedgeEligibility.ELIGIBLE, eligibility_evidence_id=None)
        )
