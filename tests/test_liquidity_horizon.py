"""Tests for liquidity_horizon module."""

import math

import pytest

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.liquidity_horizon import (
    lha_es_from_scalars,
    lha_es_from_vectors,
    lha_es_scalar_approximation,
)


def _uniform_losses(n: int, value: float) -> list[float]:
    return [value] * n


def test_lha_es_from_scalars_lh10_only() -> None:
    # Only LH10 present. LHA_ES = sqrt(1.0 * ES10^2) = ES10.
    es_by_lh = {LiquidityHorizon.LH10: 100.0}
    result = lha_es_from_scalars(es_by_lh)
    assert result == pytest.approx(100.0)


def test_lha_es_from_scalars_all_horizons() -> None:
    # Manual calculation with known values.
    # weights: LH10=1, LH20=(20-10)/10=1, LH40=(40-20)/10=2, LH60=(60-40)/10=2, LH120=(120-60)/10=6
    es = {
        LiquidityHorizon.LH10:  100.0,
        LiquidityHorizon.LH20:  80.0,
        LiquidityHorizon.LH40:  60.0,
        LiquidityHorizon.LH60:  40.0,
        LiquidityHorizon.LH120: 20.0,
    }
    expected = math.sqrt(
        1 * 100**2
        + 1 * 80**2
        + 2 * 60**2
        + 2 * 40**2
        + 6 * 20**2
    )
    result = lha_es_from_scalars(es)
    assert result == pytest.approx(expected, rel=1e-9)


def test_lha_es_from_vectors_matches_scalars() -> None:
    # Constant loss vectors: ES = constant. Should match scalar path.
    lh_vectors = {
        LiquidityHorizon.LH10:  _uniform_losses(100, 100.0),
        LiquidityHorizon.LH20:  _uniform_losses(100, 80.0),
        LiquidityHorizon.LH40:  _uniform_losses(100, 60.0),
        LiquidityHorizon.LH60:  _uniform_losses(100, 40.0),
        LiquidityHorizon.LH120: _uniform_losses(100, 20.0),
    }
    scalar_result = lha_es_from_scalars({
        LiquidityHorizon.LH10:  100.0,
        LiquidityHorizon.LH20:  80.0,
        LiquidityHorizon.LH40:  60.0,
        LiquidityHorizon.LH60:  40.0,
        LiquidityHorizon.LH120: 20.0,
    })
    vector_result = lha_es_from_vectors(lh_vectors)
    assert vector_result == pytest.approx(scalar_result, rel=1e-6)


def test_lha_es_missing_lh10_raises() -> None:
    with pytest.raises(KeyError):
        lha_es_from_vectors({LiquidityHorizon.LH20: [1.0, 2.0]})


def test_lha_es_from_scalars_missing_lh10_raises() -> None:
    with pytest.raises(KeyError):
        lha_es_from_scalars({LiquidityHorizon.LH20: 50.0})


def test_lha_es_missing_intermediate_horizons() -> None:
    # If only LH10 and LH120 are provided, intermediate contributions are zero.
    lh_vectors = {
        LiquidityHorizon.LH10:  _uniform_losses(100, 100.0),
        LiquidityHorizon.LH120: _uniform_losses(100, 20.0),
    }
    expected = math.sqrt(1 * 100**2 + 6 * 20**2)
    result = lha_es_from_vectors(lh_vectors)
    assert result == pytest.approx(expected, rel=1e-6)


def test_scalar_approximation_is_labelled_toy() -> None:
    # Just confirm it runs and produces a reasonable number.
    # It is NOT the primary method.
    result = lha_es_scalar_approximation(100.0, weighted_avg_lh_days=20.0)
    assert result == pytest.approx(100.0 * math.sqrt(2.0), rel=1e-9)
