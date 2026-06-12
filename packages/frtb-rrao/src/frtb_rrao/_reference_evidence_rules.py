"""RRAO evidence and investment-fund inclusion reference rules."""

from __future__ import annotations

from frtb_rrao._reference_eu_rule_sets import _EU_ARTICLE_2_EVIDENCE_TYPES
from frtb_rrao._reference_rule_types import RraoEvidenceRule, RraoInvestmentFundRule
from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoInvestmentFundExposureType,
    RraoRegulatoryProfile,
)

PROFILE_EVIDENCE_RULES: dict[RraoRegulatoryProfile, tuple[RraoEvidenceRule, ...]] = {
    RraoRegulatoryProfile.BASEL_MAR23: (
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="BASEL_EXOTIC_UNDERLYING",
            citation_id="basel_mar23_2",
        ),
        *(
            RraoEvidenceRule(
                evidence_type=evidence_type,
                classification=RraoClassification.OTHER_RESIDUAL_RISK,
                risk_weight_key="OTHER_0_1_PERCENT",
                reason_code=f"BASEL_{evidence_type.value}",
                citation_id="basel_mar23_3",
            )
            for evidence_type in (
                RraoEvidenceType.GAP_RISK,
                RraoEvidenceType.CORRELATION_RISK,
                RraoEvidenceType.BEHAVIOURAL_RISK,
                RraoEvidenceType.CTP_THREE_OR_MORE_UNDERLYINGS,
                RraoEvidenceType.NON_REPLICABLE_OPTIONALITY,
                RraoEvidenceType.NO_MATURITY_OPTIONALITY,
                RraoEvidenceType.NO_STRIKE_OR_BARRIER_OPTIONALITY,
                RraoEvidenceType.MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY,
            )
        ),
    ),
    RraoRegulatoryProfile.US_NPR_2_0: (
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="US_NPR_EXOTIC_EXPOSURE",
            citation_id="us_npr_211_a_1",
        ),
        *(
            RraoEvidenceRule(
                evidence_type=evidence_type,
                classification=RraoClassification.OTHER_RESIDUAL_RISK,
                risk_weight_key="OTHER_0_1_PERCENT",
                reason_code=f"US_NPR_{evidence_type.value}",
                citation_id="us_npr_211_a_2",
            )
            for evidence_type in (
                RraoEvidenceType.GAP_RISK,
                RraoEvidenceType.CORRELATION_RISK,
                RraoEvidenceType.BEHAVIOURAL_RISK,
                RraoEvidenceType.CTP_THREE_OR_MORE_UNDERLYINGS,
                RraoEvidenceType.NON_REPLICABLE_OPTIONALITY,
                RraoEvidenceType.NO_MATURITY_OPTIONALITY,
                RraoEvidenceType.NO_STRIKE_OR_BARRIER_OPTIONALITY,
                RraoEvidenceType.MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY,
            )
        ),
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.SUPERVISOR_DIRECTIVE,
            classification=RraoClassification.SUPERVISOR_DIRECTED,
            risk_weight_key="SUPERVISOR_DIRECTED_0_1_PERCENT",
            reason_code="US_NPR_SUPERVISOR_DIRECTIVE",
            citation_id="us_npr_211_a_4",
        ),
    ),
    RraoRegulatoryProfile.EU_CRR3: (
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="EU_CRR3_EXOTIC_UNDERLYING",
            citation_id="eu_rts_2022_2328_article_1",
        ),
        *(
            RraoEvidenceRule(
                evidence_type=evidence_type,
                classification=RraoClassification.OTHER_RESIDUAL_RISK,
                risk_weight_key="OTHER_0_1_PERCENT",
                reason_code=f"EU_CRR3_{evidence_type.value}",
                citation_id="eu_rts_2022_2328_article_2_annex",
            )
            for evidence_type in _EU_ARTICLE_2_EVIDENCE_TYPES
        ),
    ),
    RraoRegulatoryProfile.PRA_UK_CRR: (
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="PRA_UK_CRR_EXOTIC_UNDERLYING",
            citation_id="uk_rts_2022_2328_article_1",
        ),
        *(
            RraoEvidenceRule(
                evidence_type=evidence_type,
                classification=RraoClassification.OTHER_RESIDUAL_RISK,
                risk_weight_key="OTHER_0_1_PERCENT",
                reason_code=f"PRA_UK_CRR_{evidence_type.value}",
                citation_id="uk_rts_2022_2328_article_2_annex",
            )
            for evidence_type in _EU_ARTICLE_2_EVIDENCE_TYPES
        ),
    ),
}

PROFILE_INVESTMENT_FUND_RULES: dict[
    RraoRegulatoryProfile,
    tuple[RraoInvestmentFundRule, ...],
] = {
    RraoRegulatoryProfile.BASEL_MAR23: (),
    RraoRegulatoryProfile.US_NPR_2_0: (
        RraoInvestmentFundRule(
            included_exposure_type=RraoInvestmentFundExposureType.EXOTIC_EXPOSURE,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="US_NPR_INVESTMENT_FUND_EXOTIC_PORTION",
            citation_ids=(
                "us_npr_211_a_3",
                "us_npr_205_e_3_iii",
                "us_npr_211_c_1_i",
            ),
        ),
        RraoInvestmentFundRule(
            included_exposure_type=RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight_key="OTHER_0_1_PERCENT",
            reason_code="US_NPR_INVESTMENT_FUND_OTHER_RESIDUAL_PORTION",
            citation_ids=(
                "us_npr_211_a_3",
                "us_npr_205_e_3_iii",
                "us_npr_211_c_1_ii",
            ),
        ),
    ),
    RraoRegulatoryProfile.EU_CRR3: (),
    RraoRegulatoryProfile.PRA_UK_CRR: (),
}

__all__ = [
    "PROFILE_EVIDENCE_RULES",
    "PROFILE_INVESTMENT_FUND_RULES",
]
