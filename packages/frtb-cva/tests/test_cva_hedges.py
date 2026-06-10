from __future__ import annotations

import pytest
from frtb_cva import (
    BaCvaHedgeType,
    CreditQuality,
    CvaHedge,
    CvaSector,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaHedgeInstrumentType,
    SaCvaHedgePurpose,
    SaCvaRiskClass,
)
from frtb_cva.hedges import assess_ba_cva_hedge_eligibility, assess_hedge_eligibility
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
        sa_cva_risk_class=SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        sa_cva_hedge_purpose=SaCvaHedgePurpose.COUNTERPARTY_CREDIT_SPREAD,
        sa_cva_hedge_instrument_type=SaCvaHedgeInstrumentType.CREDIT_SPREAD_INSTRUMENT,
        whole_transaction_evidence_id="whole-transaction-1",
        market_risk_ima_eligible=True,
        eligibility_evidence_id="evidence-1",
    )
    base.update(overrides)
    return CvaHedge(**base)  # type: ignore[arg-type]


def test_eligible_single_name_cds_passes_validation() -> None:
    decision = assess_hedge_eligibility(_eligible_hedge())
    assert decision.eligibility is HedgeEligibility.ELIGIBLE
    assert "basel_mar50_38" in decision.citations


def test_sa_cva_exposure_component_hedge_does_not_require_ba_hedge_type() -> None:
    decision = assess_hedge_eligibility(
        _eligible_hedge(
            hedge_type=None,
            sa_cva_risk_class=SaCvaRiskClass.GIRR,
            sa_cva_hedge_purpose=SaCvaHedgePurpose.EXPOSURE_COMPONENT,
            sa_cva_hedge_instrument_type=SaCvaHedgeInstrumentType.INTEREST_RATE,
        )
    )
    assert decision.eligibility is HedgeEligibility.ELIGIBLE
    assert decision.reason_code == "eligible_whole_transaction_hedge"


def test_sa_cva_credit_spread_hedge_requires_ccs_or_rcs_assignment() -> None:
    with pytest.raises(CvaInputError, match="whole-instrument CCS or RCS"):
        assess_hedge_eligibility(
            _eligible_hedge(
                sa_cva_risk_class=SaCvaRiskClass.GIRR,
                sa_cva_hedge_purpose=SaCvaHedgePurpose.COUNTERPARTY_CREDIT_SPREAD,
            )
        )


def test_sa_cva_excluded_hedge_uses_market_risk_ima_exclusion_reason() -> None:
    decision = assess_hedge_eligibility(
        _eligible_hedge(
            eligibility=HedgeEligibility.EXCLUDED,
            rejection_reason="market_risk_model_scope",
            market_risk_ima_eligible=False,
            market_risk_ima_exclusion_reason="not_market_risk_ima_eligible",
        )
    )
    assert decision.eligibility is HedgeEligibility.EXCLUDED
    assert decision.reason_code == "not_market_risk_ima_eligible"
    assert "basel_mar50_39" in decision.citations


def test_ba_cva_eligibility_does_not_require_sa_metadata() -> None:
    hedge = _eligible_hedge(
        sa_cva_risk_class=None,
        sa_cva_hedge_purpose=None,
        sa_cva_hedge_instrument_type=None,
        whole_transaction_evidence_id=None,
        market_risk_ima_eligible=None,
    )
    decision = assess_ba_cva_hedge_eligibility(hedge)
    assert decision.eligibility is HedgeEligibility.ELIGIBLE
    assert decision.reason_code == "eligible_ba_cva_credit_spread_hedge"


def test_ba_cva_eligibility_requires_ba_hedge_type() -> None:
    decision = assess_ba_cva_hedge_eligibility(_eligible_hedge(hedge_type=None))
    assert decision.eligibility is HedgeEligibility.INELIGIBLE
    assert decision.reason_code == "instrument_type_not_eligible_for_ba_cva"


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
