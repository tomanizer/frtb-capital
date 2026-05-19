"""Tests for NMRF SES module."""

import math

import pytest

from frtb_ima.nmrf import (
    aggregate_ses,
    aggregate_ses_type_a,
    aggregate_ses_type_b,
    ses_for_nmrf_linear,
)


def test_ses_linear_basic() -> None:
    assert ses_for_nmrf_linear(100.0, 0.05) == pytest.approx(5.0)


def test_ses_linear_negative_sensitivity() -> None:
    # Short position — abs(sensitivity) used
    assert ses_for_nmrf_linear(-200.0, 0.03) == pytest.approx(6.0)


def test_ses_linear_negative_shock() -> None:
    assert ses_for_nmrf_linear(100.0, -0.05) == pytest.approx(5.0)


def test_ses_linear_zero() -> None:
    assert ses_for_nmrf_linear(0.0, 0.10) == pytest.approx(0.0)


def test_aggregate_ses_type_a_linear_sum() -> None:
    values = [10.0, 20.0, 30.0]
    assert aggregate_ses_type_a(values) == pytest.approx(60.0)


def test_aggregate_ses_type_a_empty() -> None:
    assert aggregate_ses_type_a([]) == pytest.approx(0.0)


def test_aggregate_ses_type_b_rho_zero() -> None:
    # rho=0: fully diversified -> sqrt(sum of squares)
    values = [3.0, 4.0]
    result = aggregate_ses_type_b(values, rho=0.0)
    assert result == pytest.approx(5.0)  # sqrt(9 + 16)


def test_aggregate_ses_type_b_rho_one() -> None:
    # rho=1: fully correlated -> linear sum
    values = [3.0, 4.0]
    result = aggregate_ses_type_b(values, rho=1.0)
    assert result == pytest.approx(7.0)


def test_aggregate_ses_type_b_default_rho() -> None:
    values = [10.0, 10.0]
    rho = 0.36
    expected = math.sqrt(rho * 20**2 + (1 - rho) * (10**2 + 10**2))
    result = aggregate_ses_type_b(values)
    assert result == pytest.approx(expected, rel=1e-9)


def test_aggregate_ses_type_b_invalid_rho() -> None:
    with pytest.raises(ValueError, match="rho"):
        aggregate_ses_type_b([1.0], rho=1.5)


def test_aggregate_ses_type_b_empty() -> None:
    assert aggregate_ses_type_b([]) == pytest.approx(0.0)


def test_aggregate_ses_combines_a_and_b() -> None:
    type_a = [10.0, 20.0]       # SES_A = 30
    type_b = [5.0, 5.0]         # SES_B = aggregate_ses_type_b([5, 5])
    expected = aggregate_ses_type_a(type_a) + aggregate_ses_type_b(type_b)
    result = aggregate_ses(type_a, type_b)
    assert result == pytest.approx(expected, rel=1e-9)
