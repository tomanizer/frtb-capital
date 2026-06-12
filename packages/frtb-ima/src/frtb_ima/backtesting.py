"""
Compatibility import surface for IMA backtesting diagnostics.

Backtesting records, scalar kernels, trace assembly, and policy wrappers now
live in focused ``backtesting_*`` modules. This module preserves the historical
``frtb_ima.backtesting`` public import path.
"""

from frtb_ima.backtesting_core import backtest, count_exceptions
from frtb_ima.backtesting_policy import (
    backtest_for_policy,
    trading_desk_backtest_for_policy,
    trading_desk_backtest_trace_for_policy,
)
from frtb_ima.backtesting_trace import trading_desk_backtest, trading_desk_backtest_trace
from frtb_ima.backtesting_types import (
    BacktestLevelResult,
    BacktestLevelTrace,
    BacktestObservationTrace,
    BacktestResult,
    BoolVector,
    FloatVector,
    TradingDeskBacktestResult,
    TradingDeskBacktestTraceResult,
)

__all__ = (
    "BacktestLevelResult",
    "BacktestLevelTrace",
    "BacktestObservationTrace",
    "BacktestResult",
    "BoolVector",
    "FloatVector",
    "TradingDeskBacktestResult",
    "TradingDeskBacktestTraceResult",
    "backtest",
    "backtest_for_policy",
    "count_exceptions",
    "trading_desk_backtest",
    "trading_desk_backtest_for_policy",
    "trading_desk_backtest_trace",
    "trading_desk_backtest_trace_for_policy",
)
