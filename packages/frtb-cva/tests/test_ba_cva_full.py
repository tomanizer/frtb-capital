from __future__ import annotations

import pytest
from frtb_cva import (
    BaCvaHedgeType,
    CreditQuality,
    CvaHedge,
    CvaSector,
    HedgeEligibility,
    HedgeReferenceRelation,
    calculate_full_portfolio,
)


def test_full_ba_cva_without_hedges_matches_reduced(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    full = calculate_full_portfolio((sovereign_counterparty,), (sovereign_netting_set,))
    assert full.k_full == pytest.approx(full.k_reduced)
    assert full.k_hedged == pytest.approx(full.k_reduced)
    assert not full.beta_floor_binding


def test_direct_hedge_reduces_full_capital(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    hedge = CvaHedge(
        hedge_id="hedge-1",
        source_row_id="row-hedge-1",
        counterparty_id=sovereign_counterparty.counterparty_id,
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=500_000.0,
        remaining_maturity=1.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="evidence-1",
    )
    without = calculate_full_portfolio((sovereign_counterparty,), (sovereign_netting_set,))
    with_hedge = calculate_full_portfolio(
        (sovereign_counterparty,),
        (sovereign_netting_set,),
        (hedge,),
    )
    assert with_hedge.k_full < without.k_full
    assert with_hedge.k_full >= with_hedge.beta * without.k_reduced - 1e-9


def test_ineligible_hedge_has_zero_benefit(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    hedge = CvaHedge(
        hedge_id="hedge-1",
        source_row_id="row-hedge-1",
        counterparty_id=sovereign_counterparty.counterparty_id,
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=900_000.0,
        remaining_maturity=1.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.INELIGIBLE,
        is_internal=False,
        rejection_reason="tranched",
    )
    baseline = calculate_full_portfolio((sovereign_counterparty,), (sovereign_netting_set,))
    with_ineligible = calculate_full_portfolio(
        (sovereign_counterparty,),
        (sovereign_netting_set,),
        (hedge,),
    )
    assert with_ineligible.k_full == pytest.approx(baseline.k_full)
    assert with_ineligible.hedge_lines[0].snh_contribution == 0.0
