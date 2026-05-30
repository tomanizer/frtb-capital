from __future__ import annotations

import re
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    get_sbm_rule_profile,
    profile_content_hash,
    resolve_sbm_profile,
)
from frtb_sbm.regimes import (
    ensure_profile_supports_risk_class_measure,
    profile_supports_risk_class_measure,
    supported_risk_class_measures,
)


def test_get_sbm_rule_profile_returns_supported_basel_profile() -> None:
    profile = get_sbm_rule_profile(SbmRegulatoryProfile.BASEL_MAR21)

    assert profile.profile_id == SbmRegulatoryProfile.BASEL_MAR21.value
    assert profile.regulator == "Basel Committee on Banking Supervision"
    assert profile.publication_date == date(2019, 1, 14)
    assert profile.supported_risk_classes == frozenset(
        {
            SbmRiskClass.GIRR,
            SbmRiskClass.FX,
            SbmRiskClass.EQUITY,
            SbmRiskClass.COMMODITY,
        }
    )
    assert profile.supported_measures[SbmRiskClass.GIRR] == frozenset(
        {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA}
    )
    assert profile.supported_measures[SbmRiskClass.FX] == frozenset({SbmRiskMeasure.DELTA})
    assert "basel_mar21_39" in profile.citations
    assert "basel_mar21_87" in profile.citations
    assert "basel_mar21_92" in profile.citations
    assert "basel_mar21_43" in profile.citations


def test_profile_content_hash_is_deterministic_and_profile_specific() -> None:
    basel_profile = get_sbm_rule_profile(SbmRegulatoryProfile.BASEL_MAR21)

    assert re.fullmatch(r"[0-9a-f]{64}", basel_profile.content_hash)
    assert basel_profile.content_hash == profile_content_hash(SbmRegulatoryProfile.BASEL_MAR21)
    assert basel_profile.content_hash == get_sbm_rule_profile("BASEL_MAR21").content_hash


@pytest.mark.parametrize(
    "profile",
    [
        SbmRegulatoryProfile.US_NPR_2_0,
        SbmRegulatoryProfile.EU_CRR3,
        SbmRegulatoryProfile.PRA_UK_CRR,
    ],
)
def test_unsupported_profiles_fail_before_calculation(profile: SbmRegulatoryProfile) -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        resolve_sbm_profile(profile)
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        get_sbm_rule_profile(profile)


def test_unknown_profile_fails_as_input_error() -> None:
    with pytest.raises(SbmInputError, match="unknown SBM regulatory profile"):
        resolve_sbm_profile("NOT_A_PROFILE")


@pytest.mark.parametrize(
    ("risk_class", "risk_measure", "supported"),
    [
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA, True),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, False),
        (SbmRiskClass.FX, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA, False),
    ],
)
def test_basel_profile_support_map(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    supported: bool,
) -> None:
    assert (
        profile_supports_risk_class_measure(
            SbmRegulatoryProfile.BASEL_MAR21,
            risk_class,
            risk_measure,
        )
        is supported
    )
    if supported:
        ensure_profile_supports_risk_class_measure(
            SbmRegulatoryProfile.BASEL_MAR21,
            risk_class,
            risk_measure,
        )
    else:
        with pytest.raises(UnsupportedRegulatoryFeatureError, match="frtb-sbm does not support"):
            ensure_profile_supports_risk_class_measure(
                SbmRegulatoryProfile.BASEL_MAR21,
                risk_class,
                risk_measure,
            )


def test_supported_risk_class_measures_lists_girr_fx_equity_and_commodity_delta() -> None:
    supported = supported_risk_class_measures(SbmRegulatoryProfile.BASEL_MAR21)

    assert supported == frozenset(
        {
            (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
            (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
            (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
            (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        }
    )
