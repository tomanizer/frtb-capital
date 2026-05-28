"""Property-based tests for PLA statistics."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from frtb_ima.pla import ks_statistic, spearman_correlation

FINITE_PNL = st.floats(
    min_value=-1_000_000.0,
    max_value=1_000_000.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)
UNIQUE_PNL_VECTOR = st.lists(FINITE_PNL, min_size=2, max_size=30, unique=True)


@given(values=UNIQUE_PNL_VECTOR)
def test_spearman_identity_and_reverse_extremes(values: list[float]) -> None:
    assert spearman_correlation(values, values) == pytest.approx(1.0)
    assert spearman_correlation(values, [-value for value in values]) == pytest.approx(-1.0)


@given(values=UNIQUE_PNL_VECTOR)
def test_spearman_invariant_under_increasing_rank_preserving_transform(
    values: list[float],
) -> None:
    rank_by_value = {value: rank for rank, value in enumerate(sorted(values), start=1)}
    transformed = [float(rank_by_value[value]) for value in values]

    assert spearman_correlation(values, transformed) == pytest.approx(1.0)


@given(left=UNIQUE_PNL_VECTOR, right=UNIQUE_PNL_VECTOR)
def test_spearman_is_symmetric(left: list[float], right: list[float]) -> None:
    n = min(len(left), len(right))

    assert spearman_correlation(left[:n], right[:n]) == pytest.approx(
        spearman_correlation(right[:n], left[:n])
    )


@given(values=st.lists(FINITE_PNL, min_size=1, max_size=40))
def test_ks_identical_samples_are_zero(values: list[float]) -> None:
    assert ks_statistic(values, values) == pytest.approx(0.0)


@given(
    left=st.lists(FINITE_PNL, min_size=1, max_size=40),
    right=st.lists(FINITE_PNL, min_size=1, max_size=40),
)
def test_ks_is_symmetric_and_unit_interval(left: list[float], right: list[float]) -> None:
    left_right = ks_statistic(left, right)

    assert 0.0 <= left_right <= 1.0
    assert left_right == pytest.approx(ks_statistic(right, left))
