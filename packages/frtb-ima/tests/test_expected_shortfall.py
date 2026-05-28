"""Tests for expected_shortfall module."""

import pytest

from frtb_ima.expected_shortfall import (
    ESEstimator,
    expected_shortfall,
    expected_shortfall_from_sorted_losses_desc,
)

DISCRETE = ESEstimator.DISCRETE_CEIL
WEIGHTED = ESEstimator.WEIGHTED_INTERPOLATED


def test_known_vector() -> None:
    # 10 losses: [1..10]. At alpha=0.90, tail is top 10% = [10].
    losses = [float(i) for i in range(1, 11)]
    es = expected_shortfall(losses, alpha=0.90, estimator=DISCRETE)
    assert es == pytest.approx(10.0)


def test_known_vector_alpha_975() -> None:
    # 100 scenarios, losses 1..100.
    # At alpha=0.975, tail = top 2.5% = ceil(100*0.025) = 3 scenarios = [100, 99, 98].
    losses = [float(i) for i in range(1, 101)]
    es = expected_shortfall(losses, alpha=0.975, estimator=DISCRETE)
    assert es == pytest.approx((100 + 99 + 98) / 3, rel=1e-6)


def test_weighted_interpolated_known_vector_alpha_975() -> None:
    losses = [float(i) for i in range(1, 101)]
    es = expected_shortfall(losses, alpha=0.975, estimator=WEIGHTED)
    assert es == pytest.approx((100 + 99 + 0.5 * 98) / 2.5, rel=1e-6)


def test_sorted_loss_helper_weighted_interpolated_known_vector() -> None:
    sorted_losses_desc = [100.0, 99.0, 98.0, 97.0]
    es = expected_shortfall_from_sorted_losses_desc(
        sorted_losses_desc,
        alpha=0.375,
        estimator=WEIGHTED,
    )
    assert es == pytest.approx((100 + 99 + 0.5 * 98) / 2.5, rel=1e-6)


def test_sorted_loss_helper_rejects_alpha_zero() -> None:
    with pytest.raises(ValueError, match="alpha"):
        expected_shortfall_from_sorted_losses_desc([2.0, 1.0], alpha=0.0, estimator=WEIGHTED)


def test_sorted_loss_helper_rejects_alpha_one() -> None:
    with pytest.raises(ValueError, match="alpha"):
        expected_shortfall_from_sorted_losses_desc([2.0, 1.0], alpha=1.0, estimator=WEIGHTED)


def test_sorted_loss_helper_rejects_unsorted_multidimensional_input() -> None:
    import numpy as np

    with pytest.raises(ValueError, match="one-dimensional"):
        expected_shortfall_from_sorted_losses_desc(
            np.array([[2.0, 1.0]]),
            alpha=0.5,
            estimator=WEIGHTED,
        )


def test_estimators_match_when_tail_mass_is_integer() -> None:
    losses = [float(i) for i in range(1, 11)]
    discrete = expected_shortfall(losses, alpha=0.50, estimator=DISCRETE)
    weighted = expected_shortfall(losses, alpha=0.50, estimator=WEIGHTED)
    assert weighted == pytest.approx(discrete)


def test_negative_pnl_converted_to_losses() -> None:
    # Negative P&L values = gains in loss convention.
    # ES should average the largest positive losses.
    losses = [-5.0, -3.0, 1.0, 2.0, 10.0]
    es = expected_shortfall(losses, alpha=0.80, estimator=DISCRETE)
    # top 20% of 5 = ceil(5*0.2) = 1 scenario = [10.0]
    assert es == pytest.approx(10.0)


def test_single_element() -> None:
    es = expected_shortfall([42.0], alpha=0.975, estimator=WEIGHTED)
    assert es == pytest.approx(42.0)


def test_all_gains_returns_negative_es() -> None:
    # All negative losses (all gains). ES of the worst gain.
    losses = [-10.0, -8.0, -5.0, -1.0]
    es = expected_shortfall(losses, alpha=0.975, estimator=DISCRETE)
    # tail count = ceil(4 * 0.025) = 1, worst = -1.0 (least negative)
    assert es == pytest.approx(-1.0)


def test_empty_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        expected_shortfall([], alpha=0.975, estimator=WEIGHTED)


def test_numpy_array_input() -> None:
    import numpy as np

    es = expected_shortfall(np.array([1.0, 2.0, 3.0]), alpha=0.80, estimator=WEIGHTED)
    assert es == pytest.approx(3.0)


def test_non_finite_losses_raise() -> None:
    with pytest.raises(ValueError, match="finite"):
        expected_shortfall([1.0, float("nan")], alpha=0.975, estimator=WEIGHTED)


def test_multidimensional_losses_raise() -> None:
    import numpy as np

    with pytest.raises(ValueError, match="one-dimensional"):
        expected_shortfall(np.array([[1.0, 2.0]]), alpha=0.975, estimator=WEIGHTED)


def test_invalid_alpha_zero() -> None:
    with pytest.raises(ValueError, match="alpha"):
        expected_shortfall([1.0, 2.0], alpha=0.0, estimator=WEIGHTED)


def test_invalid_alpha_one() -> None:
    with pytest.raises(ValueError, match="alpha"):
        expected_shortfall([1.0, 2.0], alpha=1.0, estimator=WEIGHTED)


def test_invalid_alpha_negative() -> None:
    with pytest.raises(ValueError, match="alpha"):
        expected_shortfall([1.0, 2.0], alpha=-0.1, estimator=WEIGHTED)
