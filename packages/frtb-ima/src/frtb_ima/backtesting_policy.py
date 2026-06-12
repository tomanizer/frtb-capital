"""
Policy wrappers for IMA backtesting.

This module applies ``RegulatoryPolicy`` backtesting parameters and emits
run-level logging for scalar and trading-desk backtesting calculations.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import date

from frtb_ima.backtesting_core import backtest
from frtb_ima.backtesting_trace import trading_desk_backtest, trading_desk_backtest_trace
from frtb_ima.backtesting_types import (
    BacktestResult,
    BoolVector,
    FloatVector,
    TradingDeskBacktestResult,
    TradingDeskBacktestTraceResult,
)
from frtb_ima.calendar import BusinessCalendar
from frtb_ima.logging import calculation_log_extra
from frtb_ima.regimes import RegulatoryPolicy

logger = logging.getLogger(__name__)


def trading_desk_backtest_for_policy(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates_by_confidence: Mapping[float, FloatVector],
    policy: RegulatoryPolicy,
    allow_prorated_thresholds: bool = False,
    official_holiday_mask: BoolVector | None = None,
    observation_dates: Sequence[date] | None = None,
    calendar: BusinessCalendar | None = None,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> TradingDeskBacktestResult:
    """Run trading-desk backtesting using policy gate parameters.
    Parameters
    ----------
    apl : FloatVector
        Apl.
    hpl : FloatVector
        Hpl.
    var_estimates_by_confidence : Mapping[float, FloatVector]
        Var estimates by confidence.
    policy : RegulatoryPolicy
        Policy.
    allow_prorated_thresholds : bool, optional
        Allow prorated thresholds.
    official_holiday_mask : BoolVector | None, optional
        Official holiday mask.
    observation_dates : Sequence[date] | None, optional
        Observation dates.
    calendar : BusinessCalendar | None, optional
        Calendar.
    run_id : str | None, optional
        Run id.
    desk_id : str | None, optional
        Desk id.

    Returns
    -------
    TradingDeskBacktestResult
        Result of the operation.
    """
    result = trading_desk_backtest(
        apl,
        hpl,
        var_estimates_by_confidence,
        window=policy.backtesting_window_days,
        exception_limits=policy.backtesting_exception_limits,
        minimum_history=policy.backtesting_minimum_history_days,
        allow_prorated_thresholds=allow_prorated_thresholds,
        official_holiday_mask=official_holiday_mask,
        observation_dates=observation_dates,
        calendar=calendar,
    )
    _log_backtesting_result(result, policy, run_id=run_id, desk_id=desk_id)
    return result


def trading_desk_backtest_trace_for_policy(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates_by_confidence: Mapping[float, FloatVector],
    policy: RegulatoryPolicy,
    allow_prorated_thresholds: bool = False,
    official_holiday_mask: BoolVector | None = None,
    observation_dates: Sequence[date] | None = None,
    calendar: BusinessCalendar | None = None,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> TradingDeskBacktestTraceResult:
    """Run policy backtesting and include per-observation exception traces.
    Parameters
    ----------
    apl : FloatVector
        Apl.
    hpl : FloatVector
        Hpl.
    var_estimates_by_confidence : Mapping[float, FloatVector]
        Var estimates by confidence.
    policy : RegulatoryPolicy
        Policy.
    allow_prorated_thresholds : bool, optional
        Allow prorated thresholds.
    official_holiday_mask : BoolVector | None, optional
        Official holiday mask.
    observation_dates : Sequence[date] | None, optional
        Observation dates.
    calendar : BusinessCalendar | None, optional
        Calendar.
    run_id : str | None, optional
        Run id.
    desk_id : str | None, optional
        Desk id.

    Returns
    -------
    TradingDeskBacktestTraceResult
        Result of the operation.
    """
    result = trading_desk_backtest_trace(
        apl,
        hpl,
        var_estimates_by_confidence,
        window=policy.backtesting_window_days,
        exception_limits=policy.backtesting_exception_limits,
        minimum_history=policy.backtesting_minimum_history_days,
        allow_prorated_thresholds=allow_prorated_thresholds,
        official_holiday_mask=official_holiday_mask,
        observation_dates=observation_dates,
        calendar=calendar,
    )
    _log_backtesting_result(result.result, policy, run_id=run_id, desk_id=desk_id)
    return result


def backtest_for_policy(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates: FloatVector,
    policy: RegulatoryPolicy,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> BacktestResult:
    """Run scalar backtesting using policy window and history settings.
    Parameters
    ----------
    apl : FloatVector
        Apl.
    hpl : FloatVector
        Hpl.
    var_estimates : FloatVector
        Var estimates.
    policy : RegulatoryPolicy
        Policy.
    run_id : str | None, optional
        Run id.
    desk_id : str | None, optional
        Desk id.

    Returns
    -------
    BacktestResult
        Result of the operation.
    """
    result = backtest(
        apl,
        hpl,
        var_estimates,
        window=policy.backtesting_window_days,
        minimum_history=policy.backtesting_minimum_history_days,
    )
    logger.info(
        "backtest_complete",
        extra=calculation_log_extra(
            run_id=run_id,
            desk_id=desk_id,
            regime=policy.regime.value,
            apl_exceptions=result.apl_exceptions,
            hpl_exceptions=result.hpl_exceptions,
            apl_zone=result.apl_zone,
            hpl_zone=result.hpl_zone,
            window_size=result.window_size,
        ),
    )
    return result


def _log_backtesting_result(
    result: TradingDeskBacktestResult,
    policy: RegulatoryPolicy,
    *,
    run_id: str | None,
    desk_id: str | None,
) -> None:
    max_apl_exceptions = max(
        (level.apl_exceptions for level in result.levels),
        default=0,
    )
    max_hpl_exceptions = max(
        (level.hpl_exceptions for level in result.levels),
        default=0,
    )
    logger.info(
        "trading_desk_backtest_complete",
        extra=calculation_log_extra(
            run_id=run_id,
            desk_id=desk_id,
            regime=policy.regime.value,
            model_eligible=result.model_eligible,
            window_size=result.window_size,
            level_count=len(result.levels),
            max_apl_exceptions=max_apl_exceptions,
            max_hpl_exceptions=max_hpl_exceptions,
        ),
    )


__all__ = (
    "backtest_for_policy",
    "trading_desk_backtest_for_policy",
    "trading_desk_backtest_trace_for_policy",
)
