from __future__ import annotations

import re
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError, stable_json_hash
from frtb_sbm import (
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    get_sbm_rule_profile,
    profile_content_hash,
    resolve_sbm_profile,
)
from frtb_sbm.reference_data import profile_reference_payload
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
            SbmRiskClass.CSR_NONSEC,
            SbmRiskClass.CSR_SEC_NONCTP,
            SbmRiskClass.CSR_SEC_CTP,
        }
    )
    assert profile.supported_measures[SbmRiskClass.CSR_NONSEC] == frozenset(
        {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
    )
    assert profile.supported_measures[SbmRiskClass.GIRR] == frozenset(
        {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
    )
    assert profile.supported_measures[SbmRiskClass.FX] == frozenset(
        {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
    )
    assert "basel_mar21_42" in profile.citations
    assert "basel_mar21_87" in profile.citations
    assert "basel_mar21_92" in profile.citations
    assert "basel_mar21_43" in profile.citations
    assert "basel_mar21_6_correlation_scenarios" in profile.citations


def test_profile_content_hash_is_deterministic_and_profile_specific() -> None:
    basel_profile = get_sbm_rule_profile(SbmRegulatoryProfile.BASEL_MAR21)
    us_npr_profile = get_sbm_rule_profile(SbmRegulatoryProfile.US_NPR_2_0)

    assert re.fullmatch(r"[0-9a-f]{64}", basel_profile.content_hash)
    assert basel_profile.content_hash == profile_content_hash(SbmRegulatoryProfile.BASEL_MAR21)
    assert basel_profile.content_hash == get_sbm_rule_profile("BASEL_MAR21").content_hash
    assert re.fullmatch(r"[0-9a-f]{64}", us_npr_profile.content_hash)
    assert us_npr_profile.content_hash == profile_content_hash(SbmRegulatoryProfile.US_NPR_2_0)
    assert us_npr_profile.content_hash != basel_profile.content_hash


def test_profile_content_hash_uses_common_stable_json_hash() -> None:
    payload = {
        "metadata": {
            "effective_date": None,
            "publication_date": "2026-03-27",
            "regulator": (
                "Office of the Comptroller of the Currency, Board of Governors of the "
                "Federal Reserve System, and Federal Deposit Insurance Corporation"
            ),
            "status": (
                "supported_us_npr_girr_delta_vega_curvature_fx_delta_vega_curvature_"
                "equity_commodity_delta_comparison_slice"
            ),
            "version": "Federal Register 91 FR 14952 proposed market-risk rule",
        },
        "supported_measures": {
            "COMMODITY": ["DELTA"],
            "EQUITY": ["DELTA"],
            "FX": ["CURVATURE", "DELTA", "VEGA"],
            "GIRR": ["CURVATURE", "DELTA", "VEGA"],
        },
        "reference_data": profile_reference_payload(SbmRegulatoryProfile.US_NPR_2_0),
    }

    assert profile_content_hash(SbmRegulatoryProfile.US_NPR_2_0) == stable_json_hash(payload)


def test_pra_uk_crr_profile_content_hash_uses_common_stable_json_hash() -> None:
    payload = {
        "metadata": {
            "effective_date": "2027-01-01",
            "publication_date": "2026-01-20",
            "regulator": "Prudential Regulation Authority",
            "status": "supported_pra_uk_crr_girr_delta_vega_curvature_comparison_slice",
            "version": (
                "PRA PS1/26 Appendix 1 / PRA2026/1 Market Risk: Advanced "
                "Standardised Approach (CRR) Part"
            ),
        },
        "supported_measures": {"GIRR": ["CURVATURE", "DELTA", "VEGA"]},
        "reference_data": profile_reference_payload(SbmRegulatoryProfile.PRA_UK_CRR),
    }

    assert profile_content_hash(SbmRegulatoryProfile.PRA_UK_CRR) == stable_json_hash(payload)


def test_get_sbm_rule_profile_returns_partial_us_npr_profile() -> None:
    profile = get_sbm_rule_profile(SbmRegulatoryProfile.US_NPR_2_0)

    assert resolve_sbm_profile(SbmRegulatoryProfile.US_NPR_2_0) is SbmRegulatoryProfile.US_NPR_2_0
    assert profile.profile_id == SbmRegulatoryProfile.US_NPR_2_0.value
    assert profile.publication_date == date(2026, 3, 27)
    assert profile.supported_risk_classes == frozenset(
        {SbmRiskClass.GIRR, SbmRiskClass.FX, SbmRiskClass.EQUITY, SbmRiskClass.COMMODITY}
    )
    assert profile.supported_measures == {
        SbmRiskClass.GIRR: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.FX: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.EQUITY: frozenset({SbmRiskMeasure.DELTA}),
        SbmRiskClass.COMMODITY: frozenset({SbmRiskMeasure.DELTA}),
    }
    assert "us_npr_91_fr_14952_va7a_girr_delta_weights" in profile.citations
    assert "us_npr_91_fr_14952_va7a_girr_vega_lh_rw" in profile.citations
    assert "us_npr_91_fr_14952_va7a_girr_curvature_shocks" in profile.citations
    assert "us_npr_91_fr_14952_va7a_fx_delta_weights" in profile.citations
    assert "us_npr_91_fr_14952_va7a_fx_vega_lh_rw" in profile.citations
    assert "us_npr_91_fr_14952_va7a_fx_curvature_shocks" in profile.citations
    assert "us_npr_91_fr_14952_va7a_equity_delta_weights" in profile.citations
    assert "us_npr_91_fr_14952_va7a_commodity_delta_weights" in profile.citations


def test_get_sbm_rule_profile_returns_partial_eu_crr3_profile() -> None:
    profile = get_sbm_rule_profile(SbmRegulatoryProfile.EU_CRR3)

    assert resolve_sbm_profile(SbmRegulatoryProfile.EU_CRR3) is SbmRegulatoryProfile.EU_CRR3
    assert profile.profile_id == SbmRegulatoryProfile.EU_CRR3.value
    assert profile.publication_date == date(2024, 6, 19)
    assert profile.supported_risk_classes == frozenset(
        {SbmRiskClass.GIRR, SbmRiskClass.FX, SbmRiskClass.EQUITY, SbmRiskClass.COMMODITY}
    )
    assert profile.supported_measures[SbmRiskClass.GIRR] == frozenset(
        {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
    )
    assert profile.supported_measures[SbmRiskClass.FX] == frozenset(
        {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
    )
    assert profile.supported_measures[SbmRiskClass.EQUITY] == frozenset({SbmRiskMeasure.DELTA})
    assert profile.supported_measures[SbmRiskClass.COMMODITY] == frozenset({SbmRiskMeasure.DELTA})
    assert "eu_crr3_42" in profile.citations
    assert "eu_crr3_87" in profile.citations


def test_get_sbm_rule_profile_returns_partial_pra_uk_crr_profile() -> None:
    profile = get_sbm_rule_profile(SbmRegulatoryProfile.PRA_UK_CRR)

    assert resolve_sbm_profile(SbmRegulatoryProfile.PRA_UK_CRR) is SbmRegulatoryProfile.PRA_UK_CRR
    assert profile.profile_id == SbmRegulatoryProfile.PRA_UK_CRR.value
    assert profile.regulator == "Prudential Regulation Authority"
    assert profile.publication_date == date(2026, 1, 20)
    assert profile.effective_date == date(2027, 1, 1)
    assert profile.supported_risk_classes == frozenset({SbmRiskClass.GIRR})
    assert profile.supported_measures == {
        SbmRiskClass.GIRR: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
    }
    assert "pra_uk_crr_325ae_girr_delta_weights" in profile.citations
    assert "pra_uk_crr_325ax_vega_risk_weights" in profile.citations
    assert "pra_uk_crr_325ax_curvature_risk_weights" in profile.citations
    assert "basel_mar21_42" not in profile.citations


def test_unknown_profile_fails_as_input_error() -> None:
    with pytest.raises(SbmInputError, match="unknown SBM regulatory profile"):
        resolve_sbm_profile("NOT_A_PROFILE")


@pytest.mark.parametrize(
    ("risk_class", "risk_measure", "supported"),
    [
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA, True),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, True),
        (SbmRiskClass.FX, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.FX, SbmRiskMeasure.VEGA, True),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA, True),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA, True),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA, True),
        (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA, True),
        (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA, True),
        (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA, True),
        (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE, True),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE, True),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE, True),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE, True),
        (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE, True),
        (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE, True),
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
        error_match = (
            "curvature capital is unsupported"
            if risk_measure is SbmRiskMeasure.CURVATURE
            else "phase-1 capital"
        )
        with pytest.raises(UnsupportedRegulatoryFeatureError, match=error_match):
            ensure_profile_supports_risk_class_measure(
                SbmRegulatoryProfile.BASEL_MAR21,
                risk_class,
                risk_measure,
            )


def test_supported_risk_class_measures_lists_delta_vega_and_curvature_paths() -> None:
    supported = supported_risk_class_measures(SbmRegulatoryProfile.BASEL_MAR21)

    assert supported == frozenset(
        {
            (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
            (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
            (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
            (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA),
            (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
            (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA),
            (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
            (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA),
            (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
            (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA),
            (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
            (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA),
            (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE),
        }
    )


def test_us_npr_profile_support_map_includes_girr_fx_and_non_girr_delta() -> None:
    supported = supported_risk_class_measures(SbmRegulatoryProfile.US_NPR_2_0)
    expected = frozenset(
        {
            (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
            (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
            (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
            (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        }
    )

    assert supported == expected
    ordered_expected = sorted(expected, key=lambda item: (item[0].value, item[1].value))
    for risk_class, risk_measure in ordered_expected:
        assert profile_supports_risk_class_measure(
            SbmRegulatoryProfile.US_NPR_2_0,
            risk_class,
            risk_measure,
        )
        ensure_profile_supports_risk_class_measure(
            SbmRegulatoryProfile.US_NPR_2_0,
            risk_class,
            risk_measure,
        )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="US_NPR_2_0"):
        ensure_profile_supports_risk_class_measure(
            SbmRegulatoryProfile.US_NPR_2_0,
            SbmRiskClass.EQUITY,
            SbmRiskMeasure.VEGA,
        )


def test_pra_uk_crr_profile_support_map_is_girr_delta_vega_and_curvature_only() -> None:
    supported = supported_risk_class_measures(SbmRegulatoryProfile.PRA_UK_CRR)

    expected = frozenset(
        {
            (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        }
    )
    assert supported == expected
    for _, risk_measure in expected:
        assert profile_supports_risk_class_measure(
            SbmRegulatoryProfile.PRA_UK_CRR,
            SbmRiskClass.GIRR,
            risk_measure,
        )
        ensure_profile_supports_risk_class_measure(
            SbmRegulatoryProfile.PRA_UK_CRR,
            SbmRiskClass.GIRR,
            risk_measure,
        )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="PRA_UK_CRR"):
        ensure_profile_supports_risk_class_measure(
            SbmRegulatoryProfile.PRA_UK_CRR,
            SbmRiskClass.FX,
            SbmRiskMeasure.DELTA,
        )
