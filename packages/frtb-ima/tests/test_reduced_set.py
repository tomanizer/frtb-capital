"""Tests for reduced-set IMCC diagnostics."""

import logging
from dataclasses import replace

import numpy as np
import pytest

from frtb_ima.reduced_set import (
    reduced_set_variation_explained,
    reduced_set_variation_explained_for_policy,
    select_reduced_risk_factor_set,
    select_reduced_risk_factor_set_for_policy,
)
from frtb_ima.regimes import get_policy


def test_reduced_set_variation_explained_passes_perfect_match() -> None:
    full = np.linspace(100.0, 200.0, 60)

    result = reduced_set_variation_explained(full, full)

    assert result.variation_explained == pytest.approx(1.0)
    assert result.passed is True
    assert result.window_size == 60
    centred_full = full - np.mean(full)
    assert result.as_dict() == {
        "window_size": 60,
        "minimum_history": 60,
        "threshold": pytest.approx(0.75),
        "variation_explained": pytest.approx(1.0),
        "passed": True,
        "full_mean": pytest.approx(float(np.mean(full))),
        "sum_squared_residuals": pytest.approx(0.0),
        "total_sum_squares": pytest.approx(float(np.dot(centred_full, centred_full))),
        "degenerate_full_series": False,
    }


def test_reduced_set_variation_explained_uses_most_recent_window() -> None:
    full = np.concatenate([np.array([1_000.0]), np.linspace(100.0, 200.0, 60)])
    reduced = np.concatenate([np.array([0.0]), np.linspace(100.0, 200.0, 60)])

    result = reduced_set_variation_explained(full, reduced)

    assert result.variation_explained == pytest.approx(1.0)
    assert result.full_mean == pytest.approx(float(np.mean(full[-60:])))
    assert result.window_size == 60


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


def test_reduced_set_variation_explained_classifies_exact_threshold() -> None:
    full = np.array([0.0, 1.0, 2.0, 3.0])
    reduced = np.array([0.0, 1.5, 1.5, 3.0])

    result = reduced_set_variation_explained(
        full,
        reduced,
        window=4,
        minimum_history=None,
        threshold=0.9,
    )

    assert result.sum_squared_residuals == pytest.approx(0.5)
    assert result.total_sum_squares == pytest.approx(5.0)
    assert result.variation_explained == pytest.approx(0.9)
    assert result.passed is True


def test_reduced_set_variation_explained_for_policy_uses_policy_defaults() -> None:
    policy = replace(get_policy(), reduced_set_coverage_window_days=61)
    full = np.linspace(100.0, 200.0, policy.reduced_set_coverage_window_days)

    result = reduced_set_variation_explained_for_policy(full, full, policy)

    assert result.window_size == policy.reduced_set_coverage_window_days
    assert result.threshold == pytest.approx(policy.reduced_set_variation_explained_threshold)


def test_reduced_set_variation_explained_for_policy_logs_audit_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = replace(get_policy(), reduced_set_coverage_window_days=61)
    full = np.linspace(100.0, 200.0, policy.reduced_set_coverage_window_days)
    caplog.set_level(logging.INFO, logger="frtb_ima.reduced_set")

    result = reduced_set_variation_explained_for_policy(
        full,
        full,
        policy,
        run_id="run-1",
        desk_id="desk-a",
    )

    record = caplog.records[-1]
    assert record.getMessage() == "reduced_set_variation_explained_complete"
    assert record.run_id == "run-1"
    assert record.desk_id == "desk-a"
    assert record.regime == policy.regime.value
    assert record.variation_explained == pytest.approx(result.variation_explained)
    assert record.threshold == pytest.approx(policy.reduced_set_variation_explained_threshold)
    assert record.passed is True
    assert record.window_size == policy.reduced_set_coverage_window_days


def test_reduced_set_variation_explained_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="one-dimensional"):
        reduced_set_variation_explained([[1.0] * 60], [[1.0] * 60])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="non-empty"):
        reduced_set_variation_explained([], [], minimum_history=None)
    with pytest.raises(ValueError, match="finite"):
        reduced_set_variation_explained([1.0] * 59 + [float("nan")], [1.0] * 60)
    with pytest.raises(ValueError, match="equal length"):
        reduced_set_variation_explained([1.0] * 60, [1.0] * 59)
    with pytest.raises(ValueError, match="non-negative"):
        reduced_set_variation_explained([1.0] * 59 + [-1.0], [1.0] * 60)
    with pytest.raises(ValueError, match="at least 60"):
        reduced_set_variation_explained([1.0] * 59, [1.0] * 59)
    with pytest.raises(ValueError, match="window"):
        reduced_set_variation_explained([1.0] * 60, [1.0] * 60, window=0)
    with pytest.raises(ValueError, match="minimum_history"):
        reduced_set_variation_explained([1.0] * 60, [1.0] * 60, minimum_history=0)
    with pytest.raises(ValueError, match="threshold"):
        reduced_set_variation_explained([1.0] * 60, [1.0] * 60, threshold=1.1)


def test_select_reduced_risk_factor_set_matches_hand_calculated_case() -> None:
    factor_a = np.array([6.0, 12.0, 18.0, 24.0])
    factor_b = np.array([4.0, 8.0, 12.0, 16.0])
    full = factor_a + factor_b

    result = select_reduced_risk_factor_set(
        full,
        {"A": factor_a, "B": factor_b},
        window=4,
        minimum_history=None,
        threshold=0.75,
    )

    assert result.selected_factor_names == ("A", "B")
    assert result.variation_explained == pytest.approx(1.0)
    assert result.passed is True
    assert result.full_current_lha_es == pytest.approx(tuple(full))
    assert result.reduced_current_lha_es == pytest.approx(tuple(full))
    assert len(result.iteration_trace) == 2
    assert result.iteration_trace[0].variation_explained == pytest.approx(0.04)
    assert result.iteration_trace[0].as_dict() == {
        "iteration": 1,
        "added_factor": "A",
        "selected_factor_names": ["A"],
        "factor_contribution_sum": pytest.approx(60.0),
        "factor_contribution_mean": pytest.approx(15.0),
        "variation_explained": pytest.approx(0.04),
        "passed": False,
    }
    payload = result.as_dict()
    assert payload["selected_factor_names"] == ["A", "B"]
    assert payload["iteration_trace"][1]["passed"] is True
    assert payload["coverage_result"]["variation_explained"] == pytest.approx(1.0)


def test_select_reduced_risk_factor_set_stops_when_one_factor_is_enough() -> None:
    full = np.array([10.0, 20.0, 30.0, 40.0])

    result = select_reduced_risk_factor_set(
        full,
        {"dominant": full, "immaterial": np.zeros(4)},
        window=4,
        minimum_history=None,
        threshold=0.75,
    )

    assert result.selected_factor_names == ("dominant",)
    assert result.variation_explained == pytest.approx(1.0)
    assert len(result.iteration_trace) == 1


def test_select_reduced_risk_factor_set_respects_minimum_factors_after_threshold_passes() -> None:
    full = np.array([10.0, 20.0, 30.0, 40.0])

    result = select_reduced_risk_factor_set(
        full,
        {"dominant": full, "reserve": np.zeros(4)},
        window=4,
        minimum_history=None,
        threshold=0.75,
        minimum_factors=2,
    )

    assert result.selected_factor_names == ("dominant", "reserve")
    assert [step.passed for step in result.iteration_trace] == [False, True]
    assert result.reduced_current_lha_es == pytest.approx(tuple(full))


def test_select_reduced_risk_factor_set_tie_breaks_by_factor_name() -> None:
    full = np.array([10.0, 20.0, 30.0, 40.0])
    equal_1 = np.array([1.0, 2.0, 3.0, 4.0])
    equal_2 = np.array([4.0, 3.0, 2.0, 1.0])

    result = select_reduced_risk_factor_set(
        full,
        {"beta": equal_2, "alpha": equal_1},
        window=4,
        minimum_history=None,
        threshold=0.0,
        minimum_factors=2,
    )

    assert result.selected_factor_names == ("alpha", "beta")
    assert result.iteration_trace[0].added_factor == "alpha"
    assert result.iteration_trace[1].added_factor == "beta"


def test_select_reduced_risk_factor_set_orders_by_contribution_before_name() -> None:
    full = np.array([10.0, 20.0, 30.0, 40.0])
    high = np.array([7.0, 14.0, 21.0, 28.0])
    low = np.array([1.0, 2.0, 3.0, 4.0])

    result = select_reduced_risk_factor_set(
        full,
        {"alpha_low": low, "zeta_high": high},
        window=4,
        minimum_history=None,
        threshold=0.0,
        minimum_factors=2,
    )

    assert result.selected_factor_names == ("zeta_high", "alpha_low")
    assert [step.added_factor for step in result.iteration_trace] == [
        "zeta_high",
        "alpha_low",
    ]


def test_select_reduced_risk_factor_set_returns_failed_result_when_threshold_unmet() -> None:
    full = np.array([100.0, 200.0, 300.0, 400.0])

    result = select_reduced_risk_factor_set(
        full,
        {
            "larger": np.array([10.0, 20.0, 30.0, 40.0]),
            "smaller": np.array([5.0, 10.0, 15.0, 20.0]),
        },
        window=4,
        minimum_history=None,
        threshold=0.75,
    )

    assert result.selected_factor_names == ("larger", "smaller")
    assert result.passed is False
    assert result.variation_explained < 0.75


def test_select_reduced_risk_factor_set_for_policy_uses_policy_defaults() -> None:
    policy = replace(get_policy(), reduced_set_coverage_window_days=61)
    full = np.linspace(100.0, 200.0, policy.reduced_set_coverage_window_days)

    result = select_reduced_risk_factor_set_for_policy(
        full,
        {"all": full},
        policy,
    )

    assert result.window_size == policy.reduced_set_coverage_window_days
    assert result.minimum_factors == policy.reduced_set_minimum_factor_count
    assert result.threshold == pytest.approx(policy.reduced_set_variation_explained_threshold)
    assert result.selected_factor_names == ("all",)


def test_select_reduced_risk_factor_set_for_policy_logs_audit_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = replace(get_policy(), reduced_set_coverage_window_days=61)
    full = np.linspace(100.0, 200.0, policy.reduced_set_coverage_window_days)
    caplog.set_level(logging.INFO, logger="frtb_ima.reduced_set")

    result = select_reduced_risk_factor_set_for_policy(
        full,
        {"all": full},
        policy,
        run_id="run-2",
        desk_id="desk-b",
    )

    record = caplog.records[-1]
    assert record.getMessage() == "reduced_set_selection_complete"
    assert record.run_id == "run-2"
    assert record.desk_id == "desk-b"
    assert record.regime == policy.regime.value
    assert record.selected_factor_count == len(result.selected_factor_names)
    assert record.variation_explained == pytest.approx(result.variation_explained)
    assert record.threshold == pytest.approx(policy.reduced_set_variation_explained_threshold)
    assert record.passed is True
    assert record.window_size == policy.reduced_set_coverage_window_days


def test_select_reduced_risk_factor_set_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        select_reduced_risk_factor_set([1.0] * 60, {})
    with pytest.raises(ValueError, match="at least 60"):
        select_reduced_risk_factor_set([1.0] * 59, {"A": [1.0] * 59})
    with pytest.raises(ValueError, match="align"):
        select_reduced_risk_factor_set([1.0] * 60, {"A": [1.0] * 59})
    with pytest.raises(ValueError, match="non-empty"):
        select_reduced_risk_factor_set([1.0] * 60, {"": [1.0] * 60})
    with pytest.raises(ValueError, match="non-negative"):
        select_reduced_risk_factor_set([1.0] * 60, {"A": [1.0] * 59 + [-1.0]})
    with pytest.raises(ValueError, match="threshold"):
        select_reduced_risk_factor_set([1.0] * 60, {"A": [1.0] * 60}, threshold=1.1)
    with pytest.raises(ValueError, match="minimum_factors"):
        select_reduced_risk_factor_set([1.0] * 60, {"A": [1.0] * 60}, minimum_factors=0)
    with pytest.raises(ValueError, match="minimum_factors"):
        select_reduced_risk_factor_set([1.0] * 60, {"A": [1.0] * 60}, minimum_factors=2)
