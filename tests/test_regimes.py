"""Tests for regulatory regime policy configuration."""

from dataclasses import FrozenInstanceError
from datetime import date, timedelta
from pathlib import Path

import pytest

from frtb_ima.backtesting import backtest, backtest_for_policy
from frtb_ima.capital import supervisory_multiplier, supervisory_multiplier_for_policy
from frtb_ima.data_models import (
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
    RiskFactor,
)
from frtb_ima.expected_shortfall import expected_shortfall
from frtb_ima.imcc import imcc, imcc_for_policy
from frtb_ima.liquidity_horizon import lha_es_from_vectors
from frtb_ima.nmrf import aggregate_ses, aggregate_ses_for_policy
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


def _flat_vec(value: float, n: int = 100) -> list[float]:
    return [value] * n


def _observations(name: str, n: int) -> list[RealPriceObservation]:
    return [
        RealPriceObservation(name, AS_OF - timedelta(days=i * 14))
        for i in range(n)
    ]


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


def test_fed_policy_reproduces_current_default_calculation_outputs() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)

    losses = [float(i) for i in range(1, 101)]
    assert expected_shortfall(losses) == pytest.approx(
        expected_shortfall(losses, alpha=policy.es_confidence_level)
    )

    all_class = {LiquidityHorizon.LH10: _flat_vec(200.0)}
    per_class = {
        RiskClass.GIRR: {LiquidityHorizon.LH10: _flat_vec(100.0)},
        RiskClass.EQUITY: {LiquidityHorizon.LH10: _flat_vec(100.0)},
    }
    assert lha_es_from_vectors(all_class) == pytest.approx(
        lha_es_from_vectors(
            all_class,
            alpha=policy.es_confidence_level,
            lha_weights=policy.lha_weights,
        )
    )
    assert imcc(all_class, per_class) == pytest.approx(
        imcc_for_policy(all_class, per_class, policy)
    )
    assert aggregate_ses([10.0], [5.0, 5.0]) == pytest.approx(
        aggregate_ses_for_policy([10.0], [5.0, 5.0], policy)
    )
    pla_vec = [float(i) for i in range(250)]
    assert pla_assessment(pla_vec, pla_vec) == pla_assessment_for_policy(
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
    assert supervisory_multiplier(6) == pytest.approx(
        supervisory_multiplier_for_policy(6, policy)
    )


def test_scalar_functions_remain_backward_compatible() -> None:
    assert expected_shortfall([1.0, 2.0, 3.0], alpha=0.80) == pytest.approx(3.0)
    assert aggregate_ses([1.0], [2.0], type_b_rho=1.0) == pytest.approx(5.0**0.5)
    assert supervisory_multiplier(10) == pytest.approx(2.0)


def test_ecb_profile_requires_unsupported_spearman_pla() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    assert policy.pla_metrics_required == PLAMetricsRequired.KS_AND_SPEARMAN

    with pytest.raises(UnsupportedRegulatoryFeature, match="spearman_pla"):
        pla_assessment_for_policy([1.0, 2.0], [1.0, 2.0], policy)


def test_type_a_type_b_taxonomy_is_fed_only_until_explicitly_supported() -> None:
    fed = get_policy(RegulatoryRegime.FED_NPR_2_0)
    ecb = get_policy(RegulatoryRegime.ECB_CRR3)
    rf = RiskFactor("RF_A", RiskClass.GIRR, LiquidityHorizon.LH10)
    obs = _observations("RF_A", 10)

    assert fed.nmrf_taxonomy_mode == NMRFTaxonomyMode.TYPE_A_TYPE_B
    assert ecb.nmrf_taxonomy_mode == NMRFTaxonomyMode.BASEL_EU_NMRF
    assert classify_risk_factor_for_policy(
        rf,
        obs,
        qualitative_pass=True,
        as_of_date=AS_OF,
        policy=fed,
    ) == ModellabilityStatus.TYPE_A_NMRF
    assert classify_risk_factor(
        rf,
        obs,
        qualitative_pass=True,
        as_of_date=AS_OF,
    ) == ModellabilityStatus.TYPE_A_NMRF

    with pytest.raises(UnsupportedRegulatoryFeature, match="type_a_type_b"):
        classify_risk_factor_for_policy(
            rf,
            obs,
            qualitative_pass=True,
            as_of_date=AS_OF,
            policy=ecb,
        )
    with pytest.raises(UnsupportedRegulatoryFeature, match="type_a_type_b"):
        aggregate_ses_for_policy([1.0], [2.0], ecb)


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
    assert expected_shortfall([10.0], alpha=context.policy.es_confidence_level) == (
        expected_shortfall([10.0])
    )


def test_traceability_docs_name_every_regime() -> None:
    doc = Path(__file__).resolve().parents[1] / "docs" / "REGULATORY_TRACEABILITY.md"
    text = doc.read_text()
    for regime in RegulatoryRegime:
        assert regime.value in text
