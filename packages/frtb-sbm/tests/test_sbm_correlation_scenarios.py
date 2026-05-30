"""Tests for inter-bucket aggregation and correlation scenarios (SBM-REQ-006)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from frtb_sbm import (
    BucketCapital,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    WeightedSensitivity,
)
from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    adjust_correlation_for_scenario,
    adjust_correlation_matrix_for_scenario,
    aggregate_inter_bucket,
    aggregate_intra_bucket,
    aggregate_risk_class_with_scenarios,
    select_max_correlation_scenario,
)
from frtb_sbm.validation import SbmInputError


def _weighted(*, sensitivity_id: str, scaled_amount: float, bucket: str) -> WeightedSensitivity:
    return WeightedSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        raw_amount=scaled_amount,
        risk_weight=1.0,
        scaled_amount=scaled_amount,
        citation_ids=("basel_mar21_girr",),
    )


def _bucket(
    *,
    bucket_id: str,
    kb: float,
    sb: float,
    weighted: tuple[WeightedSensitivity, ...],
) -> BucketCapital:
    return BucketCapital(
        bucket_id=bucket_id,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        kb=kb,
        sb=sb,
        weighted_sensitivities=weighted,
        citation_ids=("basel_mar21_girr",),
    )


def test_correlation_scenario_adjustments_follow_mar21_6() -> None:
    """MAR21.6: medium, high (x1.25 capped), and low (max(2rho-1, 0.75rho))."""
    assert adjust_correlation_for_scenario(0.4, SbmScenarioLabel.MEDIUM) == pytest.approx(0.4)
    assert adjust_correlation_for_scenario(0.4, SbmScenarioLabel.HIGH) == pytest.approx(0.5)
    assert adjust_correlation_for_scenario(0.4, SbmScenarioLabel.LOW) == pytest.approx(0.3)
    assert adjust_correlation_for_scenario(0.9, SbmScenarioLabel.HIGH) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("scenario", "base"),
    [
        (SbmScenarioLabel.LOW, 0.30),
        (SbmScenarioLabel.MEDIUM, 0.40),
        (SbmScenarioLabel.HIGH, 0.90),
    ],
)
def test_adjust_correlation_for_scenario_matches_profile_lookup(
    scenario: SbmScenarioLabel,
    base: float,
) -> None:
    from frtb_sbm import SbmRegulatoryProfile, apply_correlation_scenario

    adjusted_lookup, _ = apply_correlation_scenario(
        SbmRegulatoryProfile.BASEL_MAR21,
        base_correlation=base,
        scenario=scenario,
    )
    assert adjust_correlation_for_scenario(base, scenario) == pytest.approx(adjusted_lookup)


def test_inter_bucket_aggregation_uses_kb_and_sb_terms() -> None:
    """MAR21.4(5): K^2 = sum Kb^2 + sum gamma_bc Sb Sc."""
    usd = _bucket(
        bucket_id="USD",
        kb=10.0,
        sb=10.0,
        weighted=(_weighted(sensitivity_id="usd", scaled_amount=10.0, bucket="USD"),),
    )
    eur = _bucket(
        bucket_id="EUR",
        kb=8.0,
        sb=6.0,
        weighted=(_weighted(sensitivity_id="eur", scaled_amount=6.0, bucket="EUR"),),
    )
    gamma = 0.5
    expected = 10.0**2 + 8.0**2 + 2.0 * gamma * 10.0 * 6.0

    result = aggregate_inter_bucket(
        (usd, eur),
        {("USD", "EUR"): gamma},
        scenario=SbmScenarioLabel.MEDIUM,
    )

    assert result.capital_variance_sum == pytest.approx(expected)
    assert result.capital == pytest.approx(math.sqrt(expected))
    assert result.alternative_sb_used is False
    assert result.inter_bucket_correlations == (("USD", "EUR", gamma),)


def test_inter_bucket_applies_alternative_sb_when_variance_negative() -> None:
    """MAR21.4(5)(b): clamp Sb to [-Kb, Kb] before recomputing capital."""
    long_bucket = _bucket(
        bucket_id="USD",
        kb=10.0,
        sb=10.0,
        weighted=(_weighted(sensitivity_id="usd", scaled_amount=10.0, bucket="USD"),),
    )
    short_bucket = _bucket(
        bucket_id="EUR",
        kb=8.0,
        sb=-20.0,
        weighted=(_weighted(sensitivity_id="eur", scaled_amount=-20.0, bucket="EUR"),),
    )

    result = aggregate_inter_bucket(
        (long_bucket, short_bucket),
        {("USD", "EUR"): 1.0},
        scenario=SbmScenarioLabel.MEDIUM,
    )

    assert result.alternative_sb_used is True
    assert result.capital_variance_sum >= 0.0
    assert result.capital == pytest.approx(math.sqrt(result.capital_variance_sum))


def test_high_scenario_increases_inter_bucket_capital_vs_medium() -> None:
    usd = _bucket(
        bucket_id="USD",
        kb=12.0,
        sb=12.0,
        weighted=(_weighted(sensitivity_id="usd", scaled_amount=12.0, bucket="USD"),),
    )
    eur = _bucket(
        bucket_id="EUR",
        kb=9.0,
        sb=9.0,
        weighted=(_weighted(sensitivity_id="eur", scaled_amount=9.0, bucket="EUR"),),
    )
    base_gamma = 0.4

    medium = aggregate_inter_bucket(
        (usd, eur),
        {("USD", "EUR"): base_gamma},
        scenario=SbmScenarioLabel.MEDIUM,
    )
    high = aggregate_inter_bucket(
        (usd, eur),
        {("USD", "EUR"): base_gamma},
        scenario=SbmScenarioLabel.HIGH,
    )

    assert high.capital > medium.capital
    assert high.inter_bucket_correlations[0][2] == pytest.approx(0.5)


def test_select_max_correlation_scenario_chooses_largest_total() -> None:
    """MAR21.7(2): GIRR delta uses the maximum scenario capital."""
    totals = {
        SbmScenarioLabel.LOW: 100.0,
        SbmScenarioLabel.MEDIUM: 120.0,
        SbmScenarioLabel.HIGH: 115.0,
    }

    selection = select_max_correlation_scenario(
        totals,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )

    assert selection.selected_scenario is SbmScenarioLabel.MEDIUM
    assert selection.selected_capital == pytest.approx(120.0)
    assert selection.branch_metadata.branch_type.value == "SCENARIO_SELECTION"
    assert selection.branch_metadata.branch_id == "girr_delta_scenario_selection"


def test_intra_bucket_kb_recomputed_under_correlation_scenarios() -> None:
    """MAR21.6: intra-bucket rho adjustments change Kb for multi-sensitivity buckets."""
    usd_ws = (
        _weighted(sensitivity_id="usd-1y", scaled_amount=100.0, bucket="USD"),
        _weighted(sensitivity_id="usd-5y", scaled_amount=50.0, bucket="USD"),
    )
    usd_matrix = np.array([[1.0, 0.8869], [0.8869, 1.0]], dtype=np.float64)
    medium = aggregate_intra_bucket(
        "USD",
        usd_ws,
        adjust_correlation_matrix_for_scenario(usd_matrix, SbmScenarioLabel.MEDIUM),
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )
    high = aggregate_intra_bucket(
        "USD",
        usd_ws,
        adjust_correlation_matrix_for_scenario(usd_matrix, SbmScenarioLabel.HIGH),
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )

    assert high.bucket_capital.kb != pytest.approx(medium.bucket_capital.kb)


def test_end_to_end_girr_delta_slice_selects_max_scenario() -> None:
    usd_ws = (
        _weighted(sensitivity_id="usd-1y", scaled_amount=100.0, bucket="USD"),
        _weighted(sensitivity_id="usd-5y", scaled_amount=50.0, bucket="USD"),
    )
    usd_matrix = np.array([[1.0, 0.8869], [0.8869, 1.0]], dtype=np.float64)
    usd_spec = IntraBucketScenarioSpec(
        bucket_id="USD",
        weighted_sensitivities=usd_ws,
        base_correlation_matrix=usd_matrix,
    )

    eur_ws = (_weighted(sensitivity_id="eur-1y", scaled_amount=80.0, bucket="EUR"),)
    eur_spec = IntraBucketScenarioSpec(
        bucket_id="EUR",
        weighted_sensitivities=eur_ws,
        base_correlation_matrix=np.array([[1.0]], dtype=np.float64),
    )

    risk_class = aggregate_risk_class_with_scenarios(
        (usd_spec, eur_spec),
        {("EUR", "USD"): 0.5},
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )

    assert risk_class.selected_scenario is not None
    assert risk_class.scenario_totals is not None
    assert len(risk_class.scenario_totals) == 3
    assert len(risk_class.scenario_details) == 3
    assert risk_class.scenario_selection is not None
    assert risk_class.scenario_selection.branch_id == "girr_delta_scenario_selection"
    assert risk_class.selected_capital == pytest.approx(max(risk_class.scenario_totals.values()))
    assert risk_class.selected_scenario == max(
        risk_class.scenario_totals,
        key=lambda label: risk_class.scenario_totals[label],
    )


def test_select_max_correlation_scenario_rejects_empty_mapping() -> None:
    with pytest.raises(SbmInputError, match="scenario_totals must not be empty"):
        select_max_correlation_scenario({}, risk_class=SbmRiskClass.GIRR)
