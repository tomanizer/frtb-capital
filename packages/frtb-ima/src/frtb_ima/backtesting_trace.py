"""
Trading-desk IMA backtesting trace assembly.

This module owns multi-level APL/HPL VaR backtesting and dated observation
traces. It keeps exception counting vectorized and materializes trace records
after masks have been computed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from frtb_ima.backtesting_trace_inputs import (
    prepare_trace_inputs,
    validated_minimum_history,
)
from frtb_ima.backtesting_trace_levels import build_level_trace
from frtb_ima.backtesting_types import (
    BacktestLevelResult,
    BacktestLevelTrace,
    BoolVector,
    FloatVector,
    TradingDeskBacktestResult,
    TradingDeskBacktestTraceResult,
)
from frtb_ima.calendar import BusinessCalendar
from frtb_ima.regimes import DEFAULT_BACKTESTING_EXCEPTION_LIMITS
from frtb_ima.validation.observation_windows import (
    require_positive_observation_count as _require_positive_observation_count,
)
from frtb_ima.validation.observation_windows import (
    require_positive_optional_observation_count as _require_positive_optional_observation_count,
)
from frtb_ima.validation.observation_windows import (
    select_recent_observation_window as _select_recent_observation_window,
)


def trading_desk_backtest(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates_by_confidence: Mapping[float, FloatVector],
    window: int = 250,
    exception_limits: Sequence[tuple[float, int]] = DEFAULT_BACKTESTING_EXCEPTION_LIMITS,
    minimum_history: int | None = None,
    allow_prorated_thresholds: bool = False,
    official_holiday_mask: BoolVector | None = None,
    observation_dates: Sequence[date] | None = None,
    calendar: BusinessCalendar | None = None,
) -> TradingDeskBacktestResult:
    """Run NPR 2.0 trading-desk backtesting across VaR confidence levels.

    Missing APL, HPL, or VaR values count as exceptions unless the day is marked
    as an official holiday.
    Parameters
    ----------
    apl : FloatVector
        Apl.
    hpl : FloatVector
        Hpl.
    var_estimates_by_confidence : Mapping[float, FloatVector]
        Var estimates by confidence.
    window : int, optional
        Window.
    exception_limits : Sequence[tuple[float, int]], optional
        Exception limits.
    minimum_history : int | None, optional
        Minimum history.
    allow_prorated_thresholds : bool, optional
        Allow prorated thresholds.
    official_holiday_mask : BoolVector | None, optional
        Official holiday mask.
    observation_dates : Sequence[date] | None, optional
        Observation dates.
    calendar : BusinessCalendar | None, optional
        Calendar.

    Returns
    -------
    TradingDeskBacktestResult
        Result of the operation.
    """
    return trading_desk_backtest_trace(
        apl,
        hpl,
        var_estimates_by_confidence,
        window=window,
        exception_limits=exception_limits,
        minimum_history=minimum_history,
        allow_prorated_thresholds=allow_prorated_thresholds,
        official_holiday_mask=official_holiday_mask,
        observation_dates=observation_dates,
        calendar=calendar,
    ).result


def trading_desk_backtest_trace(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates_by_confidence: Mapping[float, FloatVector],
    window: int = 250,
    exception_limits: Sequence[tuple[float, int]] = DEFAULT_BACKTESTING_EXCEPTION_LIMITS,
    minimum_history: int | None = None,
    allow_prorated_thresholds: bool = False,
    official_holiday_mask: BoolVector | None = None,
    observation_dates: Sequence[date] | None = None,
    calendar: BusinessCalendar | None = None,
) -> TradingDeskBacktestTraceResult:
    """Run NPR 2.0 trading-desk backtesting with per-observation audit traces.

    Counts remain vectorized; trace records are built after exception masks.
    Parameters
    ----------
    apl : FloatVector
        Apl.
    hpl : FloatVector
        Hpl.
    var_estimates_by_confidence : Mapping[float, FloatVector]
        Var estimates by confidence.

    Returns
    -------
    TradingDeskBacktestTraceResult
        Result of the operation.
    """
    _require_positive_observation_count(window, field="window")
    _require_positive_optional_observation_count(minimum_history, field="minimum_history")
    inputs = prepare_trace_inputs(
        apl,
        hpl,
        var_estimates_by_confidence,
        exception_limits,
        official_holiday_mask,
        observation_dates,
    )
    validated_minimum_history(inputs.min_length, minimum_history, allow_prorated_thresholds)

    window_size = min(window, inputs.min_length)
    start_index = inputs.min_length - window_size
    date_window = _select_recent_observation_window(
        inputs.dates,
        window_size,
        calendar=calendar,
        validation_label="backtesting",
    )
    apl_w = inputs.apl[-window_size:]
    hpl_w = inputs.hpl[-window_size:]
    holiday_w = inputs.holiday_mask[-window_size:] if inputs.holiday_mask is not None else None
    level_results: list[BacktestLevelResult] = []
    level_traces: list[BacktestLevelTrace] = []
    for confidence_level, limit in exception_limits:
        level_result, level_trace = build_level_trace(
            confidence_level,
            limit,
            var_estimates_by_confidence[confidence_level],
            apl_w=apl_w,
            hpl_w=hpl_w,
            holiday_w=holiday_w,
            dates_w=date_window.observation_dates,
            start_index=start_index,
            window=window,
            window_size=window_size,
            allow_prorated_thresholds=allow_prorated_thresholds,
        )
        level_results.append(level_result)
        level_traces.append(level_trace)

    result = TradingDeskBacktestResult(
        levels=tuple(level_results),
        window_size=window_size,
        model_eligible=all(result.level_passed for result in level_results),
        calendar_source=date_window.calendar_source,
        calendar_version=date_window.calendar_version,
        calendar_basis=date_window.calendar_basis,
        official_holiday_count=date_window.official_holiday_count,
        missing_business_dates=date_window.missing_business_dates,
    )
    return TradingDeskBacktestTraceResult(result=result, levels=tuple(level_traces))


__all__ = ("trading_desk_backtest", "trading_desk_backtest_trace")
