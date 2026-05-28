"""Independent numerical reference vectors for core IMA calculations."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats

from frtb_ima.capital import supervisory_multiplier
from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.expected_shortfall import ESEstimator, expected_shortfall
from frtb_ima.imcc import imcc_breakdown
from frtb_ima.liquidity_horizon import lha_es_from_vectors
from frtb_ima.nmrf import aggregate_ses_type_a, aggregate_ses_type_b
from frtb_ima.pla import ks_statistic, spearman_correlation
from frtb_ima.regimes import (
    DEFAULT_SUPERVISORY_MULTIPLIER_SCHEDULE,
    get_policy,
)

# Expected shortfall


def test_es_uniform_distribution_matches_closed_form_tail_mean() -> None:
    """Reference source: analytic - exact ES for continuous Uniform(0, 1)."""
    alpha = 0.95
    losses = (np.arange(100, dtype=float) + 0.5) / 100.0
    reference = (1.0 + alpha) / 2.0

    actual = expected_shortfall(
        losses,
        alpha=alpha,
        estimator=ESEstimator.WEIGHTED_INTERPOLATED,
    )

    assert actual == pytest.approx(reference, abs=1e-15)


def test_es_truncated_normal_matches_analytic_tail_integral() -> None:
    """Reference source: analytic truncated-normal tail integral from phi/Phi."""
    alpha = 0.975
    lower = -1.0
    upper = 2.0
    lower_cdf = stats.norm.cdf(lower)
    upper_cdf = stats.norm.cdf(upper)
    quantile = stats.norm.ppf(lower_cdf + alpha * (upper_cdf - lower_cdf))
    reference = (stats.norm.pdf(quantile) - stats.norm.pdf(upper)) / (
        upper_cdf - stats.norm.cdf(quantile)
    )

    probabilities = (np.arange(20_000, dtype=float) + 0.5) / 20_000
    losses = stats.norm.ppf(lower_cdf + probabilities * (upper_cdf - lower_cdf))
    actual = expected_shortfall(
        losses,
        alpha=alpha,
        estimator=ESEstimator.WEIGHTED_INTERPOLATED,
    )

    assert actual == pytest.approx(reference, abs=2e-5)


# LHA ES


def test_lha_es_matches_closed_form_weighted_square_root() -> None:
    """Reference source: analytic - Basel MAR33.4 weighted square-root formula."""
    vectors = {
        LiquidityHorizon.LH10: [3.0, 3.0, 3.0],
        LiquidityHorizon.LH20: [2.0, 2.0, 2.0],
        LiquidityHorizon.LH60: [1.0, 1.0, 1.0],
        LiquidityHorizon.LH120: [0.5, 0.5, 0.5],
    }
    reference = math.sqrt(3.0**2 + 2.0**2 + 2.0 * 1.0**2 + 6.0 * 0.5**2)

    actual = lha_es_from_vectors(
        vectors,
        alpha=0.975,
        estimator=ESEstimator.WEIGHTED_INTERPOLATED,
    )

    assert actual == pytest.approx(reference, abs=1e-15)


# IMCC


def test_imcc_two_risk_class_case_matches_analytic_unconstrained_and_constrained_forms() -> None:
    """Reference source: analytic - Basel MAR33 constrained/unconstrained IMCC blend."""
    all_risk_class_vectors = {
        LiquidityHorizon.LH10: [7.0, 7.0, 7.0],
        LiquidityHorizon.LH20: [3.0, 3.0, 3.0],
    }
    per_risk_class_vectors = {
        RiskClass.GIRR: {
            LiquidityHorizon.LH10: [3.0, 3.0, 3.0],
            LiquidityHorizon.LH20: [1.0, 1.0, 1.0],
        },
        RiskClass.CSR: {
            LiquidityHorizon.LH10: [4.0, 4.0, 4.0],
            LiquidityHorizon.LH20: [2.0, 2.0, 2.0],
        },
    }
    unconstrained_reference = math.sqrt(7.0**2 + 3.0**2)
    constrained_reference = math.sqrt(3.0**2 + 1.0**2) + math.sqrt(4.0**2 + 2.0**2)
    imcc_reference = 0.5 * unconstrained_reference + 0.5 * constrained_reference

    result = imcc_breakdown(
        all_risk_class_vectors,
        per_risk_class_vectors,
        alpha=0.975,
        estimator=ESEstimator.WEIGHTED_INTERPOLATED,
        w=0.5,
    )

    assert result.unconstrained_lha_es == pytest.approx(unconstrained_reference, abs=1e-15)
    assert result.constrained_lha_es == pytest.approx(constrained_reference, abs=1e-15)
    assert result.imcc == pytest.approx(imcc_reference, abs=1e-15)


# SES Type A aggregation


def test_ses_type_a_aggregation_matches_root_sum_of_squares_reference() -> None:
    """Reference source: analytic - U.S. NPR 2.0 Type A zero-correlation form."""
    values = [3.0, 4.0]

    assert aggregate_ses_type_a(values) == pytest.approx(5.0, abs=1e-15)


# SES Type B aggregation


def test_ses_type_b_aggregation_matches_partial_correlation_reference() -> None:
    """Reference source: analytic - U.S. NPR 2.0 Type B rho=0.36 aggregation."""
    values = [10.0, 20.0]
    rho = get_policy().type_b_ses_rho
    reference = math.sqrt(rho * (10.0 + 20.0) ** 2 + (1.0 - rho) * (10.0**2 + 20.0**2))

    assert rho == pytest.approx(0.36)
    assert aggregate_ses_type_b(values, rho=rho) == pytest.approx(reference, abs=1e-15)


# PLA KS


def test_pla_ks_statistic_matches_scipy_peer_reference() -> None:
    """Reference source: SciPy stats.ks_2samp peer implementation."""
    hpl = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    rtpl = np.array([-1.5, -0.5, 0.5, 1.5, 2.5])
    reference = stats.ks_2samp(hpl, rtpl, method="asymp").statistic

    assert ks_statistic(hpl, rtpl) == pytest.approx(reference, abs=1e-15)


# PLA Spearman


def test_pla_spearman_correlation_matches_scipy_peer_reference() -> None:
    """Reference source: SciPy stats.spearmanr peer implementation."""
    hpl = np.array([10.0, 20.0, 20.0, 40.0, 50.0, 60.0])
    rtpl = np.array([11.0, 19.0, 21.0, 39.0, 55.0, 58.0])
    reference = stats.spearmanr(hpl, rtpl).statistic

    assert spearman_correlation(hpl, rtpl) == pytest.approx(reference, abs=1e-15)


# Supervisory multiplier mapping


def test_supervisory_multiplier_mapping_matches_basel_mar99_table_2_reference() -> None:
    """Reference source: Basel MAR99 Table 2 backtesting multiplier schedule."""
    expected = {
        0: 1.50,
        4: 1.50,
        5: 1.70,
        6: 1.76,
        7: 1.83,
        8: 1.88,
        9: 1.92,
        10: 2.00,
        15: 2.00,
    }

    for exception_count, reference in expected.items():
        assert supervisory_multiplier(
            exception_count,
            schedule=DEFAULT_SUPERVISORY_MULTIPLIER_SCHEDULE,
            red_zone_multiplier=2.00,
        ) == pytest.approx(reference, abs=1e-15)
