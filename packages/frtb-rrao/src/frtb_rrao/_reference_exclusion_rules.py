"""RRAO exclusion reference rules by supported profile."""

from __future__ import annotations

from frtb_rrao._reference_eu_rule_sets import _EU_ARTICLE_3_EXCLUSION_REASONS
from frtb_rrao._reference_rule_types import RraoExclusionRule
from frtb_rrao.data_models import RraoExclusionReason, RraoRegulatoryProfile

PROFILE_EXCLUSION_RULES: dict[RraoRegulatoryProfile, tuple[RraoExclusionRule, ...]] = {
    RraoRegulatoryProfile.BASEL_MAR23: tuple(
        RraoExclusionRule(
            exclusion_reason=reason,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code=f"BASEL_EXCLUSION_{reason.value}",
            citation_id="basel_mar23_4_7",
        )
        for reason in (
            RraoExclusionReason.LISTED,
            RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            RraoExclusionReason.TWO_OR_FEWER_UNDERLYINGS_NON_PATH_DEPENDENT_OPTION,
            RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
        )
    ),
    RraoRegulatoryProfile.US_NPR_2_0: (
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.LISTED,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_LISTED",
            citation_id="us_npr_211_b_1",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_CLEARABLE",
            citation_id="us_npr_211_b_1",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.TWO_OR_FEWER_UNDERLYINGS_NON_PATH_DEPENDENT_OPTION,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_SIMPLE_OPTION",
            citation_id="us_npr_211_b_1",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_EXACT_BACK_TO_BACK",
            citation_id="us_npr_211_b_2_i",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.DELIVERABLE_HEDGE_PAIR,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_DELIVERABLE_HEDGE_PAIR",
            citation_id="us_npr_211_b_2_ii",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.GOVERNMENT_OR_GSE_DEBT,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_GOVERNMENT_OR_GSE_DEBT",
            citation_id="us_npr_211_b_2_iii",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.FALLBACK_CAPITAL_REQUIREMENT,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_FALLBACK_CAPITAL",
            citation_id="us_npr_211_b_2_iv",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.INTERNAL_DESK_TRANSACTION,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_INTERNAL_DESK_TRANSACTION",
            citation_id="us_npr_211_b_2_v",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.AGENCY_DETERMINED_EXCLUSION,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_AGENCY_DETERMINED",
            citation_id="us_npr_211_b_2_vi",
        ),
    ),
    RraoRegulatoryProfile.EU_CRR3: (
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.LISTED,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="EU_CRR3_EXCLUSION_LISTED",
            citation_id="eu_crr_325u_4",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="EU_CRR3_EXCLUSION_CLEARABLE",
            citation_id="eu_crr_325u_4",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="EU_CRR3_EXCLUSION_PERFECTLY_OFFSETTING",
            citation_id="eu_crr_325u_4",
        ),
        *(
            RraoExclusionRule(
                exclusion_reason=reason,
                risk_weight_key="NON_PRESUMPTIVE_0_PERCENT",
                reason_code=f"EU_CRR3_NON_PRESUMPTIVE_{reason.value}",
                citation_id="eu_rts_2022_2328_article_3",
            )
            for reason in _EU_ARTICLE_3_EXCLUSION_REASONS
        ),
    ),
    RraoRegulatoryProfile.PRA_UK_CRR: (
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.LISTED,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="PRA_UK_CRR_EXCLUSION_LISTED",
            citation_id="uk_crr_325u_4",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="PRA_UK_CRR_EXCLUSION_CLEARABLE",
            citation_id="uk_crr_325u_4",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="PRA_UK_CRR_EXCLUSION_PERFECTLY_OFFSETTING",
            citation_id="uk_crr_325u_4",
        ),
        *(
            RraoExclusionRule(
                exclusion_reason=reason,
                risk_weight_key="NON_PRESUMPTIVE_0_PERCENT",
                reason_code=f"PRA_UK_CRR_NON_PRESUMPTIVE_{reason.value}",
                citation_id="uk_rts_2022_2328_article_3",
            )
            for reason in _EU_ARTICLE_3_EXCLUSION_REASONS
        ),
    ),
}

__all__ = ["PROFILE_EXCLUSION_RULES"]
