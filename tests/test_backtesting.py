"""Tests for backtesting module."""

import math
from datetime import date, timedelta

import pytest

from frtb_ima.backtesting import (
    backtest,
    count_exceptions,
    trading_desk_backtest,
    trading_desk_backtest_trace,
    trading_desk_backtest_trace_for_policy,
)
from frtb_ima.regimes import get_policy


def test_count_exceptions_none() -> None:
    pnl = [100.0, 200.0, 50.0]
    var = [150.0, 250.0, 100.0]
    assert count_exceptions(pnl, var) == 0


def test_count_exceptions_all() -> None:
    # All actual losses exceed VaR
    pnl = [-200.0, -300.0, -400.0]
    var = [100.0, 100.0, 100.0]
    assert count_exceptions(pnl, var) == 3


def test_count_exceptions_exact_boundary_not_exception() -> None:
    # -pnl == var: NOT an exception (strict >)
    pnl = [-100.0]
    var = [100.0]
    assert count_exceptions(pnl, var) == 0


def test_count_exceptions_just_over() -> None:
    pnl = [-100.01]
    var = [100.0]
    assert count_exceptions(pnl, var) == 1


def test_count_exceptions_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        count_exceptions([1.0, 2.0], [1.0])


def test_count_exceptions_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        count_exceptions([], [])


def test_count_exceptions_rejects_non_positive_var() -> None:
    with pytest.raises(ValueError, match="positive"):
        count_exceptions([-100.0], [0.0])


def test_count_exceptions_rejects_non_finite_inputs() -> None:
    with pytest.raises(ValueError, match="finite"):
        count_exceptions([float("nan")], [100.0])


def test_backtest_window_trims_to_250() -> None:
    n = 300
    pnl = [100.0] * n          # all gains — no exceptions
    var = [50.0] * n
    result = backtest(pnl, pnl, var, window=250)
    assert result.window_size == 250
    assert result.apl_exceptions == 0
    assert result.hpl_exceptions == 0


def test_backtest_exception_zones() -> None:
    n = 250
    # 6 APL exceptions, 3 HPL exceptions
    apl = [-200.0] * 6 + [100.0] * (n - 6)
    hpl = [-200.0] * 3 + [100.0] * (n - 3)
    var = [100.0] * n
    result = backtest(apl, hpl, var)
    assert result.apl_exceptions == 6
    assert result.hpl_exceptions == 3
    assert result.apl_zone == "AMBER"
    assert result.hpl_zone == "GREEN"


def test_backtest_red_zone() -> None:
    n = 250
    apl = [-200.0] * 12 + [100.0] * (n - 12)
    var = [100.0] * n
    result = backtest(apl, apl, var)
    assert result.apl_zone == "RED"


def test_backtest_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError, match="window"):
        backtest([1.0], [1.0], [100.0], window=0)


def test_trading_desk_backtest_uses_975_and_99_percentile_limits() -> None:
    n = 250
    apl = [-200.0] * 12 + [-150.0] * 18 + [100.0] * (n - 30)
    hpl = [-200.0] * 5 + [-150.0] * 10 + [100.0] * (n - 15)
    var = {
        0.975: [100.0] * n,
        0.99: [175.0] * n,
    }

    result = trading_desk_backtest(apl, hpl, var)

    assert result.model_eligible is True
    assert result.level(0.99).apl_exceptions == 12
    assert result.level(0.99).exception_limit == pytest.approx(12.0)
    assert result.level(0.975).apl_exceptions == 30
    assert result.level(0.975).exception_limit == pytest.approx(30.0)


def test_trading_desk_backtest_fails_when_either_pnl_series_exceeds_limit() -> None:
    n = 250
    apl = [-200.0] * 13 + [100.0] * (n - 13)
    hpl = [100.0] * n
    var = {
        0.975: [100.0] * n,
        0.99: [100.0] * n,
    }

    result = trading_desk_backtest(apl, hpl, var)

    assert result.model_eligible is False
    assert result.level(0.99).apl_passed is False
    assert result.level(0.99).hpl_passed is True


def test_trading_desk_backtest_counts_missing_values_as_exceptions() -> None:
    n = 250
    apl = [100.0] * n
    hpl = [100.0] * n
    apl[0] = math.nan
    var = {
        0.975: [100.0] * n,
        0.99: [100.0] * n,
    }

    result = trading_desk_backtest(apl, hpl, var)

    assert result.level(0.99).apl_exceptions == 1
    assert result.level(0.975).apl_exceptions == 1


def test_trading_desk_backtest_trace_reports_dated_exception_reasons() -> None:
    n = 250
    start = date(2025, 1, 1)
    dates = tuple(start + timedelta(days=idx) for idx in range(n))
    apl = [100.0] * n
    hpl = [100.0] * n
    apl[0] = math.nan
    hpl[1] = -200.0
    var = {
        0.975: [100.0] * n,
        0.99: [100.0] * n,
    }

    result = trading_desk_backtest_trace(
        apl,
        hpl,
        var,
        observation_dates=dates,
    )

    level = result.level(0.99)
    assert result.result == trading_desk_backtest(apl, hpl, var)
    assert level.result.apl_exceptions == 1
    assert level.result.hpl_exceptions == 1
    assert len(level.observations) == n
    assert len(level.exception_observations()) == 2
    assert level.observations[0].observation_date == date(2025, 1, 1)
    assert level.observations[0].apl is None
    assert level.observations[0].apl_reason == "missing_pnl"
    assert level.observations[1].hpl_reason == "loss_exceeds_var"
    assert level.as_dict()["result"]["apl_exceptions"] == 1


def test_trading_desk_backtest_excludes_official_holiday_missing_values() -> None:
    n = 250
    apl = [100.0] * n
    hpl = [100.0] * n
    apl[0] = math.nan
    var = {
        0.975: [100.0] * n,
        0.99: [100.0] * n,
    }
    holidays = [False] * n
    holidays[0] = True

    result = trading_desk_backtest(apl, hpl, var, official_holiday_mask=holidays)

    assert result.level(0.99).apl_exceptions == 0
    assert result.level(0.975).apl_exceptions == 0


def test_trading_desk_backtest_trace_marks_official_holiday_exclusions() -> None:
    n = 250
    apl = [100.0] * n
    hpl = [100.0] * n
    apl[0] = math.nan
    var = {
        0.975: [100.0] * n,
        0.99: [100.0] * n,
    }
    holidays = [False] * n
    holidays[0] = True

    result = trading_desk_backtest_trace(
        apl,
        hpl,
        var,
        official_holiday_mask=holidays,
    )

    observation = result.level(0.99).observations[0]
    assert observation.official_holiday is True
    assert observation.apl_exception is False
    assert observation.apl_reason == "official_holiday"


def test_trading_desk_backtest_prorates_exception_limits_for_short_history() -> None:
    n = 125
    apl = [-200.0] * 6 + [100.0] * (n - 6)
    hpl = [100.0] * n
    var = {
        0.975: [100.0] * n,
        0.99: [100.0] * n,
    }

    result = trading_desk_backtest(
        apl,
        hpl,
        var,
        minimum_history=250,
        allow_prorated_thresholds=True,
    )

    assert result.window_size == 125
    assert result.level(0.99).exception_limit == pytest.approx(6.0)
    assert result.model_eligible is True


def test_trading_desk_backtest_trace_for_policy_uses_policy_window() -> None:
    policy = get_policy()
    n = policy.backtesting_window_days
    apl = [100.0] * n
    hpl = [100.0] * n
    var = {
        0.975: [100.0] * n,
        0.99: [100.0] * n,
    }

    result = trading_desk_backtest_trace_for_policy(apl, hpl, var, policy)

    assert result.window_size == policy.backtesting_window_days
    assert result.model_eligible is True


def test_trading_desk_backtest_trace_rejects_misaligned_dates() -> None:
    n = 250
    var = {
        0.975: [100.0] * n,
        0.99: [100.0] * n,
    }
    with pytest.raises(ValueError, match="observation_dates"):
        trading_desk_backtest_trace(
            [100.0] * n,
            [100.0] * n,
            var,
            observation_dates=[date(2025, 1, 1)],
        )
