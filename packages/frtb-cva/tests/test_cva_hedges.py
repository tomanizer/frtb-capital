from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from frtb_cva import (
    BaCvaHedgeType,
    CreditQuality,
    CvaHedge,
    CvaSector,
    CvaSourceLineage,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaHedgeInstrumentType,
    SaCvaHedgePurpose,
    SaCvaRiskClass,
    build_cva_hedge_batch_from_hedges,
)
from frtb_cva._batch_hedges import (
    _assess_ba_cva_hedge_eligibility,
    _assess_sa_cva_hedge_eligibility,
    _eligible_sa_cva_hedge_ids,
    _hedge_from_batch_row,
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
        lineage=CvaSourceLineage(
            source_system="synthetic",
            source_file="hedges.csv",
            source_row_id="row-hedge-1",
        ),
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


def test_batch_hedge_row_materializer_preserves_eligibility_inputs() -> None:
    hedge = _eligible_hedge(
        hedge_id="hedge-materialized",
        internal_desk_counterparty_id="internal-desk-1",
        discount_factor_explicit=True,
    )
    batch = build_cva_hedge_batch_from_hedges((hedge,))

    assert _hedge_from_batch_row(batch, 0) == hedge


def test_batch_hedge_row_materializer_treats_nan_optional_values_as_missing() -> None:
    batch = replace(
        build_cva_hedge_batch_from_hedges((_eligible_hedge(),)),
        hedge_types=np.array([np.nan], dtype=object),
        internal_desk_counterparty_ids=np.array([np.nan], dtype=object),
        sa_cva_risk_classes=np.array([np.nan], dtype=object),
        sa_cva_hedge_purposes=np.array([np.nan], dtype=object),
        sa_cva_hedge_instrument_types=np.array([np.nan], dtype=object),
        whole_transaction_evidence_ids=np.array([np.nan], dtype=object),
        market_risk_ima_eligibilities=np.array([np.nan], dtype=object),
        market_risk_ima_exclusion_reasons=np.array([np.nan], dtype=object),
        eligibility_evidence_ids=np.array([np.nan], dtype=object),
        rejection_reasons=np.array([np.nan], dtype=object),
    )

    hedge = _hedge_from_batch_row(batch, 0)

    assert hedge.hedge_type is None
    assert hedge.internal_desk_counterparty_id is None
    assert hedge.sa_cva_risk_class is None
    assert hedge.sa_cva_hedge_purpose is None
    assert hedge.sa_cva_hedge_instrument_type is None
    assert hedge.whole_transaction_evidence_id is None
    assert hedge.market_risk_ima_eligible is None
    assert hedge.market_risk_ima_exclusion_reason is None
    assert hedge.eligibility_evidence_id is None
    assert hedge.rejection_reason is None


@pytest.mark.parametrize(
    "hedge",
    [
        _eligible_hedge(hedge_id="h-eligible"),
        _eligible_hedge(
            hedge_id="h-exposure",
            hedge_type=None,
            sa_cva_risk_class=SaCvaRiskClass.GIRR,
            sa_cva_hedge_purpose=SaCvaHedgePurpose.EXPOSURE_COMPONENT,
            sa_cva_hedge_instrument_type=SaCvaHedgeInstrumentType.INTEREST_RATE,
        ),
        _eligible_hedge(
            hedge_id="h-excluded",
            eligibility=HedgeEligibility.EXCLUDED,
            rejection_reason="market_risk_model_scope",
            market_risk_ima_eligible=False,
            market_risk_ima_exclusion_reason="not_market_risk_ima_eligible",
        ),
        _eligible_hedge(
            hedge_id="h-ineligible",
            eligibility=HedgeEligibility.INELIGIBLE,
            rejection_reason="tranched_credit_derivative",
        ),
    ],
)
def test_batch_and_row_hedge_eligibility_decisions_match(hedge: CvaHedge) -> None:
    batch = build_cva_hedge_batch_from_hedges((hedge,))

    assert _assess_sa_cva_hedge_eligibility(batch, 0, profile="BASEL_MAR50_2020") == (
        assess_hedge_eligibility(hedge, profile="BASEL_MAR50_2020")
    )
    assert _assess_ba_cva_hedge_eligibility(batch, 0, profile="BASEL_MAR50_2020") == (
        assess_ba_cva_hedge_eligibility(hedge, profile="BASEL_MAR50_2020")
    )


def test_batch_and_row_internal_hedge_without_evidence_decisions_match() -> None:
    hedge = _eligible_hedge(
        hedge_id="h-internal",
        is_internal=True,
        eligibility_evidence_id=None,
    )
    batch = replace(
        build_cva_hedge_batch_from_hedges((_eligible_hedge(hedge_id="h-internal"),)),
        is_internal=np.array([True], dtype=np.bool_),
        eligibility_evidence_ids=np.array([None], dtype=object),
    )

    assert _assess_sa_cva_hedge_eligibility(batch, 0, profile="BASEL_MAR50_2020") == (
        assess_hedge_eligibility(hedge, profile="BASEL_MAR50_2020")
    )
    assert _assess_ba_cva_hedge_eligibility(batch, 0, profile="BASEL_MAR50_2020") == (
        assess_ba_cva_hedge_eligibility(hedge, profile="BASEL_MAR50_2020")
    )


@pytest.mark.parametrize(
    "hedge",
    [
        _eligible_hedge(
            hedge_id="h-missing-purpose",
            sa_cva_hedge_purpose=None,
        ),
        _eligible_hedge(
            hedge_id="h-wrong-risk-class",
            sa_cva_risk_class=SaCvaRiskClass.GIRR,
            sa_cva_hedge_purpose=SaCvaHedgePurpose.COUNTERPARTY_CREDIT_SPREAD,
        ),
        _eligible_hedge(
            hedge_id="h-exposure-with-ccs",
            sa_cva_risk_class=SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
            sa_cva_hedge_purpose=SaCvaHedgePurpose.EXPOSURE_COMPONENT,
            sa_cva_hedge_instrument_type=SaCvaHedgeInstrumentType.INTEREST_RATE,
        ),
    ],
)
def test_batch_and_row_sa_cva_hedge_validation_failures_match(hedge: CvaHedge) -> None:
    batch = build_cva_hedge_batch_from_hedges((hedge,))

    with pytest.raises(CvaInputError) as row_error:
        assess_hedge_eligibility(hedge)
    with pytest.raises(CvaInputError) as batch_error:
        _assess_sa_cva_hedge_eligibility(batch, 0, profile="BASEL_MAR50_2020")

    assert batch_error.value.field == row_error.value.field
    assert batch_error.value.record_id == row_error.value.record_id


def test_batch_eligible_sa_cva_hedge_ids_uses_shared_row_rule() -> None:
    eligible = _eligible_hedge(hedge_id="h-eligible")
    excluded = _eligible_hedge(
        hedge_id="h-excluded",
        eligibility=HedgeEligibility.EXCLUDED,
        rejection_reason="market_risk_model_scope",
        market_risk_ima_eligible=False,
        market_risk_ima_exclusion_reason="not_market_risk_ima_eligible",
    )
    batch = build_cva_hedge_batch_from_hedges((eligible, excluded))

    assert _eligible_sa_cva_hedge_ids(batch, profile="BASEL_MAR50_2020") == frozenset(
        {"h-eligible"}
    )
