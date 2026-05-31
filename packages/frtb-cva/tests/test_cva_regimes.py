from __future__ import annotations

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import (
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
    "profile",
    [
        CvaRegulatoryProfile.US_NPR20_VB,
        CvaRegulatoryProfile.EU_CRR3_CVA,
        CvaRegulatoryProfile.UK_PRA_CVA,
    ],
)
def test_unsupported_profiles_fail_before_calculation(profile: CvaRegulatoryProfile) -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError):
        resolve_cva_profile(profile)
