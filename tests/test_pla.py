"""Tests for PLA KS statistic."""

from datetime import date, timedelta

import pytest

from frtb_ima.pla import (
    ks_statistic,
    pla_assessment,
    pla_assessment_for_policy,
    pla_assessment_for_policy_with_diagnostics,
)
from frtb_ima.regimes import get_policy


def test_ks_identical_distributions() -> None:
    # Same vector: KS = 0
    vec = [float(i) for i in range(1, 101)]
    assert ks_statistic(vec, vec) == pytest.approx(0.0)


def test_ks_completely_separated() -> None:
    # Two non-overlapping distributions: KS should be 1.0
    hpl = [1.0, 2.0, 3.0]
    rtpl = [10.0, 20.0, 30.0]
    result = ks_statistic(hpl, rtpl)
    assert result == pytest.approx(1.0)


def test_ks_partial_overlap() -> None:
    hpl = [1.0, 2.0, 3.0, 4.0]
    rtpl = [2.0, 3.0, 4.0, 5.0]
    result = ks_statistic(hpl, rtpl)
    assert 0.0 < result < 1.0


def test_ks_empty_hpl_raises() -> None:
    with pytest.raises(ValueError, match="hpl"):
        ks_statistic([], [1.0, 2.0])


def test_ks_empty_rtpl_raises() -> None:
    with pytest.raises(ValueError, match="rtpl"):
        ks_statistic([1.0, 2.0], [])


def test_ks_accepts_numpy_arrays() -> None:
    import numpy as np

    vec = np.array([1.0, 2.0, 3.0])
    assert ks_statistic(vec, vec) == pytest.approx(0.0)


def test_ks_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        ks_statistic([1.0, float("nan")], [1.0, 2.0])


def test_pla_assessment_green_zone() -> None:
    vec = [float(i) for i in range(200)]
    result = pla_assessment(vec, vec)
    assert result.zone == "GREEN"
    assert result.ks_statistic == pytest.approx(0.0)


def test_pla_assessment_red_zone() -> None:
    hpl = [float(i) for i in range(1, 101)]
    rtpl = [float(i + 200) for i in range(1, 101)]
    result = pla_assessment(hpl, rtpl)
    assert result.zone == "RED"
    assert result.ks_statistic > 0.12


def test_pla_result_lengths() -> None:
    hpl = [1.0, 2.0, 3.0]
    rtpl = [1.0, 2.0, 3.0, 4.0]
    result = pla_assessment(hpl, rtpl)
    assert result.n_hpl == 3
    assert result.n_rtpl == 4


def test_pla_assessment_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        pla_assessment([1.0, 2.0], [1.0, 2.0], green_threshold=0.2, amber_threshold=0.1)


def test_pla_assessment_for_policy_with_diagnostics_reports_window() -> None:
    policy = get_policy()
    n = 300
    start = date(2025, 1, 1)
    dates = tuple(start + timedelta(days=idx) for idx in range(n))
    hpl = [float(idx) for idx in range(n)]
    rtpl = [float(idx) for idx in range(n)]

    result = pla_assessment_for_policy_with_diagnostics(
        hpl,
        rtpl,
        policy,
        observation_dates=dates,
    )

    assert result.pla == pla_assessment_for_policy(hpl, rtpl, policy)
    assert result.zone == "GREEN"
    assert result.diagnostics.available_observations == n
    assert result.diagnostics.window_size == policy.pla_window_days
    assert result.diagnostics.start_index == n - policy.pla_window_days
    assert result.diagnostics.start_date == dates[n - policy.pla_window_days]
    assert result.diagnostics.end_date == dates[-1]
    assert result.as_dict()["diagnostics"]["window_size"] == policy.pla_window_days


def test_pla_policy_assessment_requires_aligned_hpl_rtpl_lengths() -> None:
    policy = get_policy()
    with pytest.raises(ValueError, match="equal length"):
        pla_assessment_for_policy_with_diagnostics(
            [1.0] * policy.pla_minimum_history_days,
            [1.0] * (policy.pla_minimum_history_days + 1),
            policy,
        )


def test_pla_policy_assessment_rejects_misaligned_dates() -> None:
    policy = get_policy()
    hpl = [1.0] * policy.pla_minimum_history_days
    rtpl = [1.0] * policy.pla_minimum_history_days
    with pytest.raises(ValueError, match="observation_dates"):
        pla_assessment_for_policy_with_diagnostics(
            hpl,
            rtpl,
            policy,
            observation_dates=[date(2025, 1, 1)],
        )
