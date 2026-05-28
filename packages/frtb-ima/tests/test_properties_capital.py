"""Property-based tests for desk-level capital assembly."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from frtb_ima.capital import models_based_capital

NON_NEGATIVE_CAPITAL = st.floats(
    min_value=0.0,
    max_value=1_000_000.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)
MULTIPLIER = st.floats(
    min_value=1.5,
    max_value=3.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)


@given(
    imcc_t_minus_1=NON_NEGATIVE_CAPITAL,
    ses_t_minus_1=NON_NEGATIVE_CAPITAL,
    imcc_60d_avg=NON_NEGATIVE_CAPITAL,
    ses_60d_avg=NON_NEGATIVE_CAPITAL,
    multiplier=MULTIPLIER,
    pla_addon=NON_NEGATIVE_CAPITAL,
    increment=NON_NEGATIVE_CAPITAL,
)
def test_models_based_capital_is_monotonic_in_spot_imcc(
    imcc_t_minus_1: float,
    ses_t_minus_1: float,
    imcc_60d_avg: float,
    ses_60d_avg: float,
    multiplier: float,
    pla_addon: float,
    increment: float,
) -> None:
    lower = models_based_capital(
        imcc_t_minus_1,
        ses_t_minus_1,
        imcc_60d_avg,
        ses_60d_avg,
        multiplier,
        pla_addon,
    )
    higher = models_based_capital(
        imcc_t_minus_1 + increment,
        ses_t_minus_1,
        imcc_60d_avg,
        ses_60d_avg,
        multiplier,
        pla_addon,
    )

    assert higher.models_based_capital >= lower.models_based_capital


@given(
    imcc_t_minus_1=NON_NEGATIVE_CAPITAL,
    ses_t_minus_1=NON_NEGATIVE_CAPITAL,
    imcc_60d_avg=NON_NEGATIVE_CAPITAL,
    ses_60d_avg=NON_NEGATIVE_CAPITAL,
    multiplier=MULTIPLIER,
    pla_addon=NON_NEGATIVE_CAPITAL,
    increment=NON_NEGATIVE_CAPITAL,
)
def test_models_based_capital_is_monotonic_in_average_imcc(
    imcc_t_minus_1: float,
    ses_t_minus_1: float,
    imcc_60d_avg: float,
    ses_60d_avg: float,
    multiplier: float,
    pla_addon: float,
    increment: float,
) -> None:
    lower = models_based_capital(
        imcc_t_minus_1,
        ses_t_minus_1,
        imcc_60d_avg,
        ses_60d_avg,
        multiplier,
        pla_addon,
    )
    higher = models_based_capital(
        imcc_t_minus_1,
        ses_t_minus_1,
        imcc_60d_avg + increment,
        ses_60d_avg,
        multiplier,
        pla_addon,
    )

    assert higher.models_based_capital >= lower.models_based_capital


@given(
    imcc_t_minus_1=NON_NEGATIVE_CAPITAL,
    ses_t_minus_1=NON_NEGATIVE_CAPITAL,
    imcc_60d_avg=NON_NEGATIVE_CAPITAL,
    ses_60d_avg=NON_NEGATIVE_CAPITAL,
    multiplier=MULTIPLIER,
    pla_addon=NON_NEGATIVE_CAPITAL,
)
def test_models_based_capital_binding_term_is_deterministic(
    imcc_t_minus_1: float,
    ses_t_minus_1: float,
    imcc_60d_avg: float,
    ses_60d_avg: float,
    multiplier: float,
    pla_addon: float,
) -> None:
    result = models_based_capital(
        imcc_t_minus_1,
        ses_t_minus_1,
        imcc_60d_avg,
        ses_60d_avg,
        multiplier,
        pla_addon,
    )
    spot_term = imcc_t_minus_1 + ses_t_minus_1
    average_term = multiplier * imcc_60d_avg + ses_60d_avg

    assert result.binding_term == ("SPOT" if spot_term >= average_term else "AVERAGE")
    assert result.models_based_capital == pytest.approx(max(spot_term, average_term) + pla_addon)
