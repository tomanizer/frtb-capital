"""
Eligible CVA hedge validation and routing metadata.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_cva.data_models import (
    CvaHedge,
    HedgeEligibility,
    SaCvaRiskClass,
)
from frtb_cva.validation import CvaInputError


@dataclass(frozen=True)
class HedgeEligibilityDecision:
    """Explicit hedge eligibility outcome with audit metadata."""

    hedge_id: str
    eligibility: HedgeEligibility
    sa_cva_risk_class: SaCvaRiskClass | None
    reason_code: str
    citations: tuple[str, ...]


def assess_hedge_eligibility(hedge: CvaHedge) -> HedgeEligibilityDecision:
    """Return an explicit eligibility decision without applying capital benefit."""

    if hedge.eligibility is HedgeEligibility.INELIGIBLE:
        return HedgeEligibilityDecision(
            hedge_id=hedge.hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=hedge.sa_cva_risk_class,
            reason_code=hedge.rejection_reason or "hedge_marked_ineligible",
            citations=("basel_mar50_37",),
        )

    if hedge.eligibility is HedgeEligibility.EXCLUDED:
        return HedgeEligibilityDecision(
            hedge_id=hedge.hedge_id,
            eligibility=HedgeEligibility.EXCLUDED,
            sa_cva_risk_class=hedge.sa_cva_risk_class,
            reason_code="hedge_excluded_from_sa_cva",
            citations=("basel_mar50_39",),
        )

    if hedge.is_internal and not hedge.eligibility_evidence_id:
        return HedgeEligibilityDecision(
            hedge_id=hedge.hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=hedge.sa_cva_risk_class,
            reason_code="internal_hedge_missing_back_to_back_evidence",
            citations=("basel_mar50_11", "basel_mar50_39"),
        )

    if hedge.eligibility is HedgeEligibility.ELIGIBLE and not hedge.eligibility_evidence_id:
        raise CvaInputError(
            "eligible hedge requires eligibility_evidence_id",
            field="eligibility_evidence_id",
            record_id=hedge.hedge_id,
        )

    return HedgeEligibilityDecision(
        hedge_id=hedge.hedge_id,
        eligibility=HedgeEligibility.ELIGIBLE,
        sa_cva_risk_class=hedge.sa_cva_risk_class,
        reason_code="eligible_whole_transaction_hedge",
        citations=("basel_mar50_37", "basel_mar50_38"),
    )


def eligible_sa_cva_hedge_ids(hedges: tuple[CvaHedge, ...]) -> frozenset[str]:
    """Return hedge ids eligible to contribute SA-CVA hedge sensitivities."""

    eligible: set[str] = set()
    for hedge in hedges:
        decision = assess_hedge_eligibility(hedge)
        if decision.eligibility is HedgeEligibility.ELIGIBLE:
            eligible.add(hedge.hedge_id)
    return frozenset(eligible)


__all__ = [
    "HedgeEligibilityDecision",
    "assess_hedge_eligibility",
    "eligible_sa_cva_hedge_ids",
]
