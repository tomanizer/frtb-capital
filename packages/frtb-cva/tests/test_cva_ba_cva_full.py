from __future__ import annotations

from dataclasses import replace

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


def test_beta_floor_flag_is_not_binding_when_hedged_component_is_zero(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    zero_exposure = replace(
        sovereign_netting_set,
        netting_set_id="ns-zero",
        ead=0.0,
        source_row_id="row-zero",
    )
    full = calculate_full_portfolio((sovereign_counterparty,), (zero_exposure,))
    assert full.k_hedged == pytest.approx(0.0)
    assert full.k_full == pytest.approx(0.0)
    assert full.beta_floor_binding is False


def test_hedge_explicit_discount_factor_unity_is_not_recomputed(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    hedge = CvaHedge(
        hedge_id="hedge-df-explicit",
        source_row_id="row-hedge-df",
        counterparty_id=sovereign_counterparty.counterparty_id,
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=100_000.0,
        remaining_maturity=5.0,
        discount_factor=1.0,
        discount_factor_explicit=True,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="evidence-df",
    )
    implicit_df = replace(
        hedge,
        hedge_id="hedge-df-implicit",
        source_row_id="row-hedge-df-implicit",
        discount_factor_explicit=False,
    )
    explicit_result = calculate_full_portfolio(
        (sovereign_counterparty,),
        (sovereign_netting_set,),
        (hedge,),
    )
    implicit_result = calculate_full_portfolio(
        (sovereign_counterparty,),
        (sovereign_netting_set,),
        (implicit_df,),
    )
    explicit_snh = explicit_result.hedge_lines[0].snh_contribution
    implicit_snh = implicit_result.hedge_lines[0].snh_contribution
    assert explicit_snh > implicit_snh


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
