"""CVA batch hedge eligibility and BA hedge weighting helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from frtb_cva._batch_contracts import CvaHedgeBatch
from frtb_cva.data_models import (
    BaCvaHedgeType,
    CreditQuality,
    CvaRegulatoryProfile,
    CvaSector,
    HedgeEligibility,
    SaCvaHedgePurpose,
    SaCvaRiskClass,
)
from frtb_cva.hedges import HedgeEligibilityDecision
from frtb_cva.reference_data import (
    ba_cva_index_risk_weight_scalar,
    ba_cva_risk_weight,
    compute_non_imm_discount_factor,
    profile_citation_id,
    profile_citation_ids,
)
from frtb_cva.validation import (
    CvaInputError,
)


def _assess_sa_cva_hedge_eligibility(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> HedgeEligibilityDecision:
    hedge_id = cast(str, batch.hedge_ids[index])
    sa_risk_class = (
        None
        if batch.sa_cva_risk_classes[index] is None
        else SaCvaRiskClass(cast(str, batch.sa_cva_risk_classes[index]))
    )
    base_decision = _assess_base_hedge_eligibility(batch, index, profile=profile)
    if base_decision.eligibility is not HedgeEligibility.ELIGIBLE:
        return base_decision
    _validate_sa_cva_hedge_batch_metadata(batch, index)
    return HedgeEligibilityDecision(
        hedge_id=hedge_id,
        eligibility=HedgeEligibility.ELIGIBLE,
        sa_cva_risk_class=sa_risk_class,
        reason_code="eligible_whole_transaction_hedge",
        citations=profile_citation_ids(("basel_mar50_37", "basel_mar50_38"), profile),
    )


def _assess_ba_cva_hedge_eligibility(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> HedgeEligibilityDecision:
    hedge_id = cast(str, batch.hedge_ids[index])
    hedge_type_value = batch.hedge_types[index]
    if hedge_type_value is None:
        return HedgeEligibilityDecision(
            hedge_id=hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=None,
            reason_code="instrument_type_not_eligible_for_ba_cva",
            citations=profile_citation_ids(("basel_mar50_18",), profile),
        )
    hedge_type = BaCvaHedgeType(cast(str, hedge_type_value))
    if hedge_type not in {
        BaCvaHedgeType.SINGLE_NAME_CDS,
        BaCvaHedgeType.SINGLE_NAME_CONTINGENT_CDS,
        BaCvaHedgeType.INDEX_CDS,
    }:
        return HedgeEligibilityDecision(
            hedge_id=hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=None,
            reason_code="instrument_type_not_eligible_for_ba_cva",
            citations=profile_citation_ids(("basel_mar50_18",), profile),
        )
    base_decision = _assess_base_hedge_eligibility(batch, index, profile=profile)
    if base_decision.eligibility is not HedgeEligibility.ELIGIBLE:
        return replace(base_decision, eligibility=HedgeEligibility.INELIGIBLE)
    return HedgeEligibilityDecision(
        hedge_id=hedge_id,
        eligibility=HedgeEligibility.ELIGIBLE,
        sa_cva_risk_class=base_decision.sa_cva_risk_class,
        reason_code="eligible_ba_cva_credit_spread_hedge",
        citations=profile_citation_ids(
            ("basel_mar50_18", "basel_mar50_19", "basel_mar50_37"),
            profile,
        ),
    )


def _assess_base_hedge_eligibility(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> HedgeEligibilityDecision:
    hedge_id = cast(str, batch.hedge_ids[index])
    eligibility = HedgeEligibility(cast(str, batch.eligibilities[index]))
    sa_risk_class = (
        None
        if batch.sa_cva_risk_classes[index] is None
        else SaCvaRiskClass(cast(str, batch.sa_cva_risk_classes[index]))
    )
    if eligibility is HedgeEligibility.INELIGIBLE:
        return HedgeEligibilityDecision(
            hedge_id=hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=sa_risk_class,
            reason_code=cast(str | None, batch.rejection_reasons[index])
            or "hedge_marked_ineligible",
            citations=profile_citation_ids(("basel_mar50_37",), profile),
        )
    if eligibility is HedgeEligibility.EXCLUDED:
        return HedgeEligibilityDecision(
            hedge_id=hedge_id,
            eligibility=HedgeEligibility.EXCLUDED,
            sa_cva_risk_class=sa_risk_class,
            reason_code=cast(str | None, batch.market_risk_ima_exclusion_reasons[index])
            or "hedge_excluded_from_sa_cva",
            citations=profile_citation_ids(("basel_mar50_39",), profile),
        )
    if bool(batch.is_internal[index]) and not batch.eligibility_evidence_ids[index]:
        return HedgeEligibilityDecision(
            hedge_id=hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=sa_risk_class,
            reason_code="internal_hedge_missing_back_to_back_evidence",
            citations=profile_citation_ids(("basel_mar50_11", "basel_mar50_39"), profile),
        )
    if not batch.eligibility_evidence_ids[index]:
        raise CvaInputError(
            "eligible hedge requires eligibility_evidence_id",
            field="eligibility_evidence_id",
            record_id=hedge_id,
        )
    return HedgeEligibilityDecision(
        hedge_id=hedge_id,
        eligibility=HedgeEligibility.ELIGIBLE,
        sa_cva_risk_class=sa_risk_class,
        reason_code="eligible_hedge",
        citations=profile_citation_ids(("basel_mar50_37",), profile),
    )


def _validate_sa_cva_hedge_batch_metadata(batch: CvaHedgeBatch, index: int) -> None:
    hedge_id = cast(str, batch.hedge_ids[index])
    purpose_value = batch.sa_cva_hedge_purposes[index]
    instrument_value = batch.sa_cva_hedge_instrument_types[index]
    if purpose_value is None:
        raise CvaInputError(
            "eligible SA-CVA hedge requires sa_cva_hedge_purpose",
            field="sa_cva_hedge_purpose",
            record_id=hedge_id,
        )
    if instrument_value is None:
        raise CvaInputError(
            "eligible SA-CVA hedge requires sa_cva_hedge_instrument_type",
            field="sa_cva_hedge_instrument_type",
            record_id=hedge_id,
        )
    if not batch.whole_transaction_evidence_ids[index]:
        raise CvaInputError(
            "eligible SA-CVA hedge requires whole_transaction_evidence_id",
            field="whole_transaction_evidence_id",
            record_id=hedge_id,
        )
    if batch.market_risk_ima_eligibilities[index] is not True:
        raise CvaInputError(
            "eligible SA-CVA hedge requires market_risk_ima_eligible=True",
            field="market_risk_ima_eligible",
            record_id=hedge_id,
        )
    purpose = SaCvaHedgePurpose(cast(str, purpose_value))
    sa_risk_class = (
        None
        if batch.sa_cva_risk_classes[index] is None
        else SaCvaRiskClass(cast(str, batch.sa_cva_risk_classes[index]))
    )
    if purpose is SaCvaHedgePurpose.COUNTERPARTY_CREDIT_SPREAD:
        if sa_risk_class not in {
            SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
            SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        }:
            raise CvaInputError(
                "credit-spread SA-CVA hedge requires whole-instrument CCS or RCS assignment",
                field="sa_cva_risk_class",
                record_id=hedge_id,
            )
    elif sa_risk_class in {
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
    }:
        raise CvaInputError(
            "exposure-component SA-CVA hedge cannot use CCS or RCS assignment",
            field="sa_cva_risk_class",
            record_id=hedge_id,
        )


def _eligible_sa_cva_hedge_ids(
    batch: CvaHedgeBatch,
    *,
    profile: CvaRegulatoryProfile | str,
) -> frozenset[str]:
    eligible: set[str] = set()
    for index in range(batch.row_count):
        if (
            _assess_sa_cva_hedge_eligibility(batch, index, profile=profile).eligibility
            is HedgeEligibility.ELIGIBLE
        ):
            eligible.add(cast(str, batch.hedge_ids[index]))
    return frozenset(eligible)


def _hedge_discount_factor(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str, bool]:
    discount_factor = float(batch.discount_factors[index])
    if bool(batch.discount_factor_explicit[index]) or discount_factor != 1.0:
        return discount_factor, profile_citation_id("basel_mar50_23", profile), True
    calculated, citation = compute_non_imm_discount_factor(float(batch.remaining_maturities[index]))
    return calculated, profile_citation_id(citation, profile), False


def _hedge_risk_weight(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str]:
    risk_weight, citation = ba_cva_risk_weight(
        CvaSector(cast(str, batch.reference_sectors[index])),
        CreditQuality(cast(str, batch.reference_credit_qualities[index])),
        profile=profile,
    )
    if BaCvaHedgeType(cast(str, batch.hedge_types[index])) is BaCvaHedgeType.INDEX_CDS:
        scalar, scalar_citation = ba_cva_index_risk_weight_scalar(profile=profile)
        return risk_weight * scalar, scalar_citation
    return risk_weight, citation
