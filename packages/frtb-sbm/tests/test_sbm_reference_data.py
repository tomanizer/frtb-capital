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
    FX_DELTA_RISK_WEIGHT,
    FX_INTER_BUCKET_CORRELATION,
    apply_correlation_scenario,
    citations_for_profile,
    commodity_bucket_definition,
    commodity_buckets_for_profile,
    commodity_delta_intra_bucket_correlation,
    commodity_delta_risk_weight,
    commodity_inter_bucket_correlation,
    correlation_scenario_definition,
    correlation_scenarios_for_profile,
    equity_bucket_definition,
    equity_buckets_for_profile,
    equity_delta_intra_bucket_correlation,
    equity_delta_risk_weight,
    equity_inter_bucket_correlation,
    fx_bucket_definition,
    fx_delta_risk_weight,
    fx_inter_bucket_correlation,
    girr_bucket_definition,
    girr_bucket_for_currency,
    girr_buckets_for_profile,
    girr_delta_intra_bucket_correlation,
    girr_delta_risk_weight,
    girr_delta_risk_weight_rule,
    girr_inter_bucket_correlation,
    girr_tenor_definition,
    girr_tenors_for_profile,
    girr_vega_intra_bucket_correlation,
    girr_vega_liquidity_horizon_days,
    girr_vega_option_tenors,
    vega_risk_weight,
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
    for bucket in equity_buckets_for_profile(profile):
        assert bucket.citation_id in citations
    for bucket in commodity_buckets_for_profile(profile):
        assert bucket.citation_id in citations


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


def test_girr_vega_liquidity_horizon_and_risk_weight() -> None:
    horizon = girr_vega_liquidity_horizon_days(SbmRegulatoryProfile.BASEL_MAR21)

    assert horizon == 60
    risk_weight, citation_ids = vega_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        liquidity_horizon_days=horizon,
    )
    assert risk_weight == 1.0
    assert citation_ids == ("basel_mar21_92",)
    assert len(girr_vega_option_tenors(SbmRegulatoryProfile.BASEL_MAR21)) == len(
        girr_tenors_for_profile(SbmRegulatoryProfile.BASEL_MAR21)
    )


def test_girr_vega_intra_bucket_correlation() -> None:
    correlation, citation_ids = girr_vega_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        option_tenor1="5y",
        option_tenor2="5y",
        tenor1="1y",
        tenor2="5y",
    )

    rho_opt = 1.0
    rho_ul = math.exp(-0.01 * abs(1.0 - 5.0) / 1.0)
    assert correlation == pytest.approx(min(1.0, rho_opt * rho_ul))
    assert citation_ids == ("basel_mar21_93",)


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


def test_fx_delta_reference_data_matches_basel_mar21() -> None:
    reduced, citations = fx_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        currency="EUR",
        reporting_currency="USD",
    )
    full, _ = fx_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        currency="MYR",
        reporting_currency="USD",
    )
    inter_bucket, inter_citations = fx_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1="EUR",
        bucket2="GBP",
    )

    assert reduced == pytest.approx(FX_DELTA_RISK_WEIGHT / math.sqrt(2.0))
    assert full == pytest.approx(FX_DELTA_RISK_WEIGHT)
    assert inter_bucket == pytest.approx(FX_INTER_BUCKET_CORRELATION)
    assert "basel_mar21_87" in citations
    assert "basel_mar21_88" in citations
    assert inter_citations == ("basel_mar21_89",)
    bucket = fx_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21, "EUR")
    assert bucket.citation_id == "basel_mar21_86"


@pytest.mark.parametrize(
    ("bucket_id", "spot_weight", "repo_weight"),
    [
        ("5", 0.30, 0.0030),
        ("6", 0.35, 0.0035),
    ],
)
def test_equity_delta_reference_data_matches_basel_mar21(
    bucket_id: str,
    spot_weight: float,
    repo_weight: float,
) -> None:
    spot, spot_citations = equity_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id=bucket_id,
        risk_factor="SPOT",
    )
    repo, repo_citations = equity_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id=bucket_id,
        risk_factor="REPO",
    )
    intra, intra_citations = equity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id=bucket_id,
        risk_factor_a="SPOT",
        risk_factor_b="SPOT",
        issuer_a="ISS-A",
        issuer_b="ISS-B",
    )
    _inter, inter_citations = equity_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1=bucket_id,
        bucket2="6" if bucket_id != "6" else "5",
    )

    assert spot == pytest.approx(spot_weight)
    assert repo == pytest.approx(repo_weight)
    assert spot_citations == ("basel_mar21_77",)
    assert repo_citations == ("basel_mar21_77",)
    assert intra_citations == ("basel_mar21_78",)
    assert inter_citations == ("basel_mar21_80",)
    assert intra > 0.0
    bucket = equity_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21, bucket_id)
    assert bucket.citation_id == "basel_mar21_72"


def test_equity_other_sector_bucket_weights_and_zero_inter_correlation() -> None:
    spot, repo = (
        equity_delta_risk_weight(
            SbmRegulatoryProfile.BASEL_MAR21,
            bucket_id="11",
            risk_factor="SPOT",
        ),
        equity_delta_risk_weight(
            SbmRegulatoryProfile.BASEL_MAR21,
            bucket_id="11",
            risk_factor="REPO",
        ),
    )
    inter, inter_citations = equity_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1="11",
        bucket2="5",
    )

    assert spot[0] == pytest.approx(0.70)
    assert repo[0] == pytest.approx(0.0070)
    assert inter == pytest.approx(0.0)
    assert inter_citations == ("basel_mar21_80",)


@pytest.mark.parametrize(
    ("bucket_id", "risk_weight", "commodity_correlation"),
    [
        ("2", 0.35, 0.95),
        ("5", 0.40, 0.60),
        ("11", 0.50, 0.15),
    ],
)
def test_commodity_delta_reference_data_matches_basel_mar21(
    bucket_id: str,
    risk_weight: float,
    commodity_correlation: float,
) -> None:
    weight, weight_citations = commodity_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id=bucket_id,
    )
    intra, intra_citations = commodity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id=bucket_id,
        commodity_a="WTI",
        commodity_b="BRENT",
        tenor_a="3m",
        tenor_b="3m",
        location_a="NYMEX",
        location_b="ICE",
    )
    _inter, inter_citations = commodity_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1=bucket_id,
        bucket2="5" if bucket_id != "5" else "2",
    )

    assert weight == pytest.approx(risk_weight)
    assert weight_citations == ("basel_mar21_82",)
    assert intra == pytest.approx(commodity_correlation * 0.999)
    assert intra_citations == ("basel_mar21_83",)
    assert inter_citations == ("basel_mar21_85",)
    bucket = commodity_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21, bucket_id)
    assert bucket.commodity_correlation == pytest.approx(commodity_correlation)
    assert bucket.citation_id == "basel_mar21_81"


def test_missing_lookup_keys_raise_input_errors() -> None:
    with pytest.raises(SbmInputError, match="no GIRR bucket for currency"):
        girr_bucket_for_currency(SbmRegulatoryProfile.BASEL_MAR21, "ZZZ")
    with pytest.raises(SbmInputError, match="no GIRR bucket definition"):
        girr_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21, "99")
    with pytest.raises(SbmInputError, match="no GIRR tenor definition"):
        girr_tenor_definition(SbmRegulatoryProfile.BASEL_MAR21, "7y")
    with pytest.raises(SbmInputError, match="no GIRR delta risk weight"):
        girr_delta_risk_weight_rule(SbmRegulatoryProfile.BASEL_MAR21, "7y")
    with pytest.raises(SbmInputError, match="no equity bucket definition"):
        equity_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21, "99")
    with pytest.raises(SbmInputError, match="no commodity bucket definition"):
        commodity_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21, "99")


@pytest.mark.parametrize(
    ("risk_class", "risk_measure"),
    [
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA),
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
