"""Property-based tests for LHA ES, IMCC, and SES aggregation."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.expected_shortfall import ESEstimator
from frtb_ima.imcc import imcc_breakdown
from frtb_ima.liquidity_horizon import lha_es_from_scalars
from frtb_ima.nmrf import aggregate_ses, aggregate_ses_breakdown

NON_NEGATIVE_SCALAR = st.floats(
    min_value=0.0,
    max_value=1_000_000.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)
WEIGHT = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)
RHO = WEIGHT


@given(
    lh10=NON_NEGATIVE_SCALAR,
    lh20=NON_NEGATIVE_SCALAR,
    lh40=NON_NEGATIVE_SCALAR,
    lh60=NON_NEGATIVE_SCALAR,
    lh120=NON_NEGATIVE_SCALAR,
)
def test_lha_es_is_at_least_lh10_es(
    lh10: float,
    lh20: float,
    lh40: float,
    lh60: float,
    lh120: float,
) -> None:
    es_by_lh = {
        LiquidityHorizon.LH10: lh10,
        LiquidityHorizon.LH20: lh20,
        LiquidityHorizon.LH40: lh40,
        LiquidityHorizon.LH60: lh60,
        LiquidityHorizon.LH120: lh120,
    }

    assert (
        lha_es_from_scalars(
            es_by_lh,
            alpha=0.975,
            estimator=ESEstimator.WEIGHTED_INTERPOLATED,
        )
        >= lh10
    )


@given(base=NON_NEGATIVE_SCALAR, increment=NON_NEGATIVE_SCALAR)
def test_lha_es_is_monotonic_in_any_liquidity_horizon_bucket(
    base: float,
    increment: float,
) -> None:
    lower = {
        LiquidityHorizon.LH10: base,
        LiquidityHorizon.LH20: base,
    }
    higher = {
        LiquidityHorizon.LH10: base,
        LiquidityHorizon.LH20: base + increment,
    }

    assert lha_es_from_scalars(
        higher,
        alpha=0.975,
        estimator=ESEstimator.WEIGHTED_INTERPOLATED,
    ) >= lha_es_from_scalars(
        lower,
        alpha=0.975,
        estimator=ESEstimator.WEIGHTED_INTERPOLATED,
    )


@given(unconstrained=NON_NEGATIVE_SCALAR, constrained=NON_NEGATIVE_SCALAR, weight=WEIGHT)
def test_imcc_blend_is_convex_combination(
    unconstrained: float,
    constrained: float,
    weight: float,
) -> None:
    result = imcc_breakdown(
        {LiquidityHorizon.LH10: [unconstrained] * 3},
        {RiskClass.GIRR: {LiquidityHorizon.LH10: [constrained] * 3}},
        alpha=0.975,
        estimator=ESEstimator.WEIGHTED_INTERPOLATED,
        w=weight,
    )
    lower = min(unconstrained, constrained)
    upper = max(unconstrained, constrained)
    tolerance = 1e-9 * max(1.0, abs(lower), abs(upper))

    assert lower - tolerance <= result.imcc <= upper + tolerance
    assert result.imcc == pytest.approx(weight * unconstrained + (1.0 - weight) * constrained)


@given(
    type_a=st.lists(NON_NEGATIVE_SCALAR, min_size=0, max_size=20),
    type_b=st.lists(NON_NEGATIVE_SCALAR, min_size=0, max_size=20),
    rho=RHO,
)
def test_ses_aggregation_dominates_type_components(
    type_a: list[float],
    type_b: list[float],
    rho: float,
) -> None:
    result = aggregate_ses_breakdown(type_a, type_b, type_b_rho=rho)
    type_a_ses = result.type_a_sum_of_squares**0.5
    type_b_ses = result.type_b_correlated_term**0.5

    assert result.total_ses >= type_a_ses
    assert result.total_ses >= type_b_ses


@given(
    type_a=st.lists(NON_NEGATIVE_SCALAR, min_size=0, max_size=20),
    type_b=st.lists(NON_NEGATIVE_SCALAR, min_size=0, max_size=20),
    increment=NON_NEGATIVE_SCALAR,
    rho=RHO,
)
def test_ses_aggregation_is_monotonic_when_a_type_a_ses_grows(
    type_a: list[float],
    type_b: list[float],
    increment: float,
    rho: float,
) -> None:
    lower = aggregate_ses(type_a, type_b, type_b_rho=rho)
    higher = aggregate_ses([*type_a, increment], type_b, type_b_rho=rho)

    assert higher >= lower
