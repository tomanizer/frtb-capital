"""Property-based tests for expected shortfall."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from frtb_ima.expected_shortfall import ESEstimator, expected_shortfall

FINITE_LOSS = st.floats(
    min_value=-1_000_000.0,
    max_value=1_000_000.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)
NON_NEGATIVE_LOSS = st.floats(
    min_value=0.0,
    max_value=1_000_000.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)


@given(value=FINITE_LOSS, count=st.integers(min_value=1, max_value=40))
def test_expected_shortfall_of_constant_vector_is_constant(value: float, count: int) -> None:
    losses = [value] * count

    for estimator in ESEstimator:
        assert expected_shortfall(losses, alpha=0.975, estimator=estimator) == pytest.approx(value)


@given(
    losses=st.lists(NON_NEGATIVE_LOSS, min_size=1, max_size=40),
    increments=st.data(),
)
def test_expected_shortfall_is_monotonic_in_losses(
    losses: list[float],
    increments: st.DataObject,
) -> None:
    addends = increments.draw(
        st.lists(NON_NEGATIVE_LOSS, min_size=len(losses), max_size=len(losses))
    )
    larger_losses = [loss + addend for loss, addend in zip(losses, addends, strict=True)]

    for estimator in ESEstimator:
        assert expected_shortfall(
            larger_losses,
            alpha=0.975,
            estimator=estimator,
        ) >= expected_shortfall(losses, alpha=0.975, estimator=estimator)


@given(losses=st.lists(FINITE_LOSS, min_size=1, max_size=40))
def test_expected_shortfall_lies_inside_loss_range(losses: list[float]) -> None:
    lower = min(losses)
    upper = max(losses)
    tolerance = 1e-9 * max(1.0, abs(lower), abs(upper))

    for estimator in ESEstimator:
        es = expected_shortfall(losses, alpha=0.975, estimator=estimator)

        assert lower - tolerance <= es <= upper + tolerance


@given(losses=st.lists(FINITE_LOSS, min_size=1, max_size=40))
def test_expected_shortfall_unchanged_by_repeating_identical_sample(losses: list[float]) -> None:
    assert expected_shortfall(
        losses + losses,
        alpha=0.975,
        estimator=ESEstimator.WEIGHTED_INTERPOLATED,
    ) == pytest.approx(
        expected_shortfall(losses, alpha=0.975, estimator=ESEstimator.WEIGHTED_INTERPOLATED)
    )
