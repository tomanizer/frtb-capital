from __future__ import annotations

import math

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
)
from frtb_sbm.reference_data import (
    apply_correlation_scenario,
    citations_for_profile,
    correlation_scenario_definition,
    correlation_scenarios_for_profile,
    girr_bucket_definition,
    girr_bucket_for_currency,
    girr_buckets_for_profile,
    girr_delta_intra_bucket_correlation,
    girr_delta_risk_weight,
    girr_delta_risk_weight_rule,
    girr_inter_bucket_correlation,
    girr_tenor_definition,
    girr_tenors_for_profile,
)
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure


def test_reference_data_entries_have_citations() -> None:
    profile = SbmRegulatoryProfile.BASEL_MAR21
    citations = citations_for_profile(profile)

    assert citations
    for bucket in girr_buckets_for_profile(profile):
        assert bucket.citation_id in citations
    for tenor in girr_tenors_for_profile(profile):
        assert tenor.citation_id in citations
    for scenario in correlation_scenarios_for_profile(profile):
        assert scenario.citation_id in citations


@pytest.mark.parametrize(
    ("currency", "bucket_id"),
    [
        ("EUR", "1"),
        ("USD", "2"),
        ("GBP", "3"),
        ("JPY", "4"),
        ("SEK", "14"),
    ],
)
def test_girr_bucket_lookup_by_currency(currency: str, bucket_id: str) -> None:
    bucket = girr_bucket_for_currency(SbmRegulatoryProfile.BASEL_MAR21, currency)

    assert bucket.bucket_id == bucket_id
    assert bucket.currency == currency
    assert bucket.citation_id == "basel_mar21_38"


def test_girr_bucket_lookup_by_id() -> None:
    bucket = girr_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21, "2")

    assert bucket.currency == "USD"


@pytest.mark.parametrize(
    ("tenor", "maturity_years", "risk_weight"),
    [
        ("3m", 0.25, 0.017),
        ("1y", 1.0, 0.016),
        ("5y", 5.0, 0.011),
        ("30y", 30.0, 0.011),
    ],
)
def test_girr_delta_risk_weights(tenor: str, maturity_years: float, risk_weight: float) -> None:
    tenor_definition = girr_tenor_definition(SbmRegulatoryProfile.BASEL_MAR21, tenor)
    rule = girr_delta_risk_weight_rule(SbmRegulatoryProfile.BASEL_MAR21, tenor)

    assert tenor_definition.maturity_years == maturity_years
    assert rule.risk_weight == risk_weight
    assert rule.citation_id == "basel_mar21_39"


def test_girr_delta_risk_weight_applies_liquid_currency_sqrt2_adjustment() -> None:
    adjusted, citation_ids = girr_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor="5y",
        currency="USD",
        reporting_currency="USD",
    )

    assert adjusted == pytest.approx(0.011 / math.sqrt(2.0))
    assert citation_ids == ("basel_mar21_39", "basel_mar21_40")


def test_girr_delta_risk_weight_skips_sqrt2_for_special_factors() -> None:
    adjusted, citation_ids = girr_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor="INFL",
        currency="USD",
        reporting_currency="USD",
    )

    assert adjusted == 0.016
    assert citation_ids == ("basel_mar21_39",)


def test_girr_delta_intra_bucket_correlation_uses_exponential_tenor_formula() -> None:
    correlation, citation_ids = girr_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor1="1y",
        tenor2="5y",
        same_curve=True,
    )

    expected = math.exp(-0.03 * abs(1.0 - 5.0) / 1.0)
    assert correlation == pytest.approx(expected)
    assert citation_ids == ("basel_mar21_41",)


def test_girr_delta_intra_bucket_correlation_handles_inflation_and_xccy() -> None:
    inflation_same, _ = girr_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor1="INFL",
        tenor2="INFL",
        same_curve=False,
    )
    inflation_diff, _ = girr_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor1="INFL",
        tenor2="1y",
        same_curve=False,
    )
    xccy_ir, _ = girr_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor1="XCCY",
        tenor2="1y",
        same_curve=False,
    )
    xccy_xccy, _ = girr_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor1="XCCY",
        tenor2="XCCY",
        same_curve=False,
    )

    assert inflation_same == 1.0
    assert inflation_diff == 0.40
    assert xccy_ir == 0.0
    assert xccy_xccy == 1.0


def test_girr_inter_bucket_correlation() -> None:
    same_bucket, _ = girr_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1="1",
        bucket2="1",
    )
    different_buckets, citation_ids = girr_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1="1",
        bucket2="2",
    )

    assert same_bucket == 1.0
    assert different_buckets == 0.50
    assert citation_ids == ("basel_mar21_42",)


@pytest.mark.parametrize(
    ("scenario", "base", "expected"),
    [
        (SbmScenarioLabel.LOW, 0.50, 0.375),
        (SbmScenarioLabel.MEDIUM, 0.50, 0.50),
        (SbmScenarioLabel.HIGH, 0.80, 1.0),
    ],
)
def test_correlation_scenario_adjustments(
    scenario: SbmScenarioLabel,
    base: float,
    expected: float,
) -> None:
    adjusted, citation_ids = apply_correlation_scenario(
        SbmRegulatoryProfile.BASEL_MAR21,
        base_correlation=base,
        scenario=scenario,
    )

    assert adjusted == pytest.approx(expected)
    assert citation_ids == ("basel_mar21_43",)


def test_correlation_scenario_definitions_cover_low_medium_high() -> None:
    scenarios = {
        definition.scenario
        for definition in correlation_scenarios_for_profile(SbmRegulatoryProfile.BASEL_MAR21)
    }

    assert scenarios == {
        SbmScenarioLabel.LOW,
        SbmScenarioLabel.MEDIUM,
        SbmScenarioLabel.HIGH,
    }
    low_scenario = correlation_scenario_definition(
        SbmRegulatoryProfile.BASEL_MAR21,
        SbmScenarioLabel.LOW,
    )
    assert low_scenario.multiplier == 0.75


def test_missing_lookup_keys_raise_input_errors() -> None:
    with pytest.raises(SbmInputError, match="no GIRR bucket for currency"):
        girr_bucket_for_currency(SbmRegulatoryProfile.BASEL_MAR21, "ZZZ")
    with pytest.raises(SbmInputError, match="no GIRR bucket definition"):
        girr_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21, "99")
    with pytest.raises(SbmInputError, match="no GIRR tenor definition"):
        girr_tenor_definition(SbmRegulatoryProfile.BASEL_MAR21, "7y")
    with pytest.raises(SbmInputError, match="no GIRR delta risk weight"):
        girr_delta_risk_weight_rule(SbmRegulatoryProfile.BASEL_MAR21, "7y")


@pytest.mark.parametrize(
    ("risk_class", "risk_measure"),
    [
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
    ],
)
def test_unsupported_risk_class_measure_paths_fail_closed(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="frtb-sbm does not support"):
        ensure_profile_supports_risk_class_measure(
            SbmRegulatoryProfile.BASEL_MAR21,
            risk_class,
            risk_measure,
        )


@pytest.mark.parametrize(
    "profile",
    [
        SbmRegulatoryProfile.US_NPR_2_0,
        SbmRegulatoryProfile.EU_CRR3,
    ],
)
def test_unsupported_profiles_fail_reference_data_lookup(profile: SbmRegulatoryProfile) -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        citations_for_profile(profile)
