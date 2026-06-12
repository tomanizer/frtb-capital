"""RRAO risk-weight reference rules by supported profile."""

from __future__ import annotations

from frtb_rrao._reference_rule_types import RraoRiskWeightRule
from frtb_rrao.data_models import RraoClassification, RraoRegulatoryProfile

PROFILE_RISK_WEIGHT_RULES: dict[RraoRegulatoryProfile, tuple[RraoRiskWeightRule, ...]] = {
    RraoRegulatoryProfile.BASEL_MAR23: (
        RraoRiskWeightRule(
            key="EXOTIC_1_PERCENT",
            classification=RraoClassification.EXOTIC,
            risk_weight=0.01,
            citation_id="basel_mar23_8_2_a",
        ),
        RraoRiskWeightRule(
            key="OTHER_0_1_PERCENT",
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight=0.001,
            citation_id="basel_mar23_8_2_b",
        ),
        RraoRiskWeightRule(
            key="EXCLUDED_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="basel_mar23_4_7",
        ),
    ),
    RraoRegulatoryProfile.US_NPR_2_0: (
        RraoRiskWeightRule(
            key="EXOTIC_1_PERCENT",
            classification=RraoClassification.EXOTIC,
            risk_weight=0.01,
            citation_id="us_npr_211_c_1_i",
        ),
        RraoRiskWeightRule(
            key="OTHER_0_1_PERCENT",
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight=0.001,
            citation_id="us_npr_211_c_1_ii",
        ),
        RraoRiskWeightRule(
            key="SUPERVISOR_DIRECTED_0_1_PERCENT",
            classification=RraoClassification.SUPERVISOR_DIRECTED,
            risk_weight=0.001,
            citation_id="us_npr_211_c_1_ii",
        ),
        RraoRiskWeightRule(
            key="EXCLUDED_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="us_npr_211_b_1",
        ),
    ),
    RraoRegulatoryProfile.EU_CRR3: (
        RraoRiskWeightRule(
            key="EXOTIC_1_PERCENT",
            classification=RraoClassification.EXOTIC,
            risk_weight=0.01,
            citation_id="eu_crr_325u_3_a",
        ),
        RraoRiskWeightRule(
            key="OTHER_0_1_PERCENT",
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight=0.001,
            citation_id="eu_crr_325u_3_b",
        ),
        RraoRiskWeightRule(
            key="EXCLUDED_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="eu_crr_325u_4",
        ),
        RraoRiskWeightRule(
            key="NON_PRESUMPTIVE_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="eu_rts_2022_2328_article_3",
        ),
    ),
    RraoRegulatoryProfile.PRA_UK_CRR: (
        RraoRiskWeightRule(
            key="EXOTIC_1_PERCENT",
            classification=RraoClassification.EXOTIC,
            risk_weight=0.01,
            citation_id="uk_crr_325u_3_a",
        ),
        RraoRiskWeightRule(
            key="OTHER_0_1_PERCENT",
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight=0.001,
            citation_id="uk_crr_325u_3_b",
        ),
        RraoRiskWeightRule(
            key="EXCLUDED_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="uk_crr_325u_4",
        ),
        RraoRiskWeightRule(
            key="NON_PRESUMPTIVE_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="uk_rts_2022_2328_article_3",
        ),
    ),
}


__all__ = ["PROFILE_RISK_WEIGHT_RULES"]
