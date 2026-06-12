"""Per-confidence-level helpers for IMA backtesting trace assembly."""

from __future__ import annotations

from datetime import date

import numpy as np
import numpy.typing as npt

from frtb_ima.backtesting_trace_inputs import as_1d_array_allowing_missing, float_or_none
from frtb_ima.backtesting_types import (
    BacktestLevelResult,
    BacktestLevelTrace,
    BacktestObservationTrace,
    FloatVector,
)
from frtb_ima.validation.backtesting_stages import _exception_flags_regulatory, _exception_reason


def build_level_trace(
    confidence_level: float,
    limit: int,
    var_series: FloatVector,
    *,
    apl_w: npt.NDArray[np.float64],
    hpl_w: npt.NDArray[np.float64],
    holiday_w: npt.NDArray[np.bool_] | None,
    dates_w: tuple[date, ...] | None,
    start_index: int,
    window: int,
    window_size: int,
    allow_prorated_thresholds: bool,
) -> tuple[BacktestLevelResult, BacktestLevelTrace]:
    """Build one confidence-level result and dated observation trace.
    Parameters
    ----------
    confidence_level : float
        Var confidence level.
    limit : int
        Exception limit.
    var_series : FloatVector
        VaR series.

    Returns
    -------
    tuple[BacktestLevelResult, BacktestLevelTrace]
        Result and trace for the configured confidence level.
    """
    var_w = as_1d_array_allowing_missing(
        var_series,
        f"var_estimates[{confidence_level}]",
    )[-window_size:]
    finite_var = var_w[np.isfinite(var_w)]
    if np.any(finite_var <= 0.0):
        raise ValueError("finite VaR estimates must contain only positive values")

    exception_limit = _exception_limit(limit, window_size, window, allow_prorated_thresholds)
    apl_exception_flags = _exception_flags_regulatory(apl_w, var_w, holiday_w)
    hpl_exception_flags = _exception_flags_regulatory(hpl_w, var_w, holiday_w)
    apl_exceptions = int(np.sum(apl_exception_flags))
    hpl_exceptions = int(np.sum(hpl_exception_flags))
    level_result = BacktestLevelResult(
        confidence_level=confidence_level,
        apl_exceptions=apl_exceptions,
        hpl_exceptions=hpl_exceptions,
        exception_limit=exception_limit,
        apl_passed=apl_exceptions <= exception_limit,
        hpl_passed=hpl_exceptions <= exception_limit,
        level_passed=apl_exceptions <= exception_limit and hpl_exceptions <= exception_limit,
        window_size=window_size,
    )
    observations = _build_observation_traces(
        apl_w,
        hpl_w,
        var_w,
        holiday_w,
        dates_w,
        apl_exception_flags,
        hpl_exception_flags,
        start_index=start_index,
    )
    return level_result, BacktestLevelTrace(level_result, observations)


def _exception_limit(
    limit: int,
    window_size: int,
    window: int,
    allow_prorated_thresholds: bool,
) -> float:
    if allow_prorated_thresholds and window_size < window:
        return float(limit) * window_size / window
    return float(limit)


def _build_observation_traces(
    apl_w: npt.NDArray[np.float64],
    hpl_w: npt.NDArray[np.float64],
    var_w: npt.NDArray[np.float64],
    holiday_w: npt.NDArray[np.bool_] | None,
    dates_w: tuple[date, ...] | None,
    apl_exception_flags: npt.NDArray[np.bool_],
    hpl_exception_flags: npt.NDArray[np.bool_],
    *,
    start_index: int,
) -> tuple[BacktestObservationTrace, ...]:
    return tuple(
        _observation_trace(
            offset,
            apl_w,
            hpl_w,
            var_w,
            holiday_w,
            dates_w,
            apl_exception_flags,
            hpl_exception_flags,
            start_index=start_index,
        )
        for offset in range(len(var_w))
    )


def _observation_trace(
    offset: int,
    apl_w: npt.NDArray[np.float64],
    hpl_w: npt.NDArray[np.float64],
    var_w: npt.NDArray[np.float64],
    holiday_w: npt.NDArray[np.bool_] | None,
    dates_w: tuple[date, ...] | None,
    apl_exception_flags: npt.NDArray[np.bool_],
    hpl_exception_flags: npt.NDArray[np.bool_],
    *,
    start_index: int,
) -> BacktestObservationTrace:
    official_holiday = bool(holiday_w[offset]) if holiday_w is not None else False
    apl_exception = bool(apl_exception_flags[offset])
    hpl_exception = bool(hpl_exception_flags[offset])
    return BacktestObservationTrace(
        original_index=start_index + offset,
        observation_date=dates_w[offset] if dates_w is not None else None,
        apl=float_or_none(float(apl_w[offset])),
        hpl=float_or_none(float(hpl_w[offset])),
        var_estimate=float_or_none(float(var_w[offset])),
        official_holiday=official_holiday,
        apl_exception=apl_exception,
        hpl_exception=hpl_exception,
        apl_reason=_exception_reason(
            float(apl_w[offset]),
            float(var_w[offset]),
            official_holiday,
            apl_exception,
        ),
        hpl_reason=_exception_reason(
            float(hpl_w[offset]),
            float(var_w[offset]),
            official_holiday,
            hpl_exception,
        ),
    )


__all__ = ("build_level_trace",)
