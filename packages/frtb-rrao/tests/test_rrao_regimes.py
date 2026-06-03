from __future__ import annotations

import re
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_rrao import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInputError,
    RraoRegulatoryProfile,
    get_rrao_rule_profile,
)
from frtb_rrao.regimes import (
    profile_content_hash,
    resolve_rrao_profile,
)


def test_get_rrao_rule_profile_returns_supported_us_profile() -> None:
    profile = get_rrao_rule_profile("US_NPR_2_0")

    assert profile.profile is RraoRegulatoryProfile.US_NPR_2_0
    assert profile.regulator == "U.S. banking agencies"
    assert profile.publication_date == date(2026, 3, 27)
    assert RraoClassification.EXOTIC in profile.supported_classifications
    assert RraoClassification.SUPERVISOR_DIRECTED in profile.supported_classifications
    assert RraoEvidenceType.SUPERVISOR_DIRECTIVE in profile.supported_evidence_types
    assert RraoExclusionReason.AGENCY_DETERMINED_EXCLUSION in profile.supported_exclusions
    assert "us_npr_211_c_1_i" in profile.citation_ids


def test_get_rrao_rule_profile_returns_supported_basel_profile() -> None:
    profile = get_rrao_rule_profile(RraoRegulatoryProfile.BASEL_MAR23)

    assert profile.profile is RraoRegulatoryProfile.BASEL_MAR23
    assert profile.regulator == "Basel Committee on Banking Supervision"
    assert RraoClassification.EXOTIC in profile.supported_classifications
    assert RraoEvidenceType.EXOTIC_UNDERLYING in profile.supported_evidence_types
    assert RraoEvidenceType.SUPERVISOR_DIRECTIVE not in profile.supported_evidence_types
    assert RraoExclusionReason.LISTED in profile.supported_exclusions
    assert RraoExclusionReason.GOVERNMENT_OR_GSE_DEBT not in profile.supported_exclusions


def test_get_rrao_rule_profile_returns_supported_eu_profile() -> None:
    profile = get_rrao_rule_profile(RraoRegulatoryProfile.EU_CRR3)

    assert profile.profile is RraoRegulatoryProfile.EU_CRR3
    assert profile.regulator == "European Union"
    assert profile.publication_date == date(2022, 11, 29)
    assert profile.effective_date == date(2022, 12, 19)
    assert RraoEvidenceType.PATH_DEPENDENT_OPTION in profile.supported_evidence_types
    assert RraoEvidenceType.GAP_RISK not in profile.supported_evidence_types
    assert RraoExclusionReason.EU_ARTICLE_3_INDEX_OPTION_CORRELATION in (
        profile.supported_exclusions
    )
    assert "eu_rts_2022_2328_article_2_annex" in profile.citation_ids


def test_profile_content_hash_is_deterministic_and_profile_specific() -> None:
    us_profile = get_rrao_rule_profile(RraoRegulatoryProfile.US_NPR_2_0)
    basel_profile = get_rrao_rule_profile(RraoRegulatoryProfile.BASEL_MAR23)
    eu_profile = get_rrao_rule_profile(RraoRegulatoryProfile.EU_CRR3)

    assert re.fullmatch(r"[0-9a-f]{64}", us_profile.content_hash)
    assert us_profile.content_hash == profile_content_hash(RraoRegulatoryProfile.US_NPR_2_0)
    assert us_profile.content_hash != basel_profile.content_hash
    assert eu_profile.content_hash != us_profile.content_hash


def test_get_rrao_rule_profile_returns_supported_pra_profile() -> None:
    profile = get_rrao_rule_profile(RraoRegulatoryProfile.PRA_UK_CRR)

    assert profile.profile is RraoRegulatoryProfile.PRA_UK_CRR
    assert profile.regulator == "PRA / UK CRR"
    assert profile.publication_date == date(2026, 1, 20)
    assert profile.effective_date == date(2027, 1, 1)
    assert RraoClassification.EXOTIC in profile.supported_classifications
    assert RraoEvidenceType.PATH_DEPENDENT_OPTION in profile.supported_evidence_types
    assert RraoExclusionReason.EU_ARTICLE_3_INDEX_OPTION_CORRELATION in (
        profile.supported_exclusions
    )
    assert "uk_rts_2022_2328_article_1" in profile.citation_ids


def test_unknown_profile_fails_as_input_error() -> None:
    with pytest.raises(RraoInputError, match="unknown RRAO regulatory profile"):
        resolve_rrao_profile("NOT_A_PROFILE")
