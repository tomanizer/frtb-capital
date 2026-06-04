"""
Eligible CVA hedge validation and routing metadata.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_cva.data_models import (
    BaCvaHedgeType,
    CvaHedge,
    CvaRegulatoryProfile,
    HedgeEligibility,
    SaCvaRiskClass,
)
from frtb_cva.reference_data import profile_citation_ids
from frtb_cva.validation import CvaInputError


@dataclass(frozen=True)
class HedgeEligibilityDecision:
    """Explicit hedge eligibility outcome with audit metadata."""

    hedge_id: str
    eligibility: HedgeEligibility
    sa_cva_risk_class: SaCvaRiskClass | None
    reason_code: str
    citations: tuple[str, ...]


def assess_hedge_eligibility(
    hedge: CvaHedge,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> HedgeEligibilityDecision:
    """Return an explicit eligibility decision without applying capital benefit.

    Parameters
    ----------
    hedge :
        Input for ``assess_hedge_eligibility`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    HedgeEligibilityDecision
        Result of ``assess_hedge_eligibility`` for audit and downstream aggregation."""

    if hedge.eligibility is HedgeEligibility.INELIGIBLE:
        return HedgeEligibilityDecision(
            hedge_id=hedge.hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=hedge.sa_cva_risk_class,
            reason_code=hedge.rejection_reason or "hedge_marked_ineligible",
            citations=profile_citation_ids(("basel_mar50_37",), profile),
        )

    if hedge.eligibility is HedgeEligibility.EXCLUDED:
        return HedgeEligibilityDecision(
            hedge_id=hedge.hedge_id,
            eligibility=HedgeEligibility.EXCLUDED,
            sa_cva_risk_class=hedge.sa_cva_risk_class,
            reason_code="hedge_excluded_from_sa_cva",
            citations=profile_citation_ids(("basel_mar50_39",), profile),
        )

    if hedge.is_internal and not hedge.eligibility_evidence_id:
        return HedgeEligibilityDecision(
            hedge_id=hedge.hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=hedge.sa_cva_risk_class,
            reason_code="internal_hedge_missing_back_to_back_evidence",
            citations=profile_citation_ids(("basel_mar50_11", "basel_mar50_39"), profile),
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
        citations=profile_citation_ids(("basel_mar50_37", "basel_mar50_38"), profile),
    )


_BA_CVA_ELIGIBLE_TYPES = frozenset(
    {
        BaCvaHedgeType.SINGLE_NAME_CDS,
        BaCvaHedgeType.SINGLE_NAME_CONTINGENT_CDS,
        BaCvaHedgeType.INDEX_CDS,
    }
)


def assess_ba_cva_hedge_eligibility(
    hedge: CvaHedge,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> HedgeEligibilityDecision:
    """Return BA-CVA hedge eligibility for full BA-CVA recognition (MAR50.18-MAR50.19).

    Parameters
    ----------
    hedge :
        Input for ``assess_ba_cva_hedge_eligibility`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    HedgeEligibilityDecision
        Result of ``assess_ba_cva_hedge_eligibility`` for audit and downstream aggregation."""

    if hedge.hedge_type not in _BA_CVA_ELIGIBLE_TYPES:
        return HedgeEligibilityDecision(
            hedge_id=hedge.hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=hedge.sa_cva_risk_class,
            reason_code="instrument_type_not_eligible_for_ba_cva",
            citations=profile_citation_ids(("basel_mar50_18",), profile),
        )

    sa_decision = assess_hedge_eligibility(hedge, profile=profile)
    if sa_decision.eligibility is not HedgeEligibility.ELIGIBLE:
        return HedgeEligibilityDecision(
            hedge_id=hedge.hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=hedge.sa_cva_risk_class,
            reason_code=sa_decision.reason_code,
            citations=sa_decision.citations,
        )

    return HedgeEligibilityDecision(
        hedge_id=hedge.hedge_id,
        eligibility=HedgeEligibility.ELIGIBLE,
        sa_cva_risk_class=hedge.sa_cva_risk_class,
        reason_code="eligible_ba_cva_credit_spread_hedge",
        citations=profile_citation_ids(
            ("basel_mar50_18", "basel_mar50_19", "basel_mar50_37"),
            profile,
        ),
    )


def eligible_sa_cva_hedge_ids(
    hedges: tuple[CvaHedge, ...],
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> frozenset[str]:
    """Return hedge ids eligible to contribute SA-CVA hedge sensitivities.

    Parameters
    ----------
    hedges :
        Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    frozenset[str]
        Result of ``eligible_sa_cva_hedge_ids`` for audit and downstream aggregation."""

    eligible: set[str] = set()
    for hedge in hedges:
        decision = assess_hedge_eligibility(hedge, profile=profile)
        if decision.eligibility is HedgeEligibility.ELIGIBLE:
            eligible.add(hedge.hedge_id)
    return frozenset(eligible)


__all__ = [
    "HedgeEligibilityDecision",
    "assess_ba_cva_hedge_eligibility",
    "assess_hedge_eligibility",
    "eligible_sa_cva_hedge_ids",
]
