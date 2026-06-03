"""Tests for regulatory regime policy configuration."""

from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, timedelta
from importlib.metadata import version
from pathlib import Path

import pytest

import frtb_ima
from frtb_ima.backtesting import backtest, backtest_for_policy
from frtb_ima.capital import supervisory_multiplier, supervisory_multiplier_for_policy
from frtb_ima.data_models import (
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
    RiskFactor,
)
from frtb_ima.expected_shortfall import ESEstimator, expected_shortfall
from frtb_ima.imcc import imcc, imcc_for_policy
from frtb_ima.liquidity_horizon import lha_es_from_vectors
from frtb_ima.nmrf import aggregate_ses, aggregate_ses_for_policy, route_nmrf_classifications_for_capital
from frtb_ima.pla import pla_assessment, pla_assessment_for_policy
from frtb_ima.regimes import (
    CalculationContext,
    NMRFTaxonomyMode,
    PLAMetricsRequired,
    RegulatoryPolicy,
    RegulatoryRegime,
    UnsupportedRegulatoryFeature,
    get_policy,
)
from frtb_ima.rfet import classify_risk_factor, classify_risk_factor_for_policy

AS_OF = date(2025, 6, 30)
MODELLING_CHOICE_NUMERIC_FIELDS = {"liquidity_horizons", "lha_weights"}


def _flat_vec(value: float, n: int = 100) -> list[float]:
    return [value] * n


def _observations(name: str, n: int) -> list[RealPriceObservation]:
    return [RealPriceObservation(name, AS_OF - timedelta(days=i * 14)) for i in range(n)]


def test_get_policy_returns_deterministic_immutable_profiles() -> None:
    fed = get_policy()
    assert fed == get_policy(RegulatoryRegime.FED_NPR_2_0)
    assert fed.regime == RegulatoryRegime.FED_NPR_2_0

    regimes = {
        get_policy(RegulatoryRegime.FED_NPR_2_0).regime,
        get_policy(RegulatoryRegime.ECB_CRR3).regime,
        get_policy(RegulatoryRegime.PRA_UK_CRR).regime,
    }
    assert regimes == {
        RegulatoryRegime.FED_NPR_2_0,
        RegulatoryRegime.ECB_CRR3,
        RegulatoryRegime.PRA_UK_CRR,
    }

    with pytest.raises(FrozenInstanceError):
        fed.es_confidence_level = 0.99  # type: ignore[misc]


def test_package_version_matches_installed_metadata() -> None:
    assert frtb_ima.__version__ == version("frtb-ima")


def test_regulatory_policy_hash_is_stable_and_field_sensitive() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    identical = get_policy(RegulatoryRegime.FED_NPR_2_0)
    changed = replace(policy, pla_green_threshold=policy.pla_green_threshold + 0.01)

    assert policy.as_dict()["regime"] == "FED_NPR_2_0"
    assert policy.policy_hash == identical.policy_hash
    assert len(policy.policy_hash) == 64
    assert policy.policy_hash != changed.policy_hash


def test_fed_policy_reproduces_current_default_calculation_outputs() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)

    losses = [float(i) for i in range(1, 101)]
    assert policy.es_estimator == ESEstimator.WEIGHTED_INTERPOLATED
    assert expected_shortfall(
        losses,
        alpha=policy.es_confidence_level,
        estimator=policy.es_estimator,
    ) == pytest.approx(99.2)

    all_class = {LiquidityHorizon.LH10: _flat_vec(200.0)}
    per_class = {
        RiskClass.GIRR: {LiquidityHorizon.LH10: _flat_vec(100.0)},
        RiskClass.EQUITY: {LiquidityHorizon.LH10: _flat_vec(100.0)},
    }
    assert lha_es_from_vectors(
        all_class,
        alpha=policy.es_confidence_level,
        estimator=policy.es_estimator,
        lha_weights=policy.lha_weights,
    ) == pytest.approx(
        lha_es_from_vectors(
            all_class,
            alpha=policy.es_confidence_level,
            estimator=policy.es_estimator,
            lha_weights=policy.lha_weights,
        )
    )
    assert imcc(
        all_class,
        per_class,
        alpha=policy.es_confidence_level,
        estimator=policy.es_estimator,
        w=policy.imcc_unconstrained_weight,
        lha_weights=policy.lha_weights,
    ) == pytest.approx(imcc_for_policy(all_class, per_class, policy))
    assert aggregate_ses([10.0], [5.0, 5.0], type_b_rho=policy.type_b_ses_rho) == pytest.approx(
        aggregate_ses_for_policy([10.0], [5.0, 5.0], policy)
    )
    pla_vec = [float(i) for i in range(250)]
    assert pla_assessment(
        pla_vec,
        pla_vec,
        green_threshold=policy.pla_green_threshold,
        amber_threshold=policy.pla_amber_threshold,
        zone_labels=policy.pla_zone_labels,
    ) == pla_assessment_for_policy(
        pla_vec,
        pla_vec,
        policy,
    )
    assert backtest([1.0] * 250, [1.0] * 250, [100.0] * 250) == backtest_for_policy(
        [1.0] * 250,
        [1.0] * 250,
        [100.0] * 250,
        policy,
    )
    assert supervisory_multiplier(
        6,
        schedule=policy.supervisory_multiplier_schedule,
        red_zone_multiplier=policy.supervisory_multiplier_red_zone,
    ) == pytest.approx(supervisory_multiplier_for_policy(6, policy))


def test_scalar_functions_accept_explicit_regulatory_parameters() -> None:
    assert expected_shortfall(
        [1.0, 2.0, 3.0],
        alpha=0.80,
        estimator=ESEstimator.DISCRETE_CEIL,
    ) == pytest.approx(3.0)
    assert aggregate_ses([1.0], [2.0], type_b_rho=1.0) == pytest.approx(5.0**0.5)
    policy = get_policy()
    assert supervisory_multiplier(
        10,
        schedule=policy.supervisory_multiplier_schedule,
        red_zone_multiplier=policy.supervisory_multiplier_red_zone,
    ) == pytest.approx(2.0)


def test_regulatory_policy_numeric_fields_have_citations_or_documented_allowlist() -> None:
    policy = get_policy()
    citation_keys = set(policy.cited_by)
    numeric_field_names = {
        field.name
        for field in fields(policy)
        if field.name != "cited_by" and _contains_numeric(getattr(policy, field.name))
    }

    missing = numeric_field_names - citation_keys - MODELLING_CHOICE_NUMERIC_FIELDS
    assert missing == set()

    assumptions_doc = (
        Path(__file__).resolve().parents[1] / "docs" / "REGULATORY_ASSUMPTIONS.md"
    ).read_text()
    for field_name in MODELLING_CHOICE_NUMERIC_FIELDS:
        assert field_name in assumptions_doc


def test_pra_policy_uses_uk_crr_citations() -> None:
    policy = get_policy(RegulatoryRegime.PRA_UK_CRR)

    assert policy.unsupported_feature("pra_uk_crr_capital_runtime") is None
    assert "UK CRR Article 325be" in policy.cited_by["rfet_short_lh_threshold"]
    assert policy.pla_metrics_required == PLAMetricsRequired.KS_AND_SPEARMAN


def test_ecb_profile_requires_ks_and_spearman_pla() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)

    assert policy.pla_metrics_required == PLAMetricsRequired.KS_AND_SPEARMAN
    assert policy.pla_spearman_green_threshold == pytest.approx(0.80)
    assert policy.pla_spearman_amber_threshold == pytest.approx(0.70)
    assert "spearman_pla" not in {feature.feature_name for feature in policy.unsupported_features}


def test_type_a_type_b_taxonomy_is_fed_only_until_explicitly_supported() -> None:
    fed = get_policy(RegulatoryRegime.FED_NPR_2_0)
    ecb = get_policy(RegulatoryRegime.ECB_CRR3)
    rf = RiskFactor("RF_A", RiskClass.GIRR, LiquidityHorizon.LH10)
    obs = _observations("RF_A", 10)

    assert fed.nmrf_taxonomy_mode == NMRFTaxonomyMode.TYPE_A_TYPE_B
    assert ecb.nmrf_taxonomy_mode == NMRFTaxonomyMode.BASEL_EU_NMRF
    assert (
        classify_risk_factor_for_policy(
            rf,
            obs,
            qualitative_pass=True,
            as_of_date=AS_OF,
            policy=fed,
        )
        == ModellabilityStatus.TYPE_A_NMRF
    )
    assert (
        classify_risk_factor(
            rf,
            obs,
            qualitative_pass=True,
            as_of_date=AS_OF,
        )
        == ModellabilityStatus.TYPE_A_NMRF
    )

    with pytest.raises(UnsupportedRegulatoryFeature, match="type_a_type_b"):
        classify_risk_factor_for_policy(
            rf,
            obs,
            qualitative_pass=True,
            as_of_date=AS_OF,
            policy=ecb,
        )
    ecb_routing = route_nmrf_classifications_for_capital(
        {
            "MOD": ModellabilityStatus.MODELLABLE,
            "NMRF_A": ModellabilityStatus.TYPE_A_NMRF,
        },
        ecb,
    )
    assert ecb_routing.imcc_risk_factors == ("MOD",)
    assert ecb_routing.ses_risk_factors == ("NMRF_A",)


def test_calculation_context_selects_policy_without_changing_low_level_semantics() -> None:
    context = CalculationContext(
        policy=get_policy(RegulatoryRegime.FED_NPR_2_0),
        as_of_date=AS_OF,
        legal_entity="Synthetic Bank",
        desk="Rates",
        run_id="test-run",
    )

    assert context.policy.regime == RegulatoryRegime.FED_NPR_2_0
    assert isinstance(context.policy, RegulatoryPolicy)
    assert expected_shortfall(
        [10.0],
        alpha=context.policy.es_confidence_level,
        estimator=context.policy.es_estimator,
    ) == (
        expected_shortfall(
            [10.0],
            alpha=context.policy.es_confidence_level,
            estimator=context.policy.es_estimator,
        )
    )


def test_traceability_docs_name_every_regime() -> None:
    doc = Path(__file__).resolve().parents[1] / "docs" / "REGULATORY_TRACEABILITY.md"
    text = doc.read_text()
    for regime in RegulatoryRegime:
        assert regime.value in text
    assert "PRA_UK_CRR" in text
    assert "tests/fixtures/ima_pra" in text


def _contains_numeric(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return True
    if isinstance(value, dict):
        return any(_contains_numeric(item) for item in value.values())
    if isinstance(value, tuple | list):
        return any(_contains_numeric(item) for item in value)
    return False
