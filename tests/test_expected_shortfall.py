"""Tests for expected_shortfall module."""

import pytest

from frtb_ima.expected_shortfall import expected_shortfall


def test_known_vector() -> None:
    # 10 losses: [1..10]. At alpha=0.90, tail is top 10% = [10].
    losses = [float(i) for i in range(1, 11)]
    es = expected_shortfall(losses, alpha=0.90)
    assert es == pytest.approx(10.0)


def test_known_vector_alpha_975() -> None:
    # 100 scenarios, losses 1..100.
    # At alpha=0.975, tail = top 2.5% = ceil(100*0.025) = 3 scenarios = [100, 99, 98].
    losses = [float(i) for i in range(1, 101)]
    es = expected_shortfall(losses, alpha=0.975)
    assert es == pytest.approx((100 + 99 + 98) / 3, rel=1e-6)


def test_negative_pnl_converted_to_losses() -> None:
    # Negative P&L values = gains in loss convention.
    # ES should average the largest positive losses.
    losses = [-5.0, -3.0, 1.0, 2.0, 10.0]
    es = expected_shortfall(losses, alpha=0.80)
    # top 20% of 5 = ceil(5*0.2) = 1 scenario = [10.0]
    assert es == pytest.approx(10.0)


def test_single_element() -> None:
    es = expected_shortfall([42.0], alpha=0.975)
    assert es == pytest.approx(42.0)


def test_all_gains_returns_negative_es() -> None:
    # All negative losses (all gains). ES of the worst gain.
    losses = [-10.0, -8.0, -5.0, -1.0]
    es = expected_shortfall(losses, alpha=0.975)
    # tail count = ceil(4 * 0.025) = 1, worst = -1.0 (least negative)
    assert es == pytest.approx(-1.0)


def test_empty_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        expected_shortfall([], alpha=0.975)


def test_invalid_alpha_zero() -> None:
    with pytest.raises(ValueError, match="alpha"):
        expected_shortfall([1.0, 2.0], alpha=0.0)


def test_invalid_alpha_one() -> None:
    with pytest.raises(ValueError, match="alpha"):
        expected_shortfall([1.0, 2.0], alpha=1.0)


def test_invalid_alpha_negative() -> None:
    with pytest.raises(ValueError, match="alpha"):
        expected_shortfall([1.0, 2.0], alpha=-0.1)
