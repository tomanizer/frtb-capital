"""Tests for liquidity_horizon module."""

import math
from datetime import date

import numpy as np
import pytest

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.liquidity_horizon import (
    lha_es_breakdown_from_scalars,
    lha_es_breakdown_from_vectors,
    lha_es_from_scalars,
    lha_es_from_vectors,
    lha_es_scalar_approximation,
)
from frtb_ima.scenario import ScenarioVector, make_scenario_metadata


def _uniform_losses(n: int, value: float) -> list[float]:
    return [value] * n


def test_lha_es_from_scalars_lh10_only() -> None:
    es_by_lh = {LiquidityHorizon.LH10: 100.0}
    result = lha_es_from_scalars(es_by_lh)
    assert result == pytest.approx(100.0)


def test_lha_es_from_scalars_all_horizons() -> None:
    es = {
        LiquidityHorizon.LH10: 100.0,
        LiquidityHorizon.LH20: 80.0,
        LiquidityHorizon.LH40: 60.0,
        LiquidityHorizon.LH60: 40.0,
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
    lh_vectors = {
        LiquidityHorizon.LH10: _uniform_losses(100, 100.0),
        LiquidityHorizon.LH20: _uniform_losses(100, 80.0),
        LiquidityHorizon.LH40: _uniform_losses(100, 60.0),
        LiquidityHorizon.LH60: _uniform_losses(100, 40.0),
        LiquidityHorizon.LH120: _uniform_losses(100, 20.0),
    }
    scalar_result = lha_es_from_scalars(
        {
            LiquidityHorizon.LH10: 100.0,
            LiquidityHorizon.LH20: 80.0,
            LiquidityHorizon.LH40: 60.0,
            LiquidityHorizon.LH60: 40.0,
            LiquidityHorizon.LH120: 20.0,
        }
    )
    vector_result = lha_es_from_vectors(lh_vectors)
    assert vector_result == pytest.approx(scalar_result, rel=1e-6)


def test_lha_breakdown_from_vectors() -> None:
    metadata = make_scenario_metadata(
        [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)]
    )

    result = lha_es_breakdown_from_vectors(
        {
            LiquidityHorizon.LH10: ScenarioVector(
                values=np.array([100.0, 100.0, 100.0]),
                metadata=metadata,
            ),
            LiquidityHorizon.LH20: ScenarioVector(
                values=np.array([80.0, 80.0, 80.0]),
                metadata=metadata,
            ),
        }
    )

    lh10 = result.component_by_horizon(LiquidityHorizon.LH10)
    lh20 = result.component_by_horizon(LiquidityHorizon.LH20)

    assert lh10.expected_shortfall == pytest.approx(100.0)
    assert lh20.expected_shortfall == pytest.approx(80.0)
    assert result.metadata_aligned is True
    assert result.scenario_count == 3


def test_lha_breakdown_summary_lines() -> None:
    result = lha_es_breakdown_from_scalars(
        {
            LiquidityHorizon.LH10: 100.0,
            LiquidityHorizon.LH20: 50.0,
        }
    )
    summary = result.summary_lines()
    assert any("lha_es=" in line for line in summary)
    assert any("LH10" in line for line in summary)


def test_lha_es_missing_lh10_raises() -> None:
    with pytest.raises(KeyError):
        lha_es_from_vectors({LiquidityHorizon.LH20: [1.0, 2.0]})


def test_lha_es_from_scalars_missing_lh10_raises() -> None:
    with pytest.raises(KeyError):
        lha_es_from_scalars({LiquidityHorizon.LH20: 50.0})


def test_lha_es_missing_intermediate_horizons() -> None:
    lh_vectors = {
        LiquidityHorizon.LH10: _uniform_losses(100, 100.0),
        LiquidityHorizon.LH120: _uniform_losses(100, 20.0),
    }
    expected = math.sqrt(1 * 100**2 + 6 * 20**2)
    result = lha_es_from_vectors(lh_vectors)
    assert result == pytest.approx(expected, rel=1e-6)


def test_scalar_approximation_is_labelled_toy() -> None:
    result = lha_es_scalar_approximation(100.0, weighted_avg_lh_days=20.0)
    assert result == pytest.approx(100.0 * math.sqrt(2.0), rel=1e-9)
