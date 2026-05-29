from __future__ import annotations

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_rrao import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInputError,
    RraoInvestmentFundExposureType,
    RraoRegulatoryProfile,
)
from frtb_rrao.reference_data import (
    citations_for_profile,
    evidence_rule_for,
    evidence_rules_for_profile,
    exclusion_rule_for,
    exclusion_rules_for_profile,
    investment_fund_rule_for,
    investment_fund_rules_for_profile,
    risk_weight_rule_for,
    risk_weight_rules_for_profile,
)


@pytest.mark.parametrize(
    "profile",
    [
        RraoRegulatoryProfile.BASEL_MAR23,
        RraoRegulatoryProfile.US_NPR_2_0,
        RraoRegulatoryProfile.EU_CRR3,
    ],
)
def test_reference_data_entries_have_citations(profile: RraoRegulatoryProfile) -> None:
    citations = citations_for_profile(profile)

    assert citations
    for rule in evidence_rules_for_profile(profile):
        assert rule.citation_id in citations
    for rule in exclusion_rules_for_profile(profile):
        assert rule.citation_id in citations
    for rule in investment_fund_rules_for_profile(profile):
        for citation_id in rule.citation_ids:
            assert citation_id in citations
    for rule in risk_weight_rules_for_profile(profile):
        assert rule.citation_id in citations


def test_us_npr_reference_data_contains_supervisor_and_profile_specific_exclusions() -> None:
    evidence_rule = evidence_rule_for(
        RraoRegulatoryProfile.US_NPR_2_0,
        RraoEvidenceType.SUPERVISOR_DIRECTIVE,
    )
    exclusion_rule = exclusion_rule_for(
        RraoRegulatoryProfile.US_NPR_2_0,
        RraoExclusionReason.GOVERNMENT_OR_GSE_DEBT,
    )

    assert evidence_rule.classification is RraoClassification.SUPERVISOR_DIRECTED
    assert evidence_rule.risk_weight_key == "SUPERVISOR_DIRECTED_0_1_PERCENT"
    assert evidence_rule.citation_id == "us_npr_211_a_4"
    assert exclusion_rule.risk_weight_key == "EXCLUDED_0_PERCENT"
    assert exclusion_rule.citation_id == "us_npr_211_b_2_iii"


def test_us_npr_reference_data_contains_investment_fund_inclusion_rules() -> None:
    exotic_rule = investment_fund_rule_for(
        RraoRegulatoryProfile.US_NPR_2_0,
        RraoInvestmentFundExposureType.EXOTIC_EXPOSURE,
    )
    other_rule = investment_fund_rule_for(
        RraoRegulatoryProfile.US_NPR_2_0,
        RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
    )

    assert exotic_rule.classification is RraoClassification.EXOTIC
    assert exotic_rule.risk_weight_key == "EXOTIC_1_PERCENT"
    assert "us_npr_211_a_3" in exotic_rule.citation_ids
    assert "us_npr_205_e_3_iii" in exotic_rule.citation_ids
    assert other_rule.classification is RraoClassification.OTHER_RESIDUAL_RISK
    assert other_rule.risk_weight_key == "OTHER_0_1_PERCENT"
    assert "us_npr_211_a_3" in other_rule.citation_ids


def test_basel_reference_data_keeps_us_specific_paths_unsupported() -> None:
    with pytest.raises(RraoInputError, match="no RRAO evidence rule"):
        evidence_rule_for(RraoRegulatoryProfile.BASEL_MAR23, RraoEvidenceType.SUPERVISOR_DIRECTIVE)
    with pytest.raises(RraoInputError, match="no RRAO exclusion rule"):
        exclusion_rule_for(
            RraoRegulatoryProfile.BASEL_MAR23,
            RraoExclusionReason.GOVERNMENT_OR_GSE_DEBT,
        )
    with pytest.raises(RraoInputError, match="no RRAO investment-fund rule"):
        investment_fund_rule_for(
            RraoRegulatoryProfile.BASEL_MAR23,
            RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
        )


def test_eu_reference_data_contains_rts_annex_and_article_3_mappings() -> None:
    annex_rule = evidence_rule_for(
        RraoRegulatoryProfile.EU_CRR3,
        RraoEvidenceType.PATH_DEPENDENT_OPTION,
    )
    article_3_rule = exclusion_rule_for(
        RraoRegulatoryProfile.EU_CRR3,
        RraoExclusionReason.EU_ARTICLE_3_INDEX_OPTION_CORRELATION,
    )

    assert annex_rule.classification is RraoClassification.OTHER_RESIDUAL_RISK
    assert annex_rule.risk_weight_key == "OTHER_0_1_PERCENT"
    assert annex_rule.citation_id == "eu_rts_2022_2328_article_2_annex"
    assert article_3_rule.risk_weight_key == "NON_PRESUMPTIVE_0_PERCENT"
    assert article_3_rule.citation_id == "eu_rts_2022_2328_article_3"


@pytest.mark.parametrize(
    ("profile", "key", "weight", "classification"),
    [
        (
            RraoRegulatoryProfile.BASEL_MAR23,
            "EXOTIC_1_PERCENT",
            0.01,
            RraoClassification.EXOTIC,
        ),
        (
            RraoRegulatoryProfile.BASEL_MAR23,
            "OTHER_0_1_PERCENT",
            0.001,
            RraoClassification.OTHER_RESIDUAL_RISK,
        ),
        (
            RraoRegulatoryProfile.US_NPR_2_0,
            "EXOTIC_1_PERCENT",
            0.01,
            RraoClassification.EXOTIC,
        ),
        (
            RraoRegulatoryProfile.US_NPR_2_0,
            "OTHER_0_1_PERCENT",
            0.001,
            RraoClassification.OTHER_RESIDUAL_RISK,
        ),
        (
            RraoRegulatoryProfile.EU_CRR3,
            "EXOTIC_1_PERCENT",
            0.01,
            RraoClassification.EXOTIC,
        ),
        (
            RraoRegulatoryProfile.EU_CRR3,
            "OTHER_0_1_PERCENT",
            0.001,
            RraoClassification.OTHER_RESIDUAL_RISK,
        ),
        (
            RraoRegulatoryProfile.EU_CRR3,
            "NON_PRESUMPTIVE_0_PERCENT",
            0.0,
            RraoClassification.EXCLUDED,
        ),
    ],
)
def test_risk_weight_lookup(
    profile: RraoRegulatoryProfile,
    key: str,
    weight: float,
    classification: RraoClassification,
) -> None:
    rule = risk_weight_rule_for(profile, key)

    assert rule.risk_weight == weight
    assert rule.classification is classification
    assert rule.citation_id


def test_missing_risk_weight_lookup_fails_deterministically() -> None:
    with pytest.raises(RraoInputError, match="no RRAO risk-weight rule"):
        risk_weight_rule_for(RraoRegulatoryProfile.US_NPR_2_0, "NOT_A_RULE")


def test_unsupported_profile_reference_data_fails_closed() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        citations_for_profile(RraoRegulatoryProfile.PRA_UK_CRR)
