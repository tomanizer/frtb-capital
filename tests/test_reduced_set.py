"""Tests for reduced-set IMCC diagnostics."""

import numpy as np
import pytest

from frtb_ima.reduced_set import (
    reduced_set_variation_explained,
    reduced_set_variation_explained_for_policy,
)
from frtb_ima.regimes import get_policy


def test_reduced_set_variation_explained_passes_perfect_match() -> None:
    full = np.linspace(100.0, 200.0, 60)

    result = reduced_set_variation_explained(full, full)

    assert result.variation_explained == pytest.approx(1.0)
    assert result.passed is True
    assert result.window_size == 60
    assert result.as_dict()["threshold"] == pytest.approx(0.75)


def test_reduced_set_variation_explained_uses_most_recent_window() -> None:
    full = np.concatenate([np.array([1_000.0]), np.linspace(100.0, 200.0, 60)])
    reduced = np.concatenate([np.array([0.0]), np.linspace(100.0, 200.0, 60)])

    result = reduced_set_variation_explained(full, reduced)

    assert result.variation_explained == pytest.approx(1.0)
    assert result.full_mean == pytest.approx(float(np.mean(full[-60:])))


def test_reduced_set_variation_explained_fails_poor_reduced_set() -> None:
    full = np.linspace(100.0, 200.0, 60)
    reduced = np.zeros(60)

    result = reduced_set_variation_explained(full, reduced)

    assert result.variation_explained < 0.75
    assert result.passed is False


def test_reduced_set_variation_explained_handles_degenerate_full_series() -> None:
    exact = reduced_set_variation_explained([100.0] * 60, [100.0] * 60)
    mismatch = reduced_set_variation_explained([100.0] * 60, [99.0] * 60)

    assert exact.degenerate_full_series is True
    assert exact.variation_explained == pytest.approx(1.0)
    assert exact.passed is True
    assert mismatch.degenerate_full_series is True
    assert mismatch.variation_explained == pytest.approx(0.0)
    assert mismatch.passed is False


def test_reduced_set_variation_explained_for_policy_uses_policy_defaults() -> None:
    policy = get_policy()
    full = np.linspace(100.0, 200.0, policy.reduced_set_coverage_window_days)

    result = reduced_set_variation_explained_for_policy(full, full, policy)

    assert result.window_size == policy.reduced_set_coverage_window_days
    assert result.threshold == pytest.approx(policy.reduced_set_variation_explained_threshold)


def test_reduced_set_variation_explained_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="equal length"):
        reduced_set_variation_explained([1.0] * 60, [1.0] * 59)
    with pytest.raises(ValueError, match="non-negative"):
        reduced_set_variation_explained([1.0] * 59 + [-1.0], [1.0] * 60)
    with pytest.raises(ValueError, match="at least 60"):
        reduced_set_variation_explained([1.0] * 59, [1.0] * 59)
    with pytest.raises(ValueError, match="threshold"):
        reduced_set_variation_explained([1.0] * 60, [1.0] * 60, threshold=1.1)
