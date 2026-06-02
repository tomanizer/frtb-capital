from __future__ import annotations

import pytest
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    CreditQuality,
    DrcBucketType,
    DrcInputError,
    DrcRiskClass,
    DrcSeniority,
    get_bucket_definition,
    get_lgd_rule,
    get_maturity_policy,
    get_risk_weight_rule,
    get_rule_profile,
    iter_bucket_definitions,
    iter_lgd_rules,
    iter_risk_weight_rules,
)


def test_us_npr_lgd_table_contains_cited_non_securitisation_values() -> None:
    expected = {
        DrcSeniority.EQUITY: 1.00,
        DrcSeniority.NON_SENIOR_DEBT: 1.00,
        DrcSeniority.SENIOR_DEBT: 0.75,
        DrcSeniority.GSE_ISSUED_NOT_GUARANTEED: 0.75,
        DrcSeniority.PSE: 0.50,
        DrcSeniority.GSE_GUARANTEED: 0.25,
        DrcSeniority.COVERED_BOND: 0.25,
        DrcSeniority.NOT_RECOVERY_LINKED: 0.00,
    }

    for seniority, expected_lgd in expected.items():
        rule = get_lgd_rule(seniority)
        assert rule.lgd_rate == expected_lgd
        assert rule.citation_id == "US_NPR_210_B_1_IV"

    for seniority in DrcSeniority:
        defaulted_rule = get_lgd_rule(seniority, is_defaulted=True)
        assert defaulted_rule.lgd_rate == 1.00
        assert defaulted_rule.citation_id == "US_NPR_210_B_1_IV"


def test_us_npr_maturity_policy_is_cited() -> None:
    policy = get_maturity_policy()

    assert policy.profile_id == US_NPR_2_0_PROFILE_ID
    assert policy.floor_years == 0.25
    assert policy.full_weight_years == 1.0
    assert policy.citation_id == "US_NPR_210_A_2_III"


def test_us_npr_nonsec_bucket_definitions_are_cited() -> None:
    buckets = {bucket.bucket_key: bucket for bucket in iter_bucket_definitions()}

    assert set(buckets) == {"NON_US_SOVEREIGN", "PSE_GSE", "CORPORATE", "DEFAULTED"}
    assert buckets["NON_US_SOVEREIGN"].bucket_type is DrcBucketType.NON_US_SOVEREIGN
    assert buckets["CORPORATE"].risk_class is DrcRiskClass.NON_SECURITISATION
    assert all(bucket.citation_id == "US_NPR_210_B_3_I" for bucket in buckets.values())


def test_us_npr_risk_weight_table_uses_strict_lookup_keys() -> None:
    expected = {
        ("NON_US_SOVEREIGN", CreditQuality.INVESTMENT_GRADE): 0.006,
        ("NON_US_SOVEREIGN", CreditQuality.SPECULATIVE_GRADE): 0.22,
        ("NON_US_SOVEREIGN", CreditQuality.SUB_SPECULATIVE_GRADE): 0.50,
        ("PSE_GSE", CreditQuality.INVESTMENT_GRADE): 0.021,
        ("PSE_GSE", CreditQuality.SPECULATIVE_GRADE): 0.22,
        ("PSE_GSE", CreditQuality.SUB_SPECULATIVE_GRADE): 0.50,
        ("CORPORATE", CreditQuality.INVESTMENT_GRADE): 0.041,
        ("CORPORATE", CreditQuality.SPECULATIVE_GRADE): 0.22,
        ("CORPORATE", CreditQuality.SUB_SPECULATIVE_GRADE): 0.50,
        ("DEFAULTED", CreditQuality.DEFAULTED): 1.00,
    }

    for (bucket_key, credit_quality), expected_risk_weight in expected.items():
        rule = get_risk_weight_rule(bucket_key, credit_quality)
        assert rule.risk_weight == expected_risk_weight
        assert rule.citation_id == "US_NPR_210_B_3_II"

    with pytest.raises(DrcInputError, match="missing DRC risk weight"):
        get_risk_weight_rule("CORPORATE", CreditQuality.UNRATED)


def test_reference_data_entries_have_profile_citations() -> None:
    profile = get_rule_profile()
    citation_ids = set(profile.citations)

    for rule in iter_lgd_rules():
        assert rule.citation_id in citation_ids
    for bucket in iter_bucket_definitions():
        assert bucket.citation_id in citation_ids
    for risk_weight in iter_risk_weight_rules():
        assert risk_weight.citation_id in citation_ids
    assert get_maturity_policy().citation_id in citation_ids


def test_missing_reference_data_is_input_error() -> None:
    with pytest.raises(DrcInputError, match="missing DRC bucket definition"):
        get_bucket_definition("MISSING")
