"""
Backtesting prototype.

Working assumption (NPR 2.0 / Basel FRTB IMA):

    Count VaR exceptions over the most recent 250 business days.
    An exception occurs when the actual loss exceeds the VaR estimate.

    Two exception series are counted separately:
        - APL exceptions: Actual P&L (APL) vs VaR
        - HPL exceptions: Hypothetical P&L (HPL) vs VaR

    NPR 2.0 trading-desk backtesting uses VaR-based measures at both 97.5%
    and 99.0% one-tailed confidence levels.
    The 250-day window is the Basel / NPR 2.0 standard backtesting window.

    Exception count thresholds (Basel traffic-light):
        Green:  0-4  exceptions
        Amber:  5-9  exceptions
        Red:   10+     exceptions

    These thresholds are prototype working assumptions.

Regulatory traceability:
    Basel MAR32 backtesting; U.S. NPR 2.0 APL/HPL VaR backtesting over 250
    business days; EU CRR Article 325bf and Delegated Regulation (EU)
    2022/2059. See docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt

from frtb_ima.logging import calculation_log_extra
from frtb_ima.regimes import DEFAULT_BACKTESTING_EXCEPTION_LIMITS, RegulatoryPolicy

# Basel backtesting traffic-light thresholds
GREEN_MAX = 4
AMBER_MAX = 9
FloatVector = Sequence[float] | npt.NDArray[np.float64]
BoolVector = Sequence[bool] | npt.NDArray[np.bool_]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestResult:
    """Basic APL/HPL backtesting result for one VaR vector."""

    apl_exceptions: int
    hpl_exceptions: int
    apl_zone: str   # "GREEN", "AMBER", "RED"
    hpl_zone: str
    window_size: int

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "apl_exceptions": self.apl_exceptions,
            "hpl_exceptions": self.hpl_exceptions,
            "apl_zone": self.apl_zone,
            "hpl_zone": self.hpl_zone,
            "window_size": self.window_size,
        }


@dataclass(frozen=True)
class BacktestLevelResult:
    """Backtesting result for one VaR confidence level."""

    confidence_level: float
    apl_exceptions: int
    hpl_exceptions: int
    exception_limit: float
    apl_passed: bool
    hpl_passed: bool
    level_passed: bool
    window_size: int

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "confidence_level": self.confidence_level,
            "apl_exceptions": self.apl_exceptions,
            "hpl_exceptions": self.hpl_exceptions,
            "exception_limit": self.exception_limit,
            "apl_passed": self.apl_passed,
            "hpl_passed": self.hpl_passed,
            "level_passed": self.level_passed,
            "window_size": self.window_size,
        }


@dataclass(frozen=True)
class TradingDeskBacktestResult:
    """NPR 2.0 trading-desk backtesting assessment across VaR levels."""

    levels: tuple[BacktestLevelResult, ...]
    window_size: int
    model_eligible: bool

    def level(self, confidence_level: float) -> BacktestLevelResult:
        """Return the result for one configured VaR confidence level."""
        for result in self.levels:
            if result.confidence_level == confidence_level:
                return result
        raise KeyError(f"No backtesting result for confidence level {confidence_level}")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "window_size": self.window_size,
            "model_eligible": self.model_eligible,
            "levels": [level.as_dict() for level in self.levels],
        }


@dataclass(frozen=True)
class BacktestObservationTrace:
    """One windowed backtesting observation for audit and exception review."""

    original_index: int
    observation_date: date | None
    apl: float | None
    hpl: float | None
    var_estimate: float | None
    official_holiday: bool
    apl_exception: bool
    hpl_exception: bool
    apl_reason: str
    hpl_reason: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "original_index": self.original_index,
            "observation_date": self.observation_date.isoformat()
            if self.observation_date is not None
            else None,
            "apl": self.apl,
            "hpl": self.hpl,
            "var_estimate": self.var_estimate,
            "official_holiday": self.official_holiday,
            "apl_exception": self.apl_exception,
            "hpl_exception": self.hpl_exception,
            "apl_reason": self.apl_reason,
            "hpl_reason": self.hpl_reason,
        }


@dataclass(frozen=True)
class BacktestLevelTrace:
    """Backtesting level result plus the dated observation trace."""

    result: BacktestLevelResult
    observations: tuple[BacktestObservationTrace, ...]

    @property
    def confidence_level(self) -> float:
        """VaR confidence level for this trace."""
        return self.result.confidence_level

    def exception_observations(self) -> tuple[BacktestObservationTrace, ...]:
        """Return observations where either APL or HPL produced an exception."""
        return tuple(
            observation
            for observation in self.observations
            if observation.apl_exception or observation.hpl_exception
        )

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "result": self.result.as_dict(),
            "observations": [
                observation.as_dict() for observation in self.observations
            ],
        }


@dataclass(frozen=True)
class TradingDeskBacktestTraceResult:
    """NPR backtesting result with per-level dated exception traces."""

    result: TradingDeskBacktestResult
    levels: tuple[BacktestLevelTrace, ...]

    @property
    def window_size(self) -> int:
        """Number of observations used after policy windowing."""
        return self.result.window_size

    @property
    def model_eligible(self) -> bool:
        """Whether every configured APL/HPL VaR level passed."""
        return self.result.model_eligible

    def level(self, confidence_level: float) -> BacktestLevelTrace:
        """Return the trace for one configured VaR confidence level."""
        for trace in self.levels:
            if trace.confidence_level == confidence_level:
                return trace
        raise KeyError(f"No backtesting trace for confidence level {confidence_level}")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "window_size": self.window_size,
            "model_eligible": self.model_eligible,
            "levels": [level.as_dict() for level in self.levels],
        }


def _as_finite_1d_array(values: FloatVector, name: str) -> npt.NDArray[np.float64]:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if arr.size == 0:
        raise ValueError(f"{name} is empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr.astype(np.float64, copy=False)


def _as_1d_array_allowing_missing(
    values: FloatVector,
    name: str,
) -> npt.NDArray[np.float64]:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if arr.size == 0:
        raise ValueError(f"{name} is empty")
    return arr.astype(np.float64, copy=False)


def _validate_observation_dates(
    observation_dates: Sequence[date] | None,
    expected_length: int,
) -> tuple[date, ...] | None:
    if observation_dates is None:
        return None
    dates = tuple(observation_dates)
    if len(dates) != expected_length:
        raise ValueError("observation_dates length must match APL/HPL")
    if not all(isinstance(item, date) for item in dates):
        raise TypeError("observation_dates must contain datetime.date values")
    return dates


def _float_or_none(value: float) -> float | None:
    if np.isfinite(value):
        return float(value)
    return None


def _zone(count: int) -> str:
    if count <= GREEN_MAX:
        return "GREEN"
    elif count <= AMBER_MAX:
        return "AMBER"
    return "RED"


def count_exceptions(
    pnl: FloatVector,
    var_estimates: FloatVector,
) -> int:
    """
    Count observations where loss exceeds the VaR estimate.

    Convention:
        pnl values:        positive = profit, negative = loss.
        var_estimates:     positive scalar (the magnitude of the VaR threshold).

    An exception occurs when -pnl[i] > var_estimates[i],
    i.e. actual loss exceeds estimated VaR.

    Args:
        pnl:           P&L observations (positive = profit).
        var_estimates: Corresponding daily VaR values (positive magnitude).

    Returns:
        Number of exceptions.

    Raises:
        ValueError: if lengths differ or inputs are empty.
    """
    pnl_arr = _as_finite_1d_array(pnl, "pnl")
    var_arr = _as_finite_1d_array(var_estimates, "var_estimates")

    if len(pnl_arr) != len(var_arr):
        raise ValueError(
            f"pnl length ({len(pnl_arr)}) != var_estimates length ({len(var_arr)})"
        )
    if np.any(var_arr <= 0.0):
        raise ValueError("var_estimates must contain only positive values")

    return int(np.sum(-pnl_arr > var_arr))


def _count_exceptions_regulatory(
    pnl: npt.NDArray[np.float64],
    var_estimates: npt.NDArray[np.float64],
    official_holiday_mask: npt.NDArray[np.bool_] | None,
) -> int:
    """
    Count exceptions with NPR missing-data treatment.

    Missing P&L or VaR values count as exceptions unless the missing value is
    related to an official holiday. This function assumes inputs have already
    been windowed and length-aligned.
    """
    return int(
        np.sum(_exception_flags_regulatory(pnl, var_estimates, official_holiday_mask))
    )


def _exception_flags_regulatory(
    pnl: npt.NDArray[np.float64],
    var_estimates: npt.NDArray[np.float64],
    official_holiday_mask: npt.NDArray[np.bool_] | None,
) -> npt.NDArray[np.bool_]:
    finite_pnl = np.isfinite(pnl)
    finite_var = np.isfinite(var_estimates)
    missing = ~(finite_pnl & finite_var)
    loss_exceeds_var = finite_pnl & finite_var & (-pnl > var_estimates)

    exceptions = missing | loss_exceeds_var
    if official_holiday_mask is not None:
        exceptions = exceptions & ~official_holiday_mask
    return exceptions.astype(np.bool_, copy=False)


def _exception_reason(
    pnl_value: float,
    var_value: float,
    official_holiday: bool,
    is_exception: bool,
) -> str:
    if official_holiday:
        return "official_holiday"
    finite_pnl = bool(np.isfinite(pnl_value))
    finite_var = bool(np.isfinite(var_value))
    if not finite_pnl and not finite_var:
        return "missing_pnl_and_var"
    if not finite_pnl:
        return "missing_pnl"
    if not finite_var:
        return "missing_var"
    if is_exception:
        return "loss_exceeds_var"
    return "none"


def backtest(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates: FloatVector,
    window: int = 250,
    minimum_history: int | None = None,
) -> BacktestResult:
    """
    Run backtesting over the most recent `window` observations.

    Args:
        apl:            Actual P&L series (positive = profit).
        hpl:            Hypothetical P&L series (positive = profit).
        var_estimates:  Daily VaR magnitudes (positive scalars).
        window:         Number of most recent business days to evaluate.
                        Default 250 per Basel / NPR 2.0.
        minimum_history: Optional minimum number of observations required before
                         windowing.

    Returns:
        BacktestResult with exception counts and zone classifications.
    """
    if window <= 0:
        raise ValueError(f"window must be positive, got {window}")
    if minimum_history is not None and minimum_history <= 0:
        raise ValueError(
            f"minimum_history must be positive when provided, got {minimum_history}"
        )

    apl_arr = _as_finite_1d_array(apl, "apl")
    hpl_arr = _as_finite_1d_array(hpl, "hpl")
    var_arr = _as_finite_1d_array(var_estimates, "var_estimates")

    if minimum_history is not None:
        min_length = min(len(apl_arr), len(hpl_arr), len(var_arr))
        if min_length < minimum_history:
            raise ValueError(
                "APL, HPL, and VaR series must contain at least "
                f"{minimum_history} observations before windowing"
            )

    apl_w = apl_arr[-window:]
    hpl_w = hpl_arr[-window:]
    var_w = var_arr[-window:]

    if len(apl_w) != len(var_w) or len(hpl_w) != len(var_w):
        raise ValueError(
            "After windowing, APL, HPL, and VaR series must have equal length"
        )
    if np.any(var_w <= 0.0):
        raise ValueError("var_estimates must contain only positive values")

    n_apl = int(np.sum(-apl_w > var_w))
    n_hpl = int(np.sum(-hpl_w > var_w))

    return BacktestResult(
        apl_exceptions=n_apl,
        hpl_exceptions=n_hpl,
        apl_zone=_zone(n_apl),
        hpl_zone=_zone(n_hpl),
        window_size=len(var_w),
    )


def trading_desk_backtest(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates_by_confidence: Mapping[float, FloatVector],
    window: int = 250,
    exception_limits: Sequence[
        tuple[float, int]
    ] = DEFAULT_BACKTESTING_EXCEPTION_LIMITS,
    minimum_history: int | None = None,
    allow_prorated_thresholds: bool = False,
    official_holiday_mask: BoolVector | None = None,
) -> TradingDeskBacktestResult:
    """
    Run NPR 2.0 trading-desk backtesting across VaR confidence levels.

    The proposed rule requires separate exception counts for APL and HPL at
    both the 97.5th and 99.0th percentiles over the most recent 250 business
    days. A desk fails the backtesting gate if either APL or HPL breaches the
    configured exception limit at any required VaR level.

    Missing APL, HPL, or VaR values are counted as exceptions unless the
    corresponding day is marked as an official holiday.
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
    ).result


def trading_desk_backtest_trace(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates_by_confidence: Mapping[float, FloatVector],
    window: int = 250,
    exception_limits: Sequence[
        tuple[float, int]
    ] = DEFAULT_BACKTESTING_EXCEPTION_LIMITS,
    minimum_history: int | None = None,
    allow_prorated_thresholds: bool = False,
    official_holiday_mask: BoolVector | None = None,
    observation_dates: Sequence[date] | None = None,
) -> TradingDeskBacktestTraceResult:
    """
    Run NPR 2.0 trading-desk backtesting with per-observation audit traces.

    Counts remain vectorized; the observation trace is built after the vector
    exception masks are computed so callers can review exact dates, values, and
    missing-data reasons.
    """
    if window <= 0:
        raise ValueError(f"window must be positive, got {window}")
    if minimum_history is not None and minimum_history <= 0:
        raise ValueError(
            f"minimum_history must be positive when provided, got {minimum_history}"
        )

    apl_arr = _as_1d_array_allowing_missing(apl, "apl")
    hpl_arr = _as_1d_array_allowing_missing(hpl, "hpl")

    if len(apl_arr) != len(hpl_arr):
        raise ValueError("APL and HPL series must have equal length")
    dates = _validate_observation_dates(observation_dates, len(apl_arr))

    holiday_arr: npt.NDArray[np.bool_] | None = None
    if official_holiday_mask is not None:
        holiday_arr = np.asarray(official_holiday_mask, dtype=bool)
        if holiday_arr.ndim != 1:
            raise ValueError("official_holiday_mask must be one-dimensional")
        if len(holiday_arr) != len(apl_arr):
            raise ValueError("official_holiday_mask length must match APL/HPL")

    min_length = len(apl_arr)
    for confidence_level, _limit in exception_limits:
        if confidence_level not in var_estimates_by_confidence:
            raise KeyError(f"Missing VaR series for confidence level {confidence_level}")
        var_arr = _as_1d_array_allowing_missing(
            var_estimates_by_confidence[confidence_level],
            f"var_estimates[{confidence_level}]",
        )
        if len(var_arr) != len(apl_arr):
            raise ValueError(
                f"VaR series length for {confidence_level} must match APL/HPL"
            )
        min_length = min(min_length, len(var_arr))

    if minimum_history is not None and min_length < minimum_history:
        if not allow_prorated_thresholds:
            raise ValueError(
                "APL, HPL, and VaR series must contain at least "
                f"{minimum_history} observations before windowing"
            )

    window_size = min(window, min_length)
    start_index = min_length - window_size
    apl_w = apl_arr[-window_size:]
    hpl_w = hpl_arr[-window_size:]
    holiday_w = holiday_arr[-window_size:] if holiday_arr is not None else None
    dates_w = dates[-window_size:] if dates is not None else None

    level_results: list[BacktestLevelResult] = []
    level_traces: list[BacktestLevelTrace] = []
    for confidence_level, limit in exception_limits:
        var_w = _as_1d_array_allowing_missing(
            var_estimates_by_confidence[confidence_level],
            f"var_estimates[{confidence_level}]",
        )[-window_size:]
        finite_var = var_w[np.isfinite(var_w)]
        if np.any(finite_var <= 0.0):
            raise ValueError("finite VaR estimates must contain only positive values")

        exception_limit = float(limit)
        if allow_prorated_thresholds and window_size < window:
            exception_limit = exception_limit * window_size / window

        apl_exception_flags = _exception_flags_regulatory(apl_w, var_w, holiday_w)
        hpl_exception_flags = _exception_flags_regulatory(hpl_w, var_w, holiday_w)
        apl_exceptions = int(np.sum(apl_exception_flags))
        hpl_exceptions = int(np.sum(hpl_exception_flags))
        apl_passed = apl_exceptions <= exception_limit
        hpl_passed = hpl_exceptions <= exception_limit
        level_result = BacktestLevelResult(
            confidence_level=confidence_level,
            apl_exceptions=apl_exceptions,
            hpl_exceptions=hpl_exceptions,
            exception_limit=exception_limit,
            apl_passed=apl_passed,
            hpl_passed=hpl_passed,
            level_passed=apl_passed and hpl_passed,
            window_size=window_size,
        )
        level_results.append(level_result)

        observations: list[BacktestObservationTrace] = []
        for offset in range(window_size):
            official_holiday = (
                bool(holiday_w[offset]) if holiday_w is not None else False
            )
            observation_date = dates_w[offset] if dates_w is not None else None
            observations.append(
                BacktestObservationTrace(
                    original_index=start_index + offset,
                    observation_date=observation_date,
                    apl=_float_or_none(float(apl_w[offset])),
                    hpl=_float_or_none(float(hpl_w[offset])),
                    var_estimate=_float_or_none(float(var_w[offset])),
                    official_holiday=official_holiday,
                    apl_exception=bool(apl_exception_flags[offset]),
                    hpl_exception=bool(hpl_exception_flags[offset]),
                    apl_reason=_exception_reason(
                        float(apl_w[offset]),
                        float(var_w[offset]),
                        official_holiday,
                        bool(apl_exception_flags[offset]),
                    ),
                    hpl_reason=_exception_reason(
                        float(hpl_w[offset]),
                        float(var_w[offset]),
                        official_holiday,
                        bool(hpl_exception_flags[offset]),
                    ),
                )
            )
        level_traces.append(
            BacktestLevelTrace(
                result=level_result,
                observations=tuple(observations),
            )
        )

    result = TradingDeskBacktestResult(
        levels=tuple(level_results),
        window_size=window_size,
        model_eligible=all(result.level_passed for result in level_results),
    )
    return TradingDeskBacktestTraceResult(
        result=result,
        levels=tuple(level_traces),
    )


def trading_desk_backtest_for_policy(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates_by_confidence: Mapping[float, FloatVector],
    policy: RegulatoryPolicy,
    allow_prorated_thresholds: bool = False,
    official_holiday_mask: BoolVector | None = None,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> TradingDeskBacktestResult:
    """Run trading-desk backtesting using a policy's NPR 2.0 gate parameters."""
    result = trading_desk_backtest(
        apl,
        hpl,
        var_estimates_by_confidence,
        window=policy.backtesting_window_days,
        exception_limits=policy.backtesting_exception_limits,
        minimum_history=policy.backtesting_minimum_history_days,
        allow_prorated_thresholds=allow_prorated_thresholds,
        official_holiday_mask=official_holiday_mask,
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
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> TradingDeskBacktestTraceResult:
    """Run policy backtesting and include per-observation exception traces."""
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
    """Run backtesting using a policy's window and minimum-history assumptions."""
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
