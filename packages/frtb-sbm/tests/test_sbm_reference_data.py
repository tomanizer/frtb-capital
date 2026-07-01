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
    GIRR_INTER_BUCKET_CORRELATION,
    apply_correlation_scenario,
    apply_correlation_scenario_definition,
    citations_for_profile,
    commodity_bucket_definition,
    commodity_buckets_for_profile,
    commodity_delta_intra_bucket_correlation,
    commodity_delta_risk_weight,
    commodity_inter_bucket_correlation,
    correlation_scenario_definition,
    correlation_scenarios_for_profile,
    curvature_risk_weight,
    equity_bucket_definition,
    equity_buckets_for_profile,
    equity_delta_intra_bucket_correlation,
    equity_delta_risk_weight,
    equity_inter_bucket_correlation,
    fx_bucket_definition,
    fx_delta_intra_bucket_correlation,
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
    vega_liquidity_horizon_days,
    vega_option_tenor_correlation,
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


def test_us_npr_fx_policy_citations_are_registered() -> None:
    citations = citations_for_profile(SbmRegulatoryProfile.US_NPR_2_0)

    assert "us_npr_91_fr_14952_va7a_fx_reporting_currency" in citations
    assert "us_npr_91_fr_14952_va7a_fx_delta_weights" in citations
    assert "us_npr_91_fr_14952_va7a_fx_delta_sqrt2" in citations
    assert "us_npr_91_fr_14952_va7a_fx_delta_intra" in citations
    assert "us_npr_91_fr_14952_va7a_fx_delta_inter" in citations
    assert "us_npr_91_fr_14952_va7a_fx_vega_option_tenors" in citations
    assert "us_npr_91_fr_14952_va7a_fx_vega_lh_rw" in citations
    assert "us_npr_91_fr_14952_va7a_fx_vega_intra" in citations
    assert "us_npr_91_fr_14952_va7a_fx_vega_inter" in citations
    assert "us_npr_91_fr_14952_va7a_fx_curvature_factors" in citations
    assert "us_npr_91_fr_14952_va7a_fx_curvature_shocks" in citations
    assert "us_npr_91_fr_14952_va7a_fx_curvature_intra" in citations
    assert "us_npr_91_fr_14952_va7a_fx_curvature_inter" in citations
    assert "us_npr_91_fr_14952_va7a_fx_curvature_scenarios" in citations
    assert "us_npr_91_fr_14952_va7a_fx_base_currency_approval" in citations
    assert "91 FR 15020" in citations["us_npr_91_fr_14952_va7a_fx_base_currency_approval"].location


def test_us_npr_equity_and_commodity_delta_reference_data_uses_profile_owned_citations() -> None:
    citations = citations_for_profile(SbmRegulatoryProfile.US_NPR_2_0)

    equity_bucket = equity_bucket_definition(SbmRegulatoryProfile.US_NPR_2_0, "5")
    equity_weight, equity_weight_citations = equity_delta_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket_id="5",
        risk_factor="SPOT",
    )
    equity_intra, equity_intra_citations = equity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket_id="5",
        risk_factor_a="SPOT",
        risk_factor_b="SPOT",
        issuer_a="Issuer A",
        issuer_b="Issuer B",
    )
    equity_inter, equity_inter_citations = equity_inter_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket1="5",
        bucket2="6",
    )
    commodity_bucket = commodity_bucket_definition(SbmRegulatoryProfile.US_NPR_2_0, "12")
    commodity_weight, commodity_weight_citations = commodity_delta_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket_id="12",
    )
    commodity_intra, commodity_intra_citations = commodity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket_id="12",
        commodity_a="INDEX-A",
        commodity_b="INDEX-B",
        tenor_a="3m",
        tenor_b="6m",
        location_a="Index",
        location_b="Index",
    )
    commodity_inter, commodity_inter_citations = commodity_inter_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket1="10",
        bucket2="12",
    )

    assert "us_npr_91_fr_14952_va7a_equity_delta_factors" in citations
    assert "us_npr_91_fr_14952_va7a_commodity_delta_factors" in citations
    assert equity_bucket.citation_id == "us_npr_91_fr_14952_va7a_equity_delta_buckets"
    assert equity_weight == pytest.approx(0.30)
    assert equity_weight_citations == ("us_npr_91_fr_14952_va7a_equity_delta_weights",)
    assert equity_intra == pytest.approx(0.25)
    assert equity_intra_citations == ("us_npr_91_fr_14952_va7a_equity_delta_intra",)
    assert equity_inter == pytest.approx(0.15)
    assert equity_inter_citations == ("us_npr_91_fr_14952_va7a_equity_delta_inter",)
    assert commodity_bucket.label == "commodity_index"
    assert commodity_bucket.citation_id == "us_npr_91_fr_14952_va7a_commodity_delta_buckets"
    assert commodity_weight == pytest.approx(0.30)
    assert commodity_weight_citations == ("us_npr_91_fr_14952_va7a_commodity_delta_weights",)
    assert commodity_intra == pytest.approx(0.50 * 0.99)
    assert commodity_intra_citations == ("us_npr_91_fr_14952_va7a_commodity_delta_intra",)
    assert commodity_inter == pytest.approx(0.20)
    assert commodity_inter_citations == ("us_npr_91_fr_14952_va7a_commodity_delta_inter",)


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


def test_girr_cny_and_cnh_are_distinct_buckets() -> None:
    cny = girr_bucket_for_currency(SbmRegulatoryProfile.BASEL_MAR21, "CNY")
    cnh = girr_bucket_for_currency(SbmRegulatoryProfile.BASEL_MAR21, "CNH")

    assert cny.bucket_id == "8"
    assert cny.currency == "CNY"
    assert cnh.bucket_id == "17"
    assert cnh.currency == "CNH"


def test_fx_delta_normalises_cnh_to_cny_bucket() -> None:
    bucket = fx_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21, "CNH")

    assert bucket.bucket_id == "CNY"
    assert bucket.currency == "CNY"


def test_fx_delta_risk_weight_treats_cnh_as_cny_for_specified_pairs() -> None:
    reduced, citations = fx_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        currency="CNH",
        reporting_currency="USD",
    )
    cny_reduced, _ = fx_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        currency="CNY",
        reporting_currency="USD",
    )

    assert reduced == cny_reduced
    assert reduced == pytest.approx(FX_DELTA_RISK_WEIGHT / math.sqrt(2.0))
    assert "basel_mar21_88" in citations

    zero_rw, zero_citations = fx_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        currency="CNH",
        reporting_currency="CNH",
    )
    assert zero_rw == 0.0
    assert "basel_mar21_87" in zero_citations

    cny_zero_rw, cny_zero_citations = fx_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        currency="CNY",
        reporting_currency="CNH",
    )
    assert cny_zero_rw == 0.0
    assert "basel_mar21_87" in cny_zero_citations


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
    assert tenor_definition.citation_id == "basel_mar21_42"
    assert rule.risk_weight == risk_weight
    assert rule.citation_id == "basel_mar21_42"


@pytest.mark.parametrize("tenor", ["INFL", "XCCY"])
def test_girr_special_risk_factors_use_special_factor_citation(tenor: str) -> None:
    rule = girr_delta_risk_weight_rule(SbmRegulatoryProfile.BASEL_MAR21, tenor)

    assert rule.risk_weight == 0.016
    assert rule.citation_id == "basel_mar21_43"


def test_girr_delta_risk_weight_applies_liquid_currency_sqrt2_adjustment() -> None:
    adjusted, citation_ids = girr_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor="5y",
        currency="USD",
        reporting_currency="USD",
    )

    assert adjusted == pytest.approx(0.011 / math.sqrt(2.0))
    assert citation_ids == ("basel_mar21_42", "basel_mar21_44")


def test_girr_delta_risk_weight_skips_sqrt2_for_special_factors() -> None:
    adjusted, citation_ids = girr_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor="INFL",
        currency="USD",
        reporting_currency="USD",
    )

    assert adjusted == 0.016
    assert citation_ids == ("basel_mar21_43",)


def test_us_npr_girr_delta_reference_data_uses_profile_owned_citations() -> None:
    citations = citations_for_profile(SbmRegulatoryProfile.US_NPR_2_0)
    bucket = girr_bucket_definition(SbmRegulatoryProfile.US_NPR_2_0, "2")
    adjusted, weight_citations = girr_delta_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        tenor="5y",
        currency="USD",
        reporting_currency="USD",
    )
    intra_correlation, intra_citations = girr_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        tenor1="1y",
        tenor2="5y",
        same_curve=True,
    )
    inter_correlation, inter_citations = girr_inter_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket1="1",
        bucket2="2",
    )

    assert "us_npr_91_fr_14952_va7a_girr_delta_weights" in citations
    assert bucket.currency == "USD"
    assert bucket.citation_id == "us_npr_91_fr_14952_va7a_girr_buckets"
    assert adjusted == pytest.approx(0.011 / math.sqrt(2.0))
    assert weight_citations == (
        "us_npr_91_fr_14952_va7a_girr_delta_weights",
        "us_npr_91_fr_14952_va7a_girr_sqrt2",
    )
    assert intra_correlation == pytest.approx(math.exp(-0.03 * 4.0))
    assert intra_citations == ("us_npr_91_fr_14952_va7a_girr_intra",)
    assert inter_correlation == GIRR_INTER_BUCKET_CORRELATION
    assert inter_citations == ("us_npr_91_fr_14952_va7a_girr_inter",)


def test_pra_uk_crr_girr_delta_reference_data_uses_profile_owned_citations() -> None:
    citations = citations_for_profile(SbmRegulatoryProfile.PRA_UK_CRR)
    bucket = girr_bucket_definition(SbmRegulatoryProfile.PRA_UK_CRR, "2")
    adjusted, weight_citations = girr_delta_risk_weight(
        SbmRegulatoryProfile.PRA_UK_CRR,
        tenor="5y",
        currency="USD",
        reporting_currency="USD",
    )
    intra_correlation, intra_citations = girr_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.PRA_UK_CRR,
        tenor1="1y",
        tenor2="5y",
        same_curve=True,
    )
    inter_correlation, inter_citations = girr_inter_bucket_correlation(
        SbmRegulatoryProfile.PRA_UK_CRR,
        bucket1="1",
        bucket2="2",
    )
    scenario = correlation_scenario_definition(
        SbmRegulatoryProfile.PRA_UK_CRR,
        SbmScenarioLabel.HIGH,
    )

    assert "pra_uk_crr_325ae_girr_delta_weights" in citations
    assert "pra_uk_crr_325h_correlation_scenarios" in citations
    assert bucket.currency == "USD"
    assert bucket.citation_id == "pra_uk_crr_325ae_girr_buckets"
    assert adjusted == pytest.approx(0.011 / math.sqrt(2.0))
    assert weight_citations == (
        "pra_uk_crr_325ae_girr_delta_weights",
        "pra_uk_crr_325ae_girr_sqrt2",
    )
    assert intra_correlation == pytest.approx(math.exp(-0.03 * 4.0))
    assert intra_citations == ("pra_uk_crr_325af_girr_intra",)
    assert inter_correlation == GIRR_INTER_BUCKET_CORRELATION
    assert inter_citations == ("pra_uk_crr_325ag_girr_inter",)
    assert scenario.citation_id == "pra_uk_crr_325h_correlation_scenarios"


def test_girr_delta_intra_bucket_correlation_uses_exponential_tenor_formula() -> None:
    correlation, citation_ids = girr_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        tenor1="1y",
        tenor2="5y",
        same_curve=True,
    )

    expected = math.exp(-0.03 * abs(1.0 - 5.0) / 1.0)
    assert correlation == pytest.approx(expected)
    assert citation_ids == ("basel_mar21_45_49",)


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


def test_non_girr_vega_liquidity_horizons_use_mar21_table_13() -> None:
    profile = SbmRegulatoryProfile.BASEL_MAR21

    assert vega_liquidity_horizon_days(profile, risk_class=SbmRiskClass.FX) == 40
    assert vega_liquidity_horizon_days(profile, risk_class=SbmRiskClass.COMMODITY) == 120
    assert vega_liquidity_horizon_days(profile, risk_class=SbmRiskClass.CSR_NONSEC) == 120
    assert vega_liquidity_horizon_days(profile, risk_class=SbmRiskClass.EQUITY, bucket_id="5") == 20
    assert vega_liquidity_horizon_days(profile, risk_class=SbmRiskClass.EQUITY, bucket_id="9") == 60


def test_vega_option_tenor_correlation_matches_mar21_exponential_term() -> None:
    correlation, citation_ids = vega_option_tenor_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        option_tenor1="1y",
        option_tenor2="5y",
    )

    assert correlation == pytest.approx(math.exp(-0.01 * abs(1.0 - 5.0) / 1.0))
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
    assert citation_ids == ("basel_mar21_50",)


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
    assert citation_ids == ("basel_mar21_6_correlation_scenarios",)


def test_apply_correlation_scenario_definition_rejects_non_finite_base() -> None:
    definition = correlation_scenario_definition(
        SbmRegulatoryProfile.BASEL_MAR21,
        SbmScenarioLabel.MEDIUM,
    )
    with pytest.raises(SbmInputError, match="base_correlation must be finite"):
        apply_correlation_scenario_definition(float("nan"), definition)


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


def test_us_npr_fx_delta_reference_data_uses_profile_owned_citations() -> None:
    reduced, citations = fx_delta_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        currency="EUR",
        reporting_currency="USD",
    )
    intra, intra_citations = fx_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket1="EUR",
        bucket2="EUR",
    )
    inter, inter_citations = fx_inter_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket1="EUR",
        bucket2="GBP",
    )
    bucket = fx_bucket_definition(SbmRegulatoryProfile.US_NPR_2_0, "EUR")

    assert reduced == pytest.approx(FX_DELTA_RISK_WEIGHT / math.sqrt(2.0))
    assert citations == (
        "us_npr_91_fr_14952_va7a_fx_delta_weights",
        "us_npr_91_fr_14952_va7a_fx_delta_sqrt2",
    )
    assert intra == pytest.approx(1.0)
    assert intra_citations == ("us_npr_91_fr_14952_va7a_fx_delta_intra",)
    assert inter == pytest.approx(FX_INTER_BUCKET_CORRELATION)
    assert inter_citations == ("us_npr_91_fr_14952_va7a_fx_delta_inter",)
    assert bucket.citation_id == "us_npr_91_fr_14952_va7a_fx_reporting_currency"


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
    "risk_class",
    [
        SbmRiskClass.FX,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.CSR_SEC_CTP,
    ],
)
def test_non_girr_vega_paths_are_supported(risk_class: SbmRiskClass) -> None:
    ensure_profile_supports_risk_class_measure(
        SbmRegulatoryProfile.BASEL_MAR21,
        risk_class,
        SbmRiskMeasure.VEGA,
    )


def test_curvature_reference_weights_include_paragraph_citations() -> None:
    girr_weight, girr_citations = curvature_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        risk_class=SbmRiskClass.GIRR,
    )
    equity_weight, equity_citations = curvature_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        risk_class=SbmRiskClass.EQUITY,
        bucket_id="1",
        risk_factor="SPOT",
    )

    assert girr_weight == pytest.approx(0.017)
    assert "basel_mar21_99" in girr_citations
    assert equity_weight == pytest.approx(0.55)
    assert "basel_mar21_98" in equity_citations


@pytest.mark.parametrize(
    "profile",
    [
        SbmRegulatoryProfile.EU_CRR3,
    ],
)
def test_unsupported_profiles_fail_reference_data_lookup(profile: SbmRegulatoryProfile) -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        citations_for_profile(profile)
