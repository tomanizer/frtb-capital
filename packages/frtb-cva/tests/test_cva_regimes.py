from __future__ import annotations

import pytest
from frtb_cva import (
    CvaMethod,
    CvaRegulatoryProfile,
    get_cva_rule_profile,
    profile_content_hash,
)
from frtb_cva.regimes import resolve_cva_profile


def test_basel_profile_is_supported() -> None:
    profile = get_cva_rule_profile(CvaRegulatoryProfile.BASEL_MAR50_2020)
    assert profile.profile is CvaRegulatoryProfile.BASEL_MAR50_2020
    assert profile.content_hash == profile_content_hash(CvaRegulatoryProfile.BASEL_MAR50_2020)
    assert "basel_mar50_14" in profile.citation_ids


def test_profile_hash_is_deterministic() -> None:
    first = get_cva_rule_profile(CvaRegulatoryProfile.BASEL_MAR50_2020)
    second = get_cva_rule_profile(CvaRegulatoryProfile.BASEL_MAR50_2020)
    assert first.content_hash == second.content_hash


@pytest.mark.parametrize(
    ("profile", "expected_citation_id"),
    [
        (CvaRegulatoryProfile.US_NPR20_VB, "us_npr20_vb_ba_cva"),
        (CvaRegulatoryProfile.EU_CRR3_CVA, "eu_crr3_article_384"),
        (CvaRegulatoryProfile.UK_PRA_CVA, "uk_pra_cva_risk_ba"),
    ],
)
def test_non_basel_profiles_are_supported_with_profile_citations(
    profile: CvaRegulatoryProfile,
    expected_citation_id: str,
) -> None:
    assert resolve_cva_profile(profile) is profile
    rule_profile = get_cva_rule_profile(profile)
    assert rule_profile.profile is profile
    assert rule_profile.supported_methods == frozenset(CvaMethod)
    assert expected_citation_id in rule_profile.citation_ids
    assert rule_profile.content_hash == profile_content_hash(profile)


def test_profile_hashes_are_profile_specific() -> None:
    hashes = {profile: profile_content_hash(profile) for profile in CvaRegulatoryProfile}
    assert len(set(hashes.values())) == len(CvaRegulatoryProfile)
